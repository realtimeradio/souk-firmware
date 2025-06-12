"""
Read the TSU seconds register and each time it changes
set the strobe comparison register so that a pulse
is emitted on the next second boundary.
"""

import time
import os
import struct
from mmap import mmap, PROT_READ, PROT_WRITE, MAP_SHARED

# See https://docs.amd.com/r/en-US/ug1087-zynq-ultrascale-registers/GEM-Module for registers
GEM2_OFFSET = 0xFF0D0000
MAP_SIZE = 0x200

TSU_TIMER_MSB_SEC = 0x1C0 # TSU seconds bits 47:32
TSU_TIMER_SEC = 0x1D0     # TSU seconds bits 31:0
TSU_TIMER_NSEC = 0x1D4    # TSU nanoseconds
TSU_CMP_MSB_SEC = 0x0E4   # Timer comparison seconds bits 47:32
TSU_CMP_SEC = 0x0E0       # Timer comparison seconds bits 31:0
TSU_CMP_NSEC = 0x0DC      # Timer compare nanoseconds

MEM_DEV = '/dev/mem'

fd = os.open(MEM_DEV, os.O_RDWR | os.O_SYNC)
mm = mmap(fd, MAP_SIZE, offset=GEM2_OFFSET, flags=MAP_SHARED, prot=PROT_READ | PROT_WRITE)

def read(mm, addr):
    raw = mm[addr:addr+4]
    return struct.unpack('<I', raw)[0]

def write(mm, addr, val):
    raw = struct.pack('<I', val)
    mm[addr:addr+4] = raw

# Pulse on second boundaries (ns = 0)
print('Setting NS comparison to 0')
write(mm, TSU_CMP_NSEC, 0)

# Set the second MSB bits, which only change every 2**32 seconds
print('Setting SEC MSB comparison')
sec_msb = read(mm, TSU_TIMER_MSB_SEC)
print('Value is %d (expecting 0)' % sec_msb)
write(mm, TSU_CMP_MSB_SEC, sec_msb)

t_old = read(mm, TSU_TIMER_SEC)
while(True):
    try:
        t = read(mm, TSU_TIMER_SEC)
        if t != t_old:
            # Catch the unlikely case of counter rollover
            if t == 0xffffffff:
                sec_msb = sec_msb + 1
                print('Setting SEC MSB comparison to %d' % sec_msb)
                write(mm, TSU_CMP_MSB_SEC, sec_msb)
            write(mm, TSU_CMP_SEC, t+1)
            t_old = t
        time.sleep(0.001)
    except KeyboardInterrupt:
        break

mm.close()
os.close(fd)

"""
Read the TSU seconds register
and each time it changes print its contents
as well as time.time()
"""

import time
import os
import struct
from mmap import mmap, PROT_READ, PROT_WRITE, MAP_SHARED

TSU_TIMER_MSB_SEC = 0x1C0
TSU_TIMER_SEC = 0x1D0
TSU_TIMER_NSEC = 0x1D4
GEM2_OFFSET = 0xFF0D0000
MAP_SIZE = 0x200

MEM_DEV = '/dev/mem'

fd = os.open(MEM_DEV, os.O_RDWR | os.O_SYNC)
mm = mmap(fd, MAP_SIZE, offset=GEM2_OFFSET, flags=MAP_SHARED, prot=PROT_READ | PROT_WRITE)

def read(mm, addr):
   raw = mm[addr:addr+4]
   return struct.unpack('<I', raw)[0]

print(read(mm, TSU_TIMER_SEC))

t_old = read(mm, TSU_TIMER_SEC)
while(True):
    try:
        t = read(mm, TSU_TIMER_SEC)
        if t != t_old:
            print(time.time(), t)
            t_old = t
        time.sleep(0.0001)
    except KeyboardInterrupt:
        break

mm.close()
os.close(fd)

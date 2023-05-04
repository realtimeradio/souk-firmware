#!/usr/bin/env python3

import os
import glob

SENSOR_PATH = '/sys/bus/i2c/devices'

# Voltage name -> I2C address (From RFSoC4x2 schematics)
sensors = {
        'VCC_0V85' : 0x40,
        'VCC_3V3'  : 0x41,
        'VCC_1V8'  : 0x42,
        'SYZYGY_VIO_BUS' : 0x48,
        'VDAC_AVCC_0V925' : 0x43,
        'VDAC_AVCC_AUX_1V8' : 0x46,
        'VDAC_AVTT_2V5' : 0x47,
        'VADC_AVCC_0V925' : 0x44,
        'VADC_AVCC_AUX_1V8' : 0x45,
        }

# Voltage name -> current limit (From RFSoC4x2 Schematics)
limits = {
        'VCC_0V85' : 40,
        'VCC_3V3'  : 6,
        'VCC_1V8'  : 6,
        'SYZYGY_VIO_BUS' : 6,
        'VDAC_AVCC_0V925' : 3,
        'VDAC_AVCC_AUX_1V8' : 2,
        'VDAC_AVTT_2V5' : 2,
        'VADC_AVCC_0V925' : 3,
        'VADC_AVCC_AUX_1V8' : 2,
        }

def read_int(fname):
    with open(fname, 'r') as fh:
        s = fh.read()
    return float(s)

for sensor, addr in sensors.items():
    name = sensor
    dev = glob.glob(os.path.join(SENSOR_PATH, '0-00%x'%addr, 'iio:device?'))
    assert len(dev) == 1
    dev = dev[0]
    raw = read_int(os.path.join(dev, 'in_current3_raw'))
    scale = read_int(os.path.join(dev, 'in_current3_scale'))
    current = scale * raw / 1000.
    #raw = read_int(os.path.join(sensor, 'in_voltage0_raw'))
    #scale = read_int(os.path.join(sensor, 'in_voltage0_scale'))
    #v0 = scale * raw / 1000.
    raw = read_int(os.path.join(dev, 'in_voltage1_raw'))
    scale = read_int(os.path.join(dev, 'in_voltage1_scale'))
    v1 = scale * raw / 1000.
    utilisation = current / limits[sensor]
    if utilisation > 1:
        print("WARNING: CURRENT LIMIT EXCEEDED!")
    print('%20s: %.2f Volt, %.2f Amp (%d%% max)' % (name, v1, current, utilisation*100))

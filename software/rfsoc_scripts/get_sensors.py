#!/usr/bin/env python3

import os
import glob

SENSOR_PATH = '/sys/bus/iio/devices/iio:device0/'

def read_int(fname):
    with open(fname, 'r') as fh:
        s = fh.read()
    return float(s)

sensor_files = sorted(glob.glob(os.path.join(SENSOR_PATH, 'in_*_raw')))

for sensor_file in sensor_files:
    sensor = os.path.basename(sensor_file)
    sensor = sensor[3:] # strip "in_"
    sensor = sensor[0:-4] # strip "_raw"
    raw = read_int(SENSOR_PATH + 'in_' + sensor + '_raw')
    scale = read_int(SENSOR_PATH + 'in_' + sensor + '_scale')
    if sensor.startswith('temp'):
        offset = read_int(SENSOR_PATH + 'in_' + sensor + '_offset')
    else:
        offset = 0
    v = scale * (raw + offset) / 1000.
    if sensor.startswith('voltage'):
        name = sensor.split('_', 1)[1]
    else:
        name = sensor
    print('%10s: %.3f' % (name, v))

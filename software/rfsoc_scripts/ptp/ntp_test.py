"""
Print the current time, in seconds, on each second boundary.
"""

import time

t_old = 0
while(True):
    t = int(time.time())
    if t != t_old:
        print(t)
        t_old = t

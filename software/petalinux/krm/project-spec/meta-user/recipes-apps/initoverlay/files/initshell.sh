#!/bin/sh

echo "[initshell] entering shell..."
mount -t proc none /proc
mount -t sysfs none /sys
exec /bin/sh

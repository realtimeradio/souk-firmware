#!/bin/sh

# Fail on errors
set -e

mount -t proc none /proc
mount -t sysfs none /sys

echo "[initoverlay] Booting with overlayfs + NFS root"

# --- 1. Read kernel command line ------------------------------

CMDLINE="$(cat /proc/cmdline)"

# Extract ip= and nfsroot= if present
NFSROOT="$(echo "$CMDLINE" | sed -n 's/.*nfsroot=\([^ ,]*\).*/\1/p')"

# Sanity check
if [ -z "$NFSROOT" ]; then
    echo "[initoverlay] ERROR: nfsroot= not supplied on kernel cmdline"
    echo "  Example:  nfsroot=10.11.0.198:/exports/zynqmp/ubuntu24,v3,tcp"
    exec /bin/sh
fi

echo "[initoverlay] Using NFS root: $NFSROOT"

# --- 2. Prepare directories -----------------------------------

mount -t tmpfs tmpfs /run
#mount -t tmpfs tmpfs /dev
mount -t tmpfs tmpfs /mnt

mkdir -p /mnt/lower
mkdir -p /mnt/upper
mkdir -p /mnt/work
mkdir -p /mnt/newroot

# --- 3. Mount the NFS root read-only ---------------------------

echo "[initoverlay] Mounting NFS root read-only"
mount -o ro -t nfs "$NFSROOT" /mnt/lower

# --- 4. Overlay mount -----------------------------------------

echo "[initoverlay] Constructing overlayfs root"
mount -t overlay overlay \
    -o lowerdir=/mnt/lower,upperdir=/mnt/upper,workdir=/mnt/work \
    /mnt/newroot

# --- 5. Switch to new root ------------------------------------

echo "[initoverlay] Switching to new root"
exec switch_root /mnt/newroot /sbin/init

# --- 6. Drop to shell on failure -------------------------------

# We should never reach here unless switch_root fails:
echo "[initoverlay] switch_root failed! Dropping to shell" > /dev/console
exec /bin/sh

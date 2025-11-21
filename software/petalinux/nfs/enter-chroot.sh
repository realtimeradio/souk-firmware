#! /bin/bash

START_DIR=`pwd`
UBUNTU_VERSION="24.04.3"

if [ -n "$1" ]; then
  UBUNTU_VERSION="$1"
fi

ROOTFS=/exports/ubuntu-${UBUNTU_VERSION}-arm64
cd $ROOTFS

mount --bind /dev/ $ROOTFS/dev
mount --bind /dev/pts $ROOTFS/dev/pts
mount --bind /proc/ $ROOTFS/proc
mount --bind /sys/ $ROOTFS/sys
chroot $ROOTFS /bin/bash <<'EOF'
echo "This is the output of uname -a." 
uname -a
EOF

chroot $ROOTFS

# do stuff here

cd $START_DIR
umount $ROOTFS/dev/pts
umount $ROOTFS/dev
umount $ROOTFS/proc
umount $ROOTFS/sys


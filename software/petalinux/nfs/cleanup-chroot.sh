#! /bin/bash

UBUNTU_VERSION="24.04.3"

if [ -n "$1" ]; then
  UBUNTU_VERSION="$1"
fi

ROOTFS=/exports/ubuntu-${UBUNTU_VERSION}-arm64
umount $ROOTFS/dev/pts
umount $ROOTFS/dev
umount $ROOTFS/proc
umount $ROOTFS/sys


#! /bin/bash

START_DIR=`pwd`
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

UBUNTU_VERSION="24.04.3"

if [ -n "$1" ]; then
  UBUNTU_VERSION="$1"
fi

ROOTFS=/exports/ubuntu-${UBUNTU_VERSION}-arm64
UBUNTU_IMG=http://cdimage.ubuntu.com/ubuntu-base/releases/${UBUNTU_VERSION}/release/ubuntu-base-${UBUNTU_VERSION}-base-arm64.tar.gz
QEMU=qemu-aarch64-static

ask_to_continue() {
    read -p "Continue? [y/N] " ans
    [ "$ans" = "y" ] || exit 1
}

echo "Creating rootfs ${ROOTFS}"
echo "Generating from image ${UBUNTU_IMG}"
ask_to_continue

echo "I am going to delete ${ROOTFS}. Is that OK. Be careful!"
ask_to_continue
rm -rf $ROOTFS

mkdir -p $ROOTFS
cd $ROOTFS
apt install -y qemu-user-static
wget $UBUNTU_IMG
tar -xzf ubuntu*.tar.gz

cp -av /usr/bin/$QEMU $ROOTFS/usr/bin/

# Give network access when in chroot, so we can download packages
cp -av /run/systemd/resolve/stub-resolv.conf $ROOTFS/etc/resolv.conf

cp ${SCRIPT_DIR}/scripts/* ${ROOTFS}/usr/bin/


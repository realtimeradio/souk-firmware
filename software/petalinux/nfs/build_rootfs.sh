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

mount --bind /dev/ $ROOTFS/dev
mount --bind /dev/pts $ROOTFS/dev/pts
mount --bind /proc/ $ROOTFS/proc
mount --bind /sys/ $ROOTFS/sys
chroot $ROOTFS /bin/bash <<'EOF'
echo "This is the output of uname -a. Only continue if this looks correct" 
uname -a
EOF
ask_to_continue

chroot $ROOTFS /bin/bash <<'EOF'

# make casper user (password casper)

useradd -G sudo -m -s /bin/bash casper
echo casper:casper | chpasswd

# install packages as needed

apt update

apt install -y locales
echo "Europe/London" > /etc/timezone && \
    dpkg-reconfigure -f noninteractive tzdata && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    echo 'LANG="en_US.UTF-8"'>/etc/default/locale && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=en_US.UTF-8
    update-locale LANGUAGE=en_US.UTF-8
#apt upgrade
apt install -y dialog perl
#apt install -y sudo apt-utils vim ifupdown net-tools ethtool udev iputils-ping resolvconf wget kmod device-tree-compiler openssh-client openssh-server build-essential cmake git i2c-tools

echo "# <file system> <dir> <type> <options> <dump> <pass>" > /etc/fstab
#echo "/dev/mmcblk1p1 /boot  vfat   umask=0002,utf8=true  0 0" >> /etc/fstab

mkdir -p /etc/network/interfaces.d
echo "auto end0" > /etc/network/interfaces.d/end0
echo "iface end0 inet dhcp" >> /etc/network/interfaces.d/end0
if [ -n "$MACADDRESS" ]; then
    echo "    hwaddress ether $MACADDRESS" >> /etc/network/interfaces.d/end0
fi

# exit the chroot
EOF

cd $START_DIR
umount $ROOTFS/dev/pts
umount $ROOTFS/dev
umount $ROOTFS/proc
umount $ROOTFS/sys


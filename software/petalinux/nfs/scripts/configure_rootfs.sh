#! /bin/bash

# make casper user (password casper)

useradd -G sudo -m -s /bin/bash casper
echo casper:casper | chpasswd

# install packages as needed

apt update

apt install -y tzdata locales
locale-gen
update-locale LANG=en_US.UTF-8
update-locale LANGUAGE=en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8
export LC_ALL=en_US.UTF-8
echo "Europe/London" > /etc/timezone
dpkg-reconfigure -f noninteractive tzdata
apt upgrade
apt install -y dialog perl
apt install -y \
	sudo \
	apt-utils \
	vim \
	ifupdown \
	net-tools \
	ethtool \
	udev \
	iputils-ping \
	resolvconf \
	wget \
	kmod \
	device-tree-compiler \
	openssh-client \
	openssh-server \
	build-essential \
	cmake \
	git \
	i2c-tools \
	nfs-common \
    libsysfs2 \
    libsysfs-dev \
    zlib1g \
    zlib1g-dev

# Mount /home on this server's NFS
ip=$(hostname -I | awk '{print $1}') # This server's IP

echo "# <file system> <dir> <type> <options> <dump> <pass>" > /etc/fstab
echo "${ip}:/exports/home /home  nfs defaults,_netdev,nofail 0 0" >> /etc/fstab
#echo "/dev/mmcblk1p1 /boot  vfat   umask=0002,utf8=true  0 0" >> /etc/fstab


mkdir -p /etc/network/interfaces.d
# If this isn't a netboot rootfs, you might want to configure ethernet interfaces here
#echo "auto eth0" > /etc/network/interfaces.d/end0
#echo "iface eth0 inet dhcp" >> /etc/network/interfaces.d/end0
#if [ -n "$MACADDRESS" ]; then
#    echo "    hwaddress ether $MACADDRESS" >> /etc/network/interfaces.d/end0
#fi

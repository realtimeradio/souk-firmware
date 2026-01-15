# Booting the KRC-4700

The preferred booting configuration uses tftp and NFS to netboot a Linux kernel and root filesystem.
This means that no SD cards are required to boot multiple boards.
Instead the boot process is as follows:

  1. On power up, the KRC4700 SoC is configured to boot from 32-bit QSPI flash
  2. The SoC loads first stage bootloaders and U-Boot from flash, as well as environment variables such as MAC address
  3. U-boot attempts to boot Linux from SD card, and if this fails looks to boot using PXE using a TFTP server provided by DHCP
  4. A TFTP server provides Linux over TFTP which mounts an NFS root filesystem read-only, with a writable volatile overlay

To execute the above, the following network services are required.

  1. A DHCP server which provides a TFTP server address
  2. A TFTP server which contains PXE Linux boot config files, and a Linux/initfs image
  3. An NFS server which hosts a read-only root filesystem (and optionally other writable filesystems, such as /home)

## DHCP configuration

A DHCP server should be available on the network, and it should populate the `tftp-server-name` DHCP option (66).
On Ubuntu systems, `dnsmasq` can be used for this purpose (and also provides a TFTP server).

## TFTP configuration

A TFTP server should be configured to serve the files provided in `tftpboot` in its root TFTP directory.
The `pxelinux.cfg/default-arm-zynqmp` PXE configuration file determines which linux image and rootfs a client is served.

## NFS Configuration

An NFS server (whose address and rootfs path are specified in `pxelinux.cfg/default-arm-zynqmp` `APPEND` options) should serve a
basic root filesystem.
Scripts are provided in `nfs` to help construct this filesystem.

**These scripts should be used with extreme caution**.

The rootfs creation scripts download an Ubuntu root filesyttem, chroot into it, and customize by installing packages.

**If the chroot fails, and commands intended for this filesystem are applied to the machine hosting the NFS, the results may be catastrophic**.

All scripts mast be run as root. You may wish to `sudo su` and then manually run the scripts line by line to verify they are operating correctly. These scripts are far from having bulletproof error handling.

 - `create-rootfs.sh` -- Download an Ubuntu rootfs and extract it. Use `create-rootfs.sh XX.YY.Z` to download Ubuntu version XX.YY.Z.
 - `enter-chroot.sh` -- Enter a pre-downloaded rootfs so that it may be customized. May be run with a `XX.YY.Z` version argument
 - `cleanup-chroot.sh` -- Attempt to cleanup mounts after a borked chroot. This may or may not work. You may have to reboot your computer. You may find you have destroyed your real filesystem. May be run with a `XX.YY.Z` version argument
 - `scripts/configure_rootfs.sh` - A script designed to be run within the chroot, which is copied to the rootfs on creation.

A typical construction process looks like:

 1. `sudo su`
 2. `./create-rootfs.sh 20.04.5`
 3. `./enter-chroot.sh 20.04.5`
 4. `configure_rootfs.sh` - Run within the chroot, takes a while!
 5. `exit` - leave the chroot


## Board Configuration

In addition to local network configuration, the board must be appropriately configured prior to trying to boot from the network.

Early-stage bootloaders must be stored locally on the FPGA board.
The following procedure writes them to flash.

  1. Place the provided `BOOT.BIN` and `boot.scr` files in a FAT32 partition
     on an micro SD card. In fact any bootable SD card should work, the file versions are mostly not important. Insert this card into the KRC4700.

  2. Connect to the KRC4700 BMC via UART (115200-baud, 8N1, port 1) and also the SoC debug console (also 115200-baud, 8N1, port 0).
     Configure the BMC to boot the board from SD card, then power cycle it. 
     On the SoC debug console, prepare to interrupt the boot process with a keypress.
     ```
     krm4:be
     krm4:0
     krm4:1
     ```

  3. Upon interrupting the boot process you will be dropped into a U-Boot shell. In this shell, run the following:
     ```
     sf probe 0 0 0 # Should show detection of a 128 MiB flash chip
     sf erase 0 1000000 # erase the first 16 MiB of flash
     dhcp # Acquire an IP address from the network
     tftpboot 0x80000 10.11.0.198:zynqmp/BOOT.BIN # Copy the BOOT.BIN binary over TFTP (replace with the IP address of your TFTP server, or leave blank if your DHCP server provides a tftp address)
     sf write 0x80000 0x0 $filesize # Write the copied binary to flash
     tftpboot 0x80000 10.11.0.198:zynqmp/boot.scr # Copy the boot.scr file
     sf write 0x80000 0x900000 $filesize # Write boot.scr to flash, in the offset expected by U-Boot, which is set at compile time.

  4. Configure the BMC to boot the board from flash, and power cycle it.
     ```
     krm4:b2
     krm4:0
     krm4:1
     ```
     You should see the board boot from flash, which will be evident from the attempt to read an environment from flash.
     ```
     U-Boot 2021.01 (Oct 12 2021 - 09:28:42 +0000)

     CPU:   ZynqMP
     Silicon: v3
     Board: Xilinx ZynqMP
     DRAM:  8 GiB
     usb dr_mode not found
     PMUFW:	v1.1
     EL Level:	EL2
     Chip ID:	zu47dr
     NAND:  0 MiB
     MMC:   mmc@ff160000: 0, mmc@ff170000: 1
     Loading Environment from SPIFlash... SF: Detected n25q512a with page size 512 Bytes, erase size 128 KiB, total 128 MiB
     *** Warning - bad CRC, using default environment
     ```

  5. Interrupt the boot process again, and set a MAC address for the board
     ```
     setenv ethaddr 02:00:47:00:00:01
     saveenv # Write ethaddr to flash
     ```

  6. Power down the board (via the BMC):
     ```
     krm4:0
     ```
     Remove the SD card. Then power up:
     ```
     krm4:1
     ```

  7. Assuming that your NFS / tftp setup is correct, you should see the board boot all the way to Ubuntu. You can log in via the serial console or SSH, and confirm that the board has an Ethernet interface with the MAC address set earlier.

  8. Once you are satisfied that booting from flash is functional, you can make this the default configuration in the BMC:
     ```
     krm4:f
     ```

  9 If you now hard power cycle the board (i.e., remove power rather than using the BMC controls) the board should once again boot to Ubuntu.

   

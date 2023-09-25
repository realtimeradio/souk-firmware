# souk-firmware
A repository for Simons Observatory UK FPGA firmware and control software.

## Software Versions:
- Ubuntu 18.04
- Xilinx Vivado System Edition 2021.2
- MATLAB/Simulink 2021a

## To open/modify/compile:

1. Clone this repository
2. Clone submodules:
```
git submodule update --init --recursive
```
3. Create a local environment specification file `firmware/startsg.local`.
4. From `firmware/`, run `startsg` (if your environment file is called `startsg.local`) or `startsg <my_local_environment_file.local>`.

## Repository Layout

 - `firmware/` -- Firmware source files and libraries
 - `software/` -- Libraries providing communication to FPGA hardware and firmware
 - `docs/` -- Documentation

# Hardware Setup

## KRM RFSoC

### Make SD card

1. Obtain a copy of the CASPER KRM-appropriate OS image, available hosted on Google Drive
2. Copy this image to SD card. Be careful, this command will wipe your SD card (or your hard disk if you enter the wrong device)
```
dd if=<casper_image_file.img> of=/dev/<your-SD-card-device>
```
for example: `dd if=casper.img of=/dev/sdb`
3. Insert the SD card into the KRM board.

### Configure the board to boot from SD card

0. Consult the KRM BMC guide for detailed instructions on interfacing with the KRM RFSoC SoM
1. Connect to the micro-USB-B port on the KRM board
2. Connect to the BMC controller serial interface at 115200 baud (which seems to be the "second" serial device). Eg, in Linux:
   ```
   picocom /dev/ttyUSB1 -b 115200
   ```
3. Set the board to boot from SD card:
   ```
   # List boot modes:
   krm4:b
   ```
   returns
   ```
   boot mode invalid option
   possible selections are:
   0 - JTAG
   1 - QSPI24
   2 - QSPI32
   5 - SD1
   6 - eMMC18
   7 - USB0
   8 - PJTAG0
   e - SD1-LS
   ```
   ```
   # Boot from SD card
   krm4:b5
   ```
   returns
   ```
   boot mode SD1
   ```
4. Save boot settings to flash
   ```
   krm4:f
   ```
5. Power cycle board

At this point, the board should boot to Linux from the SD card. You can watch the boot process via the "other" (`/dev /ttyUSB0`, for example) serial interface at 115200 baud.

### Connect to the board over Ethernet

By default, the provided image will configure the KRM board's Ethernet interface to have two IP addresses. One is obtained automatically via DHCP. The other is statically defined, and is `10.11.11.11/24`. Note that, at present, the provided OS image does not include a statically defined MAC address for the interface, so after a power cycles the board is likely to be allocated a new IP address.

1. Connect via SSH
```
ssh casper@10.11.11.11 # password is casper
```

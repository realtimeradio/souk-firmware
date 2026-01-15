#include <configs/xilinx_zynqmp.h>

#define CONFIG_BOOTCOMMAND "run bootcmd_pxe"

#undef BOOT_TARGET_DEVICES
#define BOOT_TARGET_DEVICES(func) \
        func(PXE, pxe, na) \
        func(MMC, mmc, 1) \
        func(MMC, mmc, 0) \
        func(USB, usb, 0) \
        func(DHCP, dhcp, na)

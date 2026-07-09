SUMMARY = "u-dma-buf (User space mappable DMA Buffer) kernel module"
DESCRIPTION = "Allocates physically contiguous DMA buffers from CMA and exposes \
them to user space as /dev/udmabufN devices that can be mmap'd cacheable, with \
sysfs handles for cache maintenance (sync_for_cpu / sync_for_device) and the \
buffer physical address (phys_addr). Buffers are declared as device tree nodes \
with compatible = \"ikwzm,u-dma-buf\". Not to be confused with the unrelated \
in-tree CONFIG_UDMABUF driver."
HOMEPAGE = "https://github.com/ikwzm/udmabuf"
SECTION = "kernel/modules"
LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=bebf0492502927bef0741aa04d1f35f5"

inherit module

# v5.5.0 -- tested upstream against linux 5.10 (this project's kernel)
SRCREV = "15bcde3cb960321e99983e227aeacc5807888333"
PV = "5.5.0+git${SRCPV}"
SRC_URI = "git://github.com/ikwzm/udmabuf.git;protocol=https;nobranch=1"

S = "${WORKDIR}/git"

# The kernel object is u-dma-buf.ko; the device tree nodes trigger udev
# autoload via the of:...ikwzm,u-dma-buf modalias, but load explicitly at
# boot as well so the /dev nodes exist even if the overlay probes early.
RPROVIDES_${PN} += "kernel-module-u-dma-buf"
KERNEL_MODULE_AUTOLOAD += "u-dma-buf"

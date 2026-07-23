FILESEXTRAPATHS_prepend := "${THISDIR}/${PN}:"

SRC_URI_append = " file://bsp.cfg"
KERNEL_FEATURES_append = " bsp.cfg"
SRC_URI += "file://user_2023-08-16-09-48-00.cfg \
            file://user_2023-08-17-15-38-00.cfg \
            file://user_2025-01-26-18-48-00.cfg \
            "


# u-dma-buf built into the kernel Image (we boot a custom rootfs, so the
# driver must travel inside image.ub rather than as a .ko in the rootfs)
SRC_URI += "file://0001-add-u-dma-buf-builtin.patch \
            file://u-dma-buf-builtin.cfg \
            "

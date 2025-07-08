FILESEXTRAPATHS_prepend := "${THISDIR}/${PN}:"

SRC_URI_append = " file://bsp.cfg"
KERNEL_FEATURES_append = " bsp.cfg"
SRC_URI += "file://user_2023-08-16-09-48-00.cfg \
            file://user_2023-08-17-15-38-00.cfg \
            file://user_2025-01-26-18-48-00.cfg \
            "


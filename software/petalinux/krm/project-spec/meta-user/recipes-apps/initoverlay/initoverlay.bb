#
# This file is the init-overlay recipe.
#

SUMMARY = "Simple initoverlay application"
SECTION = "PETALINUX/apps"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://initoverlay.sh \
           file://initshell.sh \
          "

S = "${WORKDIR}"

do_install() {
        install -d ${D}${bindir}
	    install -m 0755 ${S}/initoverlay.sh ${D}${bindir}
	    install -m 0755 ${S}/initshell.sh ${D}${bindir}
}

#PACKAGES += " ${PN}-base"
#FILES_${PN}-base = "/initoverlay.sh"
#FILES_${PN}-base = "/initshell.sh"

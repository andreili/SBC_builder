#!/bin/sh

OS_DIR_DEF="./root/"
DDIR=$(realpath "$1")
ROOT_DIR="$2"
KPATH="$3"

if [ -z "${DDIR}" ]
then
    echo "No root directory specified!"
    exit 1
fi
if [ -z "${ROOT_DIR}" ]
then
    echo "No main directory specified!"
    exit 1
fi
KV=$(make -C "${KPATH}/" --silent kernelversion)

# copy custom patches
mkdir -p ${DDIR}/etc/portage/patches
cp -R ${ROOT_DIR}/patch/os_custom/* ${DDIR}/etc/portage/patches/

mkdir -p ${DDIR}/usr/portage
mount --bind ${ROOT_DIR}/files/portage ${DDIR}/usr/portage
mkdir -p ${DDIR}/usr/src/linux-${KV}
mount --bind ${KPATH} ${DDIR}/usr/src/linux-${KV}

mount --bind /dev ${DDIR}/dev
mount --bind /dev/shm ${DDIR}/dev/shm
mount --bind /dev/pts ${DDIR}/dev/pts
mount --bind /sys ${DDIR}/sys
mount --bind /proc ${DDIR}/proc
mount -t tmpfs tmpfs ${DDIR}/var/tmp/
if [ -z "$4" ]
then
    chroot ${DDIR}/ /bin/bash
    ret=$?
else
    chroot ${DDIR}/ /bin/bash -c "${@:4}"
    ret=$?
fi
umount ${DDIR}/var/tmp
umount ${DDIR}/usr/src/linux-${KV}
umount ${DDIR}/proc
umount ${DDIR}/sys
umount ${DDIR}/dev/pts
umount ${DDIR}/dev/shm
umount ${DDIR}/dev
if [ -n "$1" ]
then
    umount ${DDIR}/usr/portage
fi
exit ${ret}

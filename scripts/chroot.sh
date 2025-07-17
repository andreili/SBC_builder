#!/bin/sh

OS_DIR_DEF="./root/"
DDIR=$(realpath "$1")
ROOT_DIR="$2"
KV=$(make -C ./build/common/kernel/ --silent kernelversion)

if [ -z "${DDIR}" ]
then
    echo "No directory specified!"
    exit 1
fi

mkdir -p ${DDIR}/usr/portage
mount --bind ${ROOT_DIR}/files/portage ${DDIR}/usr/portage
mkdir -p ${DDIR}/usr/src/linux-${KV}
mount --bind ${ROOT_DIR}/build/common/kernel ${DDIR}/usr/src/linux-${KV}

mount --bind /dev ${DDIR}/dev
mount --bind /dev/shm ${DDIR}/dev/shm
mount --bind /dev/pts ${DDIR}/dev/pts
mount --bind /sys ${DDIR}/sys
mount --bind /proc ${DDIR}/proc
mount -t tmpfs tmpfs ${DDIR}/var/tmp/
if [ -z "$3" ]
then
    chroot ${DDIR}/ /bin/bash
    ret=$?
else
    chroot ${DDIR}/ /bin/bash -c "${@:3}"
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

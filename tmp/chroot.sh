#!/bin/sh

do_chroot()
{
    if [ -z "$1" ]
    then
        DDIR=${OS_DIR_DEF}
    else
        DDIR=$(realpath "$1")
        mkdir -p ${DDIR}/var/db/pkg
        mkdir -p ${DDIR}/var/db/repos
        #mount --bind /media/1/H616/root/var/db/pkg ${DDIR}/var/db/pkg
        #cp -r ${OS_DIR_DEF}/var/db/pkg/* ${DDIR}/var/db/pkg
        mount --bind ${OS_DIR_DEF}/var/cache ${DDIR}/var/cache
        mount --bind ${OS_DIR_DEF}/usr/portage ${DDIR}/usr/portage
    fi
    mkdir -p ${DDIR}/usr/src/linux-5.16-CB1

    if [ -z "${DDIR}" ]
    then
        echo "No directory specified!"
        exit 1
    fi

    mount --bind /dev ${DDIR}/dev
    mount --bind /dev/shm ${DDIR}/dev/shm
    mount --bind /dev/pts ${DDIR}/dev/pts
    mount --bind /sys ${DDIR}/sys
    mount --bind /proc ${DDIR}/proc
    mount --bind /var/db/repos ${DDIR}/var/db/repos
    mount --bind ${DDIR}/../CB1-Kernel/kernel ${DDIR}/usr/src/linux-5.16-CB1
    mount -t tmpfs tmpfs ${DDIR}/var/tmp/
    cp -v "${ROOT_DIR}/scripts/qemu-aarch64" "${DDIR}/bin/"
    if [ -z "$2" ]
    then
        chroot ${DDIR}/ /bin/bash
    else
        chroot ${DDIR}/ /bin/bash -c "$2"
    fi
    umount ${DDIR}/var/tmp
    umount ${DDIR}/usr/src/linux-5.16-CB1
    umount ${DDIR}/var/db/repos
    umount ${DDIR}/proc
    umount ${DDIR}/sys
    umount ${DDIR}/dev/pts
    umount ${DDIR}/dev/shm
    umount ${DDIR}/dev
    if [ -n "$1" ]
    then
        umount ${DDIR}/usr/portage
        umount ${DDIR}/var/cache
        #umount ${DDIR}/var/db/pkg
        rm -rf ${DDIR}/var/db/pkg
    fi
}

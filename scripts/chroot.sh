#!/bin/sh

OS_DIR_DEF="./root/"

#do_chroot()
#{
    if [ -z "$1" ]
    then
        DDIR=${OS_DIR_DEF}
    else
        DDIR=$(realpath "$1")
        mount --bind ${OS_DIR_DEF}/usr/portage ${DDIR}/usr/portage
    fi
    mkdir -p ${DDIR}/usr/src/linux-6.14-rc7

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
    mount --bind /mnt/work/SBC/universal/build/btt_cb1/kernel_btt_cb1 ${DDIR}/usr/src/linux-6.14-rc7
    mount -t tmpfs tmpfs ${DDIR}/var/tmp/
    if [ -z "$2" ]
    then
        chroot ${DDIR}/ /bin/bash
    else
        chroot ${DDIR}/ /bin/bash -c "${@:2}"
    fi
    umount ${DDIR}/var/tmp
    umount ${DDIR}/usr/src/linux-6.14-rc7
    umount ${DDIR}/var/db/repos
    umount ${DDIR}/proc
    umount ${DDIR}/sys
    umount ${DDIR}/dev/pts
    umount ${DDIR}/dev/shm
    umount ${DDIR}/dev
    if [ -n "$1" ]
    then
        umount ${DDIR}/usr/portage
    fi
#}

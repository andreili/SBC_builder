#!/bin/sh
set -e          # Any subsequent(*) commands which fail will cause the shell script to exit immediately
set -o errtrace # trace ERR through - enabled
set -o errexit  ## set -e : exit the script if any statement returns a non-true return value - enabled

invalid_param()
{
    echo "Invalid parameters!"
    exit 1
}

if [ "$#" -lt 2 ]; then
    invalid_param
fi

ROOT_DIR="$(realpath $(dirname "$0"))"
GIT_BARE_ROOT="${ROOT_DIR}/git_bare"
DONE_MARKER=".done_marker"

source ${ROOT_DIR}/scripts/boards/${1}.sh
source ${ROOT_DIR}/scripts/host/binfmt.sh
source ${ROOT_DIR}/scripts/host/chroot.sh
source ${ROOT_DIR}/scripts/host/sources.sh

now=$(date +"%Y_%m_%d")
BACK_FN="back_os_${TARGET}_${now}.tar.xz"
SQH_FS="root_${TARGET}.sqh"
TMP_DIR="${ROOT_DIR}/tmp"
CFG_DIR="${ROOT_DIR}/cfg/${TARGET}"
OUT_DIR="${ROOT_DIR}/out/${TARGET}"
OS_DIR_DEF="${ROOT_DIR}/root"
CROSS_COMP=aarch64-unknown-linux-gnu-

MOD_1_NAME="klipper"
MOD_1_GIT="https://github.com/Klipper3d/klipper.git"
MOD_2_NAME="klipper_katapult"
MOD_2_GIT="https://github.com/Arksine/katapult.git"

INST_DEV=/dev/sdc

mkdir -p ${OUT_DIR}
mkdir -p ${CFG_DIR}

uboot_prepare()
{
    source_prepare git "${UBOOT_GIT_URL}" "${UBOOT_GIT_DIR}" "${UBOOT_DIR}" "${UBOOT_TAG}" "${UBOOT_PATCH_DIR}"
}

uboot_config()
{
    uboot_prepare
    if [ -f "${CFG_DIR}/${CFG_UBOOT}" ]
    then
        cp "${CFG_DIR}/${CFG_UBOOT}" "${UBOOT_DIR}/.config"
    fi
    cd ${UBOOT_DIR} &&
        make CROSS_COMPILE=${CROSS_COMP} ${UBOOT_ARGS} -j menuconfig &&
        cp "${UBOOT_DIR}/.config" "${CFG_DIR}/${CFG_UBOOT}"
}

uboot_build()
{
    uboot_extras_build
    uboot_prepare
    echo "Build U-Boot..."
    if [ -f "${CFG_DIR}/${CFG_UBOOT}" ]
    then
        cp "${CFG_DIR}/${CFG_UBOOT}" "${UBOOT_DIR}/.config"
    fi
    cd ${UBOOT_DIR} &&
        make CROSS_COMPILE=${CROSS_COMP} ${UBOOT_ARGS} clean &&
        make CROSS_COMPILE=${CROSS_COMP} ${UBOOT_ARGS} -j
    for str in ${UBOOT_FILES[@]}; do
        cp "${UBOOT_DIR}/${str}" "${OUT_DIR}/${str}"
    done
}

kernel_prepare()
{
    source_prepare git "${KERNEL_GIT_URL}" "${KERNEL_GIT_DIR}" "${KERNEL_DIR}" "${KERNEL_TAG}" "${KERNEL_PATCH_DIR}"
}

kernel_config()
{
    kernel_prepare
    if [ -f "${CFG_DIR}/${CFG_KERNEL}" ]
    then
        cp "${CFG_DIR}/${CFG_KERNEL}" "${KERNEL_SDIR}/.config"
    fi
    cd ${KERNEL_SDIR} &&
        make ${KERNEL_PARAMS} menuconfig &&
        cp "${KERNEL_SDIR}/.config" "${CFG_DIR}/${CFG_KERNEL}"
}

kernel_build()
{
    kernel_prepare
    if [ -f "${CFG_DIR}/${CFG_KERNEL}" ]
    then
        cp "${CFG_DIR}/${CFG_KERNEL}" "${KERNEL_SDIR}/.config"
    fi
    cd ${KERNEL_SDIR} &&
        make ${KERNEL_PARAMS} Image dtbs -j8 &&
        cp "${KERNEL_SDIR}/arch/${KARCH}/boot/Image" "${OUT_DIR}/Image" &&
        cp "${KERNEL_SDIR}/arch/${KARCH}/boot/dts/${KERNEL_DT_DIR}/${KERNEL_DT_NAME}.dtb" "${OUT_DIR}/${KERNEL_DT_NAME}.dtb"
}

sqh_root()
{
    if [ -e "${TMP_DIR}" ]
    then
        rm -rf "${TMP_DIR}"
    fi
    mkdir -p "${TMP_DIR}"
    chmod u+s ${ROOT_DIR}/root/usr/bin/Xorg
    cd ${ROOT_DIR}/root && "${ROOT_DIR}/scripts/back.sh" && cd ${ROOT_DIR}
    cd "${TMP_DIR}" && tar xf "${ROOT_DIR}/${BACK_FN}" && cd ${ROOT_DIR}
    #${ROOT_DIR}/root/chroot.sh ${TMP_DIR} 'emerge -ac --with-bdeps=n && exit'
    if [ -f "${OUT_DIR}/${SQH_FS}" ]
    then
        mv "${OUT_DIR}/${SQH_FS}" "${OUT_DIR}/${SQH_FS}".old
    fi
    mksquashfs "${TMP_DIR}" "${OUT_DIR}/${SQH_FS}" -comp xz
}

source_sync()
{
    prepare_uboot
    prepare_kernel
}

case "$2" in
    bundle)
        bundle
        ;;
    sync)
        source_sync
        ;;
    chroot)
        do_chroot $3
        ;;
    uboot_config)
        uboot_config
        ;;
    uboot)
        uboot_build
        ;;
    kernel_config)
        kernel_config
        ;;
    kernel)
        kernel_build
        ;;
    ramdisk)
        mkramdisk
        ;;
    sqh_root)
        sqh_root
        ;;
    cleanup)
        rm -rf "${GIT_BARE_ROOT}"
        ;;
    *)
        invalid_param
        ;;
esac

#diff -Naur linux-6.8.9-gentoo_or linux-6.8.9-gentoo --exclude=*.conf* --exclude=*generated* --exclude=*scripts* > 1.patch
#make -C /lib/modules/5.16.17/build M=/usr/src/w1-gpio-cl modules V=1
#install -m644 w1-gpio-cl.ko /lib/modules/5.16.17/kernel/drivers/w1/masters
#--depclean --with-bdeps=n

# RAM-disk image
#



#if [ -e "${TMP_DIR}" ]; then
#    rm -rf "${TMP_DIR}"
#fi
#for i in $(seq 1 20); do
#    MOD_NAME="MOD_${i}_NAME"
#    MOD_GIT="MOD_${i}_GIT"
#    if [ -n "${!MOD_NAME}" ]; then
#	mod_tmp="${TMP_DIR}/home/biqu/${!MOD_NAME}"
#	mkdir -p "${mod_tmp}"
#	git clone "${!MOD_GIT}" "${mod_tmp}" --depth=1
#	mksquashfs "${TMP_DIR}" "./${!MOD_NAME}.lzm" -comp xz -force-uid 1000 -force-gid 1000
#	rm -rf "${TMP_DIR}"
#    fi
#done


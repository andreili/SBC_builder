TARGET="btt_cb1"


CARCH="aarch64"
KARCH="arm64"

KERNEL_SDIR="${ROOT_DIR}/CB1-Kernel/kernel"
#KERNEL_BDIR="${ROOT_DIR}/CB1-Kernel_build"
KERNEL_PARAMS="ARCH=${KARCH} CROSS_COMPILE=${CROSS_COMP}"
KERNEL_DT_NAME="1"
KERNEL_DT_DIR="sunxi"

KERNEL_GIT_URL="https://github.com/torvalds/linux.git"
KERNEL_GIT_DIR="${GIT_BARE_ROOT}/kernel_mainline"
KERNEL_DIR=${ROOT_DIR}/build/vkernel
KERNEL_VERSION="v6.14-rc7"
KERNEL_TAG="tag:${KERNEL_VERSION}"
KERNEL_PATCH_DIR="kernel/sunxi64"

ATF_GIT_URL="https://github.com/ARM-software/arm-trusted-firmware"
ATF_GIT_DIR="${GIT_BARE_ROOT}/atf_mainline"
ATF_DIR=${ROOT_DIR}/build/${TARGET}_atf
ATF_VERSION="lts-v2.12.1"
ATF_TAG="tag:${ATF_VERSION}"
ATF_PLAT=sun50i_h616
ATF_PATCH_DIR="atf/sunxi64"

UBOOT_GIT_URL="https://github.com/u-boot/u-boot.git"
UBOOT_GIT_DIR="${GIT_BARE_ROOT}/uboot_mainline"
UBOOT_DIR=${ROOT_DIR}/build/${TARGET}_uboot
UBOOT_VERSION="v2024.01"
UBOOT_TAG="tag:${UBOOT_VERSION}"
UBOOT_PATCH_DIR="uboot/sunxi"
UBOOT_ARGS="BL31=${ATF_DIR}/build/${ATF_PLAT}/release/bl31.bin"
UBOOT_FILES=("u-boot-sunxi-with-spl.bin")

CFG_UBOOT="uboot_config"
CFG_KERNEL="kernel_${KERNEL_VERSION}_config"

uboot_extras_build()
{
    echo "[🔨] Build ATF"
    source_prepare git "${ATF_GIT_URL}" "${ATF_GIT_DIR}" "${ATF_DIR}" "${ATF_TAG}" "${ATF_PATCH_DIR}"
    cd ${ATF_DIR} &&
        make CROSS_COMPILE=${CROSS_COMP} PLAT=${ATF_PLAT} DEBUG=0 clean &&
        make CROSS_COMPILE=${CROSS_COMP} PLAT=${ATF_PLAT} DEBUG=0 bl31 -j
}

mkramdisk()
{
    mkimage -A arm -T ramdisk -C none -n uInitrd -d  ${ROOT_DIR}/root/boot/initramfs-5.16.17.img ${ROOT_DIR}/root/boot/uInitrd
}

write_uboot()
{
    drive=$1
    echo "[🔨] Write U-Boot"
    dd if=/dev/zero of="${drive}" bs=1M count=512
    for str in ${UBOOT_FILES[@]}; do
        dd if="${OUT_DIR}/${str}" of="${drive}" bs=1024 seek=8
    done
}

bundle()
{
    build_uboot
    build_kernel
    #system
    #ramdisk
    #mkramdisk
    #sqh_root
}

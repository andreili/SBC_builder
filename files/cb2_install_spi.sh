#!/bin/sh

echo "Copying u-boot to SPI flash..."
dd if=/mnt/cdrom/u-boot-rockchip-spi.bin of=/dev/mtdblock0 bs=4096

echo "Creating boot partition image..."
dd if=/dev/zero of=./boot.img bs=1M count=30 >/dev/null 2>&1
mkfs.ext2 ./boot.img >/dev/null 2>&1
mount -o loop ./boot.img /media >/dev/null 2>&1
cp -r /mnt/cdrom/extlinux /media/
cp /mnt/cdrom/Image /media/
cp -r /mnt/cdrom/dtb /media/
cp /mnt/cdrom/uInitrd /media/
cp -r /mnt/cdrom/modules /media/
umount /media
dd if=./boot.img of=/dev/mtdblock1

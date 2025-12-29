#!/bin/sh
set -e

TGTDEV=/dev/mmcblk0
SRCDEV=/dev/mmcblk1
sed -e 's/\s*\([\+0-9a-zA-Z]*\).*/\1/' << EOF | fdisk ${TGTDEV}
g
n

32768
+2G
n



w
EOF
#dd if=/mnt/cdrom/idbloader.img of=${TGTDEV} bs=512 seek=64
#dd if=/mnt/cdrom/u-boot.itb of=${TGTDEV} bs=512 seek=16384
dd if=/mnt/cdrom/u-boot-rockchip-spi.bin of=/dev/mtdblock0 bs=4096
mkfs.ext4 ${TGTDEV}p1
mkfs.ext4 ${TGTDEV}p2
mount ${TGTDEV}p1 /media
cp -R /mnt/cdrom/* /media/
umount /media
mount ${TGTDEV}p2 /media
touch /media/rw_part
umount /media

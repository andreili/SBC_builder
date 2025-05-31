#!/bin/sh

QEMU_AARCH64_FILTER="\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\xb7\x00:\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff"
if [ ! -f "/proc/sys/fs/binfmt_misc/qemu-${CARCH}" ]
then
    # only aarch64 is supported
    sudo sh -c "printf '%s\n' ':qemu-${CARCH}:M::${QEMU_AARCH64_FILTER}:/usr/bin/qemu-${CARCH}:' > /proc/sys/fs/binfmt_misc/register"
fi

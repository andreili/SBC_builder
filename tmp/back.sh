#!/bin/sh
now=$(date +"%Y_%m_%d")
BASEDIR=$(dirname "$0")
XZ_OPT="-9 --extreme --threads=0" tar -cvJpf ../back_os_${now}.tar.xz --exclude-from=${BASEDIR}/excl_root.lst .
#XZ_OPT="-9 --extreme --threads=0" tar -cvJpf ../back_home_${now}.tar.xz ./home
#XZ_OPT="-9 --extreme --threads=0" tar -cvJpf ../back_${now}.tar.xz .

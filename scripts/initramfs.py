import json, os, shutil
from pathlib import Path
from . import *

class Initramfs:
    def __init__(self):
        self.busybox = Sources("busybox", "https://git.busybox.net/busybox")
        self.busybox.init_source_path("common")
        self.busybox.set_git_params("@", "head")
        self.busybox_cfg = f"{ROOT_DIR}/cfg/busybox_config"
        self.eudev = Sources("eudev", "https://github.com/eudev-project/eudev.git")
        self.eudev.init_source_path("common")
        self.eudev.set_git_params("@", "head")
        self.e2fsp = Sources("e2fsp", "git://git.kernel.org/pub/scm/fs/ext2/e2fsprogs.git")
        self.e2fsp.init_source_path("common")
        self.e2fsp.set_git_params("@", "head")
        self.build_dir = f"{ROOT_DIR}/build/common"
        self.out_dir = f"{ROOT_DIR}/out"
        self.root_dir = f"{ROOT_DIR}/root/media/initramfs_tmp"

    def __prepare(self):
        self.busybox.sync()
        self.eudev.sync()
        self.e2fsp.sync()
        self.busybox.do_patch("common", "busybox")
        self.eudev.do_patch("common", "eudev")
        self.e2fsp.do_patch("common", "e2fsp")

    def __chrooted(self, obj, os, dir, cmd):
        os.bind(obj.work_dir, dir)
        os.custom(f"cd {dir} && {cmd}")
        os.unbind(dir)

    def __busybox(self, os):
        Logger.build(f"Compile busybox")
        dir = "/media/busybox"
        #self.__chrooted(self.busybox, os, dir, "make menuconfig")
        self.__chrooted(self.busybox, os, dir, "make -l10")
        shutil.copy(self.busybox.work_dir + "/busybox", f"{self.build_dir}/")

    def __eudev(self, os):
        Logger.build(f"Compile eudev")
        dir = "/media/udev"
        udev_bin = "src/udev/udevadm"
        cfg_cmd  = "--exec-prefix="
        cfg_cmd += " --bindir=/usr/bin --sbindir=/usr/sbin --includedir=/usr/include"
        cfg_cmd += " --libdir=/usr/lib --disable-shared --enable-static"
        cfg_cmd += " --enable-blkid --disable-introspection --disable-manpages"
        cfg_cmd += " --disable-selinux --disable-rule-generator"
        cfg_cmd += " --disable-hwdb --disable-kmod"
        #self.__chrooted(self.eudev, os, dir, f"./autogen.sh && ./configure {cfg_cmd}")
        self.__chrooted(self.eudev, os, dir, f"make -l10 && strip --strip-all {udev_bin}")
        shutil.copy(self.eudev.work_dir + f"/{udev_bin}", f"{self.build_dir}/")

    def __e2fsp(self, os):
        Logger.build(f"Compile e2fsprogs")
        dir = "/media/e2fsp"
        bin1 = "e2fsck/e2fsck"
        bin2 = "resize/resize2fs"
        cfg_cmd  = "--bindir=/bin"
        #--disable-fsck
        cfg_cmd += " --with-root-prefix=\"\" --disable-nls"
        cfg_cmd += " --enable-libblkid --enable-libuuid"
        cfg_cmd += " --disable-uuidd --disable-debugfs"
        cfg_cmd += " --disable-imager --enable-resizer"
        cfg_cmd += " --disable-defrag"
        cfg_cmd += " --enable-lto "
        self.__chrooted(self.e2fsp, os, dir, f"LDFLAGS='-static' ./configure {cfg_cmd}")
        self.__chrooted(self.e2fsp, os, dir, f"make -l10 && strip --strip-all {bin1} {bin2}")
        shutil.copy(self.e2fsp.work_dir + f"/{bin1}", f"{self.build_dir}/")
        shutil.copy(self.e2fsp.work_dir + f"/{bin2}", f"{self.build_dir}/")

    def __cpio(self):
        Logger.build(f"\tCreate init.cpio")
        f = open(f"{self.build_dir}/init.cpio", "wb")
        p = subprocess.Popen(["/usr/src/linux/usr/gen_init_cpio",
            f"{ROOT_DIR}/files/initramfs/initramfs.list"], stdout=f, cwd=ROOT_DIR)
        p.wait()
        f.close()

    def __compress_gzip(self):
        Logger.build(f"\tCompress GZIP")
        p = subprocess.Popen(["gzip", "-fk", "--best", f"{self.build_dir}/init.cpio"])
        p.wait()

    def __compress_lzma(self):
        Logger.build(f"\tCompress LZMA")
        p = subprocess.Popen(["lzma", "-fzk9e", f"{self.build_dir}/init.cpio"])
        p.wait()

    def __mkimage(self):
        Logger.build(f"\tImage")
        p = subprocess.Popen(["mkimage", "-A", "arm", "-T", "ramdisk", "-C",
            "none", "-n", "uInitrd", "-d", f"{self.build_dir}/init.cpio.lzma",
            f"{self.out_dir}/uInitrd"])
        p.wait()

    def __initrd(self):
        Logger.build(f"Make uInitrd")
        self.__cpio()
        self.__compress_gzip()
        self.__compress_lzma()
        self.__mkimage()

    def build(self, os):
        #self.__prepare()
        #self.__busybox(os)
        #self.__eudev(os)
        #self.__e2fsp(os)
        self.__initrd()

import json, os, shutil
from pathlib import Path
from . import *

def try_cfg(name):
    cfg_fn = f"{ROOT_DIR}" + "/%{cfg_dir}%/" + name
    cfg_fn = parse_variables(cfg_fn)
    cfg_path = Path(cfg_fn)
    if (cfg_path.is_file()):
        return cfg_fn
    else:
        return f"{ROOT_DIR}/cfg/{name}"

class Initramfs:
    def __init__(self):
        self.arch = parse_variables("%{ARCH}%")
        self.busybox = Sources("busybox", "https://git.busybox.net/busybox")
        self.busybox.init_source_path("", True)
        self.busybox.set_git_params("@", "head")
        self.busybox_cfg = try_cfg("busybox_config")
        self.eudev = Sources("eudev", "https://github.com/eudev-project/eudev.git")
        self.eudev.init_source_path("", True)
        self.eudev.set_git_params("@", "head")
        self.e2fsp = Sources("e2fsp", "git://git.kernel.org/pub/scm/fs/ext2/e2fsprogs.git")
        self.e2fsp.init_source_path("", True)
        self.e2fsp.set_git_params("@", "head")
        self.build_dir = f"{BUILD_DIR}/common_{self.arch}"
        self.files_dir = f"{self.build_dir}/initrd"
        self.out_dir = f"{OUT_DIR}"
        self.root_dir = f"{ROOT_DIR}/root_{self.arch}/media/initramfs_tmp"
        os.makedirs(self.files_dir, exist_ok=True)

    def __prepare(self):
        self.busybox.sync()
        self.eudev.sync()
        self.e2fsp.sync()
        self.busybox.do_patch("", "busybox")
        self.eudev.do_patch("", "eudev")
        self.e2fsp.do_patch("", "e2fsp")

    def __chrooted(self, obj, os, dir, cmd):
        os.bind(obj.work_dir, dir)
        os.custom(f"cd {dir} && {cmd}")
        os.unbind(dir)

    def __busybox(self, os):
        Logger.build(f"Compile busybox")
        dir = "/media/busybox"
        os.sudo(f"cp {self.busybox_cfg} {self.busybox.work_dir}/.config", self.busybox.work_dir, None, None, True)
        #self.__chrooted(self.busybox, os, dir, "make menuconfig")
        self.__chrooted(self.busybox, os, dir, "sed -i -r -e 's:[[:space:]]?-(Werror|Os|falign-(functions|jumps|loops|labels)=1|fomit-frame-pointer)\\>::g' Makefile.flags")
        self.__chrooted(self.busybox, os, dir, "sed -i -e 's:-static-libgcc::' Makefile.flags")
        self.__chrooted(self.busybox, os, dir, "make -j5")
        #self.__chrooted(self.busybox, os, dir, "make -j5")
        shutil.copy(self.busybox.work_dir + "/busybox", f"{self.files_dir}/")
        cfg_or = Path(self.busybox_cfg)
        if (cfg_or.is_file()):
            # backup old configuration
            shutil.copyfile(self.busybox_cfg, f"{self.busybox_cfg}.bak")
            shutil.copyfile(self.busybox.work_dir + "/.config", self.busybox_cfg)

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
        makefile = Path(f"{self.eudev.work_dir}/Makefile")
        if (not makefile.is_file()):
            self.__chrooted(self.eudev, os, dir, f"./autogen.sh && ./configure {cfg_cmd}")
        self.__chrooted(self.eudev, os, dir, f"make -j5 && strip --strip-all {udev_bin}")
        shutil.copy(self.eudev.work_dir + f"/{udev_bin}", f"{self.files_dir}/")

    def __e2fsp(self, os):
        Logger.build(f"Compile e2fsprogs")
        dir = "/media/e2fsp"
        bins = [ "e2fsck/e2fsck", "resize/resize2fs" ]#, "misc/mke2fs" ]
        cfg_cmd  = "--bindir=/bin"
        #--disable-fsck
        cfg_cmd += " --bindir=/bin --with-root-prefix=\"\" --disable-nls"
        cfg_cmd += " --disable-libblkid --disable-libuuid"
        cfg_cmd += " --disable-uuidd --disable-debugfs"
        cfg_cmd += " --disable-imager --enable-resizer"
        cfg_cmd += " --disable-defrag"
        #cfg_cmd += " --enable-lto "
        makefile = Path(f"{self.e2fsp.work_dir}/Makefile")
        if (not makefile.is_file()):
            self.__chrooted(self.e2fsp, os, dir, f"LDFLAGS='-static' ./configure {cfg_cmd}")
        self.__chrooted(self.e2fsp, os, dir, f"make -j5 && strip --strip-all {" ".join(bins)}")
        for bin in bins:
            shutil.copy(self.e2fsp.work_dir + f"/{bin}", f"{self.files_dir}/")
        #shutil.copy(self.e2fsp.work_dir + f"/misc/mke2fs.conf", f"{self.files_dir}/")

    def __cpio(self):
        Logger.build(f"\tCreate init.cpio")
        f = open(f"{ROOT_DIR}/files/initramfs/initramfs.list", "w")
        f.write("# directory structure\n")
        f.write("dir /sys           755 0 0\n")
        f.write("dir /dev           755 0 0\n")
        f.write("dir /proc          755 0 0\n")
        f.write("dir /run           755 0 0\n")
        f.write("dir /bin           755 0 0\n")
        f.write("dir /var           755 0 0\n")
        f.write("dir /lib           755 0 0\n")
        f.write("dir /mnt           755 0 0\n")
        f.write("dir /etc           755 0 0\n")
        f.write("dir /root          700 0 0\n")
        f.write("dir /tmp           755 0 0\n")
        f.write("dir /mnt/cdrom              755 0 0\n")
        f.write("dir /mnt/rw_part            755 0 0\n")
        f.write("dir /mnt/livecd             755 0 0\n")
        f.write("dir /mnt/overlay            755 0 0\n")
        f.write("dir /newroot                755 0 0\n")
        f.write("dir /newroot/mnt            755 0 0\n")
        f.write("dir /newroot/mnt/cdrom      755 0 0\n")
        f.write("dir /newroot/mnt/rw_part    755 0 0\n")
        f.write("dir /newroot/mnt/livecd     755 0 0\n")
        f.write("dir /newroot/mnt/overlay    755 0 0\n")
        f.write("#symlinks to easy script starts\n")
        f.write("slink /bin/[                            busybox                         755 0 0\n")
        f.write("slink /bin/ash                          busybox                         755 0 0\n")
        f.write("slink /bin/cat                          busybox                         755 0 0\n")
        f.write("slink /bin/chmod                        busybox                         755 0 0\n")
        f.write("slink /bin/cut                          busybox                         755 0 0\n")
        f.write("slink /bin/echo                         busybox                         755 0 0\n")
        f.write("slink /bin/mkdir                        busybox                         755 0 0\n")
        f.write("slink /bin/mknod                        busybox                         755 0 0\n")
        f.write("slink /bin/mount                        busybox                         755 0 0\n")
        f.write("slink /bin/sh                           busybox                         755 0 0\n")
        f.write("slink /bin/touch                        busybox                         755 0 0\n")
        f.write("slink /bin/uname                        busybox                         755 0 0\n")
        f.write("slink /bin/sed                          busybox                         755 0 0\n")
        f.write("slink /bin/ts                           busybox                         755 0 0\n")
        f.write("slink /lib64                            /lib                            755 0 0\n")
        f.write("slink /sbin                             /bin                            755 0 0\n")
        f.write("slink /etc/mtab                         /proc/self/mounts               777 0 0\n")
        f.write("slink /dev/stderr                       /proc/self/fd/2                 777 0 0\n")
        f.write("slink /dev/stdin                        /proc/self/fd/0                 777 0 0\n")
        f.write("slink /dev/std/out                      /proc/self/fd/1                 777 0 0\n")
        f.write(f"file /bin/busybox            build/common_{self.arch}/initrd/busybox            755 0 0\n")
        f.write(f"file /bin/udevadm            build/common_{self.arch}/initrd/udevadm            755 0 0\n")
        f.write(f"file /bin/e2fsck             build/common_{self.arch}/initrd/e2fsck             755 0 0\n")
        f.write(f"file /bin/resize2fs          build/common_{self.arch}/initrd/resize2fs          755 0 0\n")
        #f.write(f"file /etc/mke2fs.conf        build/common_{self.arch}/initrd/mke2fs.conf        755 0 0\n")
        #f.write(f"file /bin/mke2fs2            build/common_{self.arch}/initrd/mke2fs             755 0 0\n")
        f.write("file /etc/init.def           files/initramfs/init.def        755 0 0\n")
        f.write("file /etc/init.script        files/initramfs/init.script     755 0 0\n")
        f.write("file /init                   files/initramfs/init            755 0 0\n")
        f.write("file /shutdown               files/initramfs/shutdown        755 0 0\n")
        f.write("file /etc/fstab              files/initramfs/fstab           755 0 0\n")
        f.write("file /etc/group              files/initramfs/group           755 0 0\n")
        #f.write("file /etc/ld.so.conf         files/initramfs/ld.so.conf      755 0 0\n")
        f.write("file /etc/passwd             files/initramfs/passwd          755 0 0\n")
        f.write("file /etc/shadow             files/initramfs/shadow          755 0 0\n")
        f.close()
        f = open(f"{self.files_dir}/init.cpio", "wb")
        p = subprocess.Popen(["/usr/src/linux/usr/gen_init_cpio",
            f"{ROOT_DIR}/files/initramfs/initramfs.list"], stdout=f, cwd=ROOT_DIR)
        p.wait()
        f.close()

    def __compress_gzip(self):
        Logger.build(f"\tCompress GZIP")
        p = subprocess.Popen(["gzip", "-fk", "--best", f"{self.files_dir}/init.cpio"])
        p.wait()

    def __compress_lzma(self):
        Logger.build(f"\tCompress LZMA")
        p = subprocess.Popen(["lzma", "-fzk9e", f"{self.files_dir}/init.cpio"])
        p.wait()

    def __mkimage(self):
        Logger.build(f"\tImage")
        p = subprocess.Popen(["mkimage", "-A", "arm", "-T", "ramdisk", "-C",
            "none", "-n", "uInitrd", "-d", f"{self.files_dir}/init.cpio.lzma",
            f"{self.out_dir}/uInitrd_{self.arch}"])
        p.wait()

    def __mkshutdown(self):
        Logger.build(f"\tShutdown image")
        dir_tmp = f"{self.build_dir}/shutdown_img_{self.arch}"
        dir_ch = Path(dir_tmp)
        if (dir_ch.is_dir()):
            p = subprocess.Popen(["sudo", "rm", "-rf", dir_tmp])
            p.wait()
        fn = f"shutdown_{self.arch}.tar.xz"
        p = subprocess.Popen(["mkdir", "-p", dir_tmp])
        p.wait()
        p = subprocess.Popen(f"sudo cat {self.files_dir}/init.cpio | sudo cpio -idm && sudo tar cJpf ../{fn} . && cp ../{fn} {self.out_dir}/{fn}",
            shell=True, cwd=dir_tmp)
        p.wait()
        p = subprocess.Popen(["sudo", "cp", f"{self.out_dir}/{fn}", f"{ROOT_DIR}/root_{self.arch}/usr/shutdown.tar.xz"])
        p.wait()
        p = subprocess.Popen(["sudo", "rm", "-rf", dir_tmp])
        p.wait()

    def __initrd(self):
        Logger.build(f"Make uInitrd")
        self.__cpio()
        self.__compress_gzip()
        self.__compress_lzma()
        self.__mkimage()
        self.__mkshutdown()

    def build(self, os):
        self.__prepare()
        self.__busybox(os)
        self.__eudev(os)
        self.__e2fsp(os)
        self.__initrd()

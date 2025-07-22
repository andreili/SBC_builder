import subprocess, os, sys, datetime, getpass, shutil, requests, stat, re
from pathlib import Path
if __name__ != '__main__':
    from . import *

units = { "B": 1, "K": 2**10, "M": 2**20, "G": 2**30 }
MARKER_ROOTFS_READY = "rootfs_ready"

class Partition(object):
    pass

class OS:
    def __init__(self):
        self.root_dir = f"{ROOT_DIR}/root"
        self.mount_dir = f"{ROOT_DIR}/build/mnt_tmp"
        self.actions = [
            [ "chroot",    self.chroot      ],
            [ "sync",      self.sync_repo   ],
            [ "update",    self.update_all  ],
            [ "reinstall", self.rebuild_all ],
            [ "pack",      self.pack        ],
            [ "sqh",       self.sqh         ]
        ]

    def __relaunch_as_sudo(self):
        if (os.geteuid() == 0):
            return
        Logger.os("Relaunch scripts with 'sudo'...")
        args = ["./build.py"]
        self.__sudo(sys.argv)
        Logger.ok_exit("Finished running from 'sudo'")

    def load_info(self):
        with open(f"{ROOT_DIR}/config/os_{self.arch}.json") as json_data:
            js_data = json.load(json_data)
            json_data.close()
            self.st3_info = js_data["stage3_info"]
            self.st3_prepare = js_data["prepare"]
            self.st3_update = js_data["update"]
            self.st3_install = js_data["install"]
            self.finalize = js_data["finalize"]
            self.board.add_vars(js_data["variables"])
            self.board.add_var("ROOT_FS", self.root_dir)

    def actions_list(self):
        lst = []
        for act in self.actions:
            lst.append(act[0])
        return lst

    def __get_stage3_url(self):
        url_descr = self.st3_info["server_dir"] + self.st3_info["info_file"]
        r = requests.get(url_descr, stream=True)
        descr = r.content.decode('utf-8').splitlines()
        stage3_fn = ""
        for d in descr:
            if (d.startswith("stage3")):
                stage3_fn = d.split()[0]
        arch_url = self.st3_info["server_dir"] + stage3_fn
        return [arch_url, stage3_fn]

    def __stage3_apply(self, info, text):
        self.__tmp_clean(self.root_dir)
        [url,fn] = self.__get_stage3_url()
        Logger.os(f"Download Stage3 archive '{fn}'...")
        temp_dir = f"{ROOT_DIR}/build/tmp"
        self.__tmp_clean(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        r = requests.get(url, stream=True)
        arch_fn = f"{temp_dir}/{fn}"
        with open(arch_fn, 'wb') as f:
            total_length = int(r.headers.get('content-length'))
            for chunk in r.iter_content(chunk_size=1024):
                f.write(chunk)
        Logger.os(f"Extract Stage3 archive...")
        os.makedirs(self.root_dir, exist_ok=True)
        self.__extract_tar(arch_fn, self.root_dir)
        self.__tmp_clean(temp_dir)

    def __stage3_steps(self, info, text, dir=""):
        if (dir == ""):
            dir = self.root_dir
        Logger.os(text)
        self.__sudo(["cp", "/etc/resolv.conf", f"{self.root_dir}/etc/resolv.conf"])
        for step in info["steps"]:
            if ("file" in step):
                is_append = "-a" if step["append"] else ""
                lines = "\n".join(step["lines"])
                path = step["file"]
                directory = Path(path).parent
                cmd  = f"mkdir -p {self.root_dir}{directory} && echo '{lines}'"
                cmd += f" | sudo tee {is_append} {self.root_dir}{path} > /dev/null"
                Logger.os(f"\tCreate file {path}...")
                self.__sudo(cmd, shell=True, cwd=dir)
            if ("chroot" in step):
                cmd = self.board.parse_variables(step["chroot"])
                self.__chroot(cmd, dir=dir)
            if ("action" in step):
                action = step["action"]
                for act in self.actions:
                    if (act[0] == action):
                        act[1]()
                        break
            if ("soft_inst" in step):
                sw_list = " ".join(step["soft_inst"])
                oneshot = "1" if step["oneshot"] else ""
                self.__chroot(f"emerge -avb{oneshot} {sw_list} -j2", dir=dir)
            if ("soft_clean" in step):
                clean_type = step["soft_clean"]
                if (clean_type == "default"):
                    self.__chroot(f"emerge -ac", dir=dir)
                if (clean_type == "bdeps"):
                    self.__chroot(f"emerge --depclean --with-bdeps=n --exclude sys-devel/gcc && ldconfig", dir=dir)
            if ("sudo" in step):
                cmd = self.board.parse_variables(step["sudo"])
                Logger.os(f"\tSudo command {cmd}...")
                self.__sudo(cmd, cwd=dir, shell=True)
            if ("copy" in step):
                path_from = self.board.parse_variables(step["copy"][0])
                path_to = self.board.parse_variables(step["copy"][1])
                if (Path(path_from).is_dir()):
                    self.__sudo(f"cp -r {path_from} {path_to}", cwd=dir, shell=True)
                else:
                    self.__sudo(f"cp {path_from} {path_to}", cwd=dir, shell=True)

    def check_rootfs(self):
        if marker_check(MARKER_ROOTFS_READY):
            return
        self.__relaunch_as_sudo()
        stages = [
            [self.st3_info,     self.__stage3_apply, ""                    ],
            [self.st3_prepare,  self.__stage3_steps, "Basic preparation..."],
            [self.st3_update,   self.__stage3_steps, "System update..."    ],
            [self.st3_install,  self.__stage3_steps, "Software installation..."],
        ]
        for st in stages:
            if (not marker_check(st[0]["marker"])):
                st[1](st[0], st[2])
                marker_set(st[0]["marker"])
        marker_set(MARKER_ROOTFS_READY)

    def set_board(self, board):
        self.board = board
        self.board.add_var("ROOTFS", self.root_dir)
        self.arch = board.parse_variables("%{ARCH}%")

    def __sudo(self, args, cwd=None, env=None, stdout=None, shell=None):
        if (os.geteuid() != 0):
            if isinstance(args, str):
                args = self.board.parse_variables("sudo " + args)
                err_n = args
            else:
                args.insert(0, "sudo")
                err_n = args[1]
        p = subprocess.Popen(args, cwd=cwd, env=env, stdout=stdout, stderr=stdout, shell=shell)
        p.wait()
        if (p.returncode != 0):
            Logger.error(f"Command '{err_n}' finished with error code {p.returncode}!")

    def __prepare(self):
        qemu_f = Path(f"/proc/sys/fs/binfmt_misc/qemu-{self.arch}")
        if (not qemu_f.is_file()):
            self.__sudo(["python", os.path.abspath(__file__), self.arch])
        self.__sudo(["cp", f"{ROOT_DIR}/files/qemu/qemu-{self.arch}", f"{self.root_dir}/bin/"])

    def __chroot(self, command, dir="", stdout=None):
        self.__prepare()
        if (dir == ""):
            dir = self.root_dir
        Logger.os(f"Start chroot'ed command '{command}' into '{dir}'")
        self.__sudo(["bash", f"{ROOT_DIR}/scripts/chroot.sh", dir, ROOT_DIR, command], stdout=stdout)

    def umount_safe(self):
        self.__sudo(["umount", "--all-targets", "--recursive", self.root_dir])

    def bind(self, dir, path):
        self.__sudo(["mkdir", "-p", f"{self.root_dir}/{path}"])
        self.__sudo(["mount", "--bind", dir, f"{self.root_dir}/{path}"])

    def unbind(self, path):
        self.__sudo(["umount", f"{self.root_dir}/{path}"])

    def chroot(self):
        self.__chroot("")

    def chroot_ext(self, command, dir):
        self.__chroot(command, dir)

    def sync_repo(self):
        self.__chroot("eix-sync -v")

    def update_all(self):
        self.__chroot("emerge -avuDN1b world -j2 && emerge -ac")
        self.__chroot("ldconfig")

    def rebuild_all(self):
        self.__chroot("emerge -av1be world -j2")
        self.__chroot("ldconfig")

    def custom(self, command):
        self.__chroot(command)

    def __do_archive(self, excl_list, name, dir):
        Logger.os(f"Create '{name}' archive...")
        my_env = os.environ.copy()
        my_env["XZ_OPT"] = "-9 --extreme --threads=0"
        date = datetime.datetime.today().strftime('%Y_%m_%d')
        arch_path = self.board.parse_variables("%{out_sh}%/back_" + name + "_" + date + ".tar.xz")
        self.__sudo(["tar", "-cJpf", arch_path,
            f"--exclude-from={ROOT_DIR}/files/backups/{excl_list}.lst", "."],
            cwd=dir, env=my_env)
        return arch_path

    def pack(self):
        return self.__do_archive("excl_min", "FULL", self.root_dir)

    def  __tmp_clean(self, path):
        Logger.os(f"Clean directory '{path}'...")
        t_dir = Path(path)
        if (t_dir.is_dir()):
            self.__sudo(["rm", "-rf", path])

    def __extract_tar(self, arch_fn, to_path):
        Logger.os("Extract to temporary directory...")
        os.makedirs(to_path, exist_ok=True)
        my_env = os.environ.copy()
        my_env["XZ_OPT"] = "-9 --extreme --threads=0"
        self.__sudo(["tar", "xf", arch_fn], cwd=to_path, env=my_env)

    def __make_sqh(self, root_path, to_file):
        Logger.os("Create squashed archive...")
        t_file = Path(to_file)
        if (t_file.is_file()):
            shutil.move(to_file, f"{to_file}.bak")
        self.__sudo(["mksquashfs", root_path, to_file, "-comp", "xz", "-xattrs-exclude", "^system.nfs"])
        user = getpass.getuser()
        self.__sudo(["chown", user + ":" + user, to_file])

    def __finalize(self, dir):
        self.__stage3_steps(self.finalize, "Finalize system installation...", dir=dir)

    def sqh(self):
        self.__relaunch_as_sudo()
        date = datetime.datetime.today().strftime('%Y_%m_%d')
        temp_dir = f"{ROOT_DIR}/build/tmp"
        # pack full system via tar
        arch_full_path = self.pack()
        self.__tmp_clean(temp_dir)
        self.__extract_tar(arch_full_path, temp_dir)
        # prepare system, remove unnecessary packages
        self.__finalize(temp_dir)
        self.__do_archive("excl_min", "FULL_min_bdeps", temp_dir)
        # pack a minimal archive
        arch_path = self.__do_archive("excl", "OS", temp_dir)
        # remove temp directory
        self.__tmp_clean(temp_dir)
        self.__extract_tar(arch_path, temp_dir)
        sqh_fn = f"{ROOT_DIR}/out/root_{date}.sqh"
        self.__make_sqh(temp_dir, sqh_fn)
        os.symlink(sqh_fn, f"{ROOT_DIR}/out/root.sqh.tmp")
        os.rename(f"{ROOT_DIR}/out/root.sqh.tmp", f"{ROOT_DIR}/out/root.sqh")
        self.__tmp_clean(temp_dir)

    def action(self, action):
        for act in self.actions:
            if (act[0] == action):
                act[1]()
                break

    def __do_cmd(self, args, cwd=None, env=None, stdin=None, stdout=None):
        if (stdin != None):
            p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=stdout, text=True)
        else:
            p = subprocess.Popen(args, cwd=cwd, env=env, stdout=stdout, stderr=stdout)
        if (stdin != None):
            p.communicate(input=stdin)
        if (p.wait() != 0):
            Logger.error(f"Command '{args[0]}' finished with error code!")

    def __part_prepare(self):
        self.block_size = self.__parse_size(self.board.installs["block_size"])
        self.partitions = []
        for part in self.board.installs["partitions"]:
            part_obj = Partition()
            part_obj.name = part["name"]
            if "first_sector" in part:
                part_obj.first_sector = int(part["first_sector"])
            else:
                part_obj.first_sector = -1
            part_obj.size = self.__parse_size(part["size"])
            part_obj.size_blk = int(part_obj.size / self.block_size) - 1
            self.partitions.append(part_obj)

    def __create_img_file(self, path, size):
        Logger.install("\tCreate image file...")
        img_f = Path(path)
        if (img_f.is_file()):
            shutil.rmtree(path, ignore_errors=True)
        blk_size = 1024*1024
        blk_count = int(size / blk_size)
        self.__do_cmd(["dd", "if=/dev/zero", f"of={path}", f"bs={blk_size}",
            f"count={blk_count}"], stdout=subprocess.DEVNULL)

    def __parse_size(self, size):
        size = size.upper()
        if not re.match(r' ', size):
            size = re.sub(r'([BKMGT])', r' \1', size)
        number, unit = [string.strip() for string in size.split()]
        return int(float(number)*units[unit])

    def __get_img_size(self):
        offset_fix = 1024 * 1024 * 1
        img_sz = offset_fix
        for part in self.partitions:
            if part.first_sector > -1:
                img_sz = offset_fix + (part.first_sector * self.block_size)
            img_sz += part.size
        return img_sz

    def __create_parts(self, img_or_dev, from_sudo):
        Logger.install("\tCreate partitions table...")
        args = ""
        part_type = "p\n"
        if (self.board.installs["type"] == "mbr"):
            args += "o\n"
        elif (self.board.installs["type"] == "gpt"):
            args += "g\n"
            part_type = ""
        offset = 0
        for part in self.partitions:
            args += f"n\n{part_type}\n"
            if part.first_sector > -1:
                offset = part.first_sector
            args += f"{offset}\n"
            args += f"+{part.size_blk}\n"
            offset += part.size_blk + 1
        args += "w\nq\n"
        cmd = []
        if (os.geteuid() != 0) and (from_sudo):
            cmd.append("sudo")
        cmd.append("fdisk")
        cmd.append(img_or_dev)
        self.__do_cmd(cmd, stdin=args, stdout=subprocess.DEVNULL)

    def __prepare_img(self, out_dir):
        Logger.install("\tImage. Prepare and mount it...")
        img_fn = f"{out_dir}/all.img"
        img_sz = self.__get_img_size()
        self.__create_img_file(img_fn, img_sz)
        return img_fn

    def __mount_loop(self, img_or_blk, idx):
        offset = 0
        i = 0
        for part in self.partitions:
            if part.first_sector > -1:
                offset = part.first_sector * self.block_size
            part_size = part.size
            if (part_size > (90 * 1024 * 1024)) and (i == idx):
                # required partition
                #print(f"\tIdx:{i} Size:{part_size}")
                self.__sudo(["losetup", "-o", str(offset), "--sizelimit",
                    str(part_size), "/dev/loop0", img_or_blk],
                    cwd=ROOT_DIR)#, stdout=subprocess.DEVNULL)
                return True
            i += 1
            offset += part_size
        return False

    def __umount_loop(self):
        self.__sudo(["losetup", "-d", "/dev/loop0"], stdout=subprocess.DEVNULL)

    def __mount_dev(self, dev, dir):
        self.__sudo(["mount", dev, dir], stdout=subprocess.DEVNULL)

    def __umount_dev(self, dir):
        self.__sudo(["umount", dir], stdout=subprocess.DEVNULL)

    def __create_fs(self, img_or_blk, is_blk):
        Logger.install("\tCreate filesystems...")
        for i in range(len(self.partitions)):
            if (not is_blk) and (self.__mount_loop(img_or_blk, i)):
                self.__sudo(["mkfs.ext2", "/dev/loop0"], stdout=subprocess.DEVNULL)
                self.__umount_loop()
            if is_blk:
                idx = i + 1
                self.__sudo(["mkfs.ext2", "-F", f"{img_or_blk}{idx}"], stdout=subprocess.DEVNULL)

    def __copy_file(self, src, dst):
        Logger.install(f"\tCopy {src}")
        self.__sudo(["mkdir", "-p", dst], stdout=subprocess.DEVNULL)
        self.__sudo(["cp", src, dst], stdout=subprocess.DEVNULL)

    def __dd_bin(self, src, block_size, offset):
        blk_sz = self.__parse_size(block_size)
        Logger.install(f"\tDD {src} (+{offset}:{blk_sz})")
        self.__sudo(["dd", f"if={src}", f"of={self.out_path}",
            f"bs={blk_sz}", f"seek={offset}", "conv=notrunc"], stdout=subprocess.DEVNULL)

    def __install_boot(self, out_dir):
        extl_dir = f"{out_dir}/extlinux"
        extl_fn  = f"{extl_dir}/extlinux.conf"
        dtb_file = self.board.parse_variables("%{DTB_FILE}%")
        cmd  = f"mkdir -p {extl_dir} && touch {out_dir}/livecd && "
        cmd += f"echo 'menu title Boot Options.\n\ntimeout 20\ndefault Kernel_def\n\n"
        cmd += f"label Kernel_def\n\tkernel /Image\n\tfdtdir /dtb/\n\tdevicetree /dtb/{dtb_file}\n\tinitrd /uInitrd\n' >> {extl_fn}"
        self.__sudo(["sh", "-c", f"{cmd}"], stdout=subprocess.DEVNULL)
        for target in self.board.targets:
            target.install_files(out_dir, self.board.out_dir, "boot", self.__copy_file, self.__dd_bin)
        self.__copy_file(f"{self.board.out_sh}/uInitrd", f"{out_dir}/")
        Logger.install(f"\tCopy root.sqh")
        self.__sudo(["cp", "-H", f"{self.board.out_sh}/root.sqh", f"{out_dir}/"])

    def __install_rw(self, out_dir):
        self.__sudo(["touch", f"{out_dir}/rw_part"], stdout=subprocess.DEVNULL)
        self.__sudo(["mkdir", "-p", f"{out_dir}/.upper"], stdout=subprocess.DEVNULL)
        self.__sudo(["mkdir", "-p", f"{out_dir}/.work"], stdout=subprocess.DEVNULL)

    def __do_boot(self, img_or_blk, is_blk):
        Logger.install("\tCreate boot files...")
        i = 0
        os.makedirs(self.mount_dir, exist_ok=True)
        for part in self.partitions:
            if is_blk:
                idx = i + 1
                self.__mount_dev(f"{img_or_blk}{idx}", self.mount_dir)
            else:
                self.__mount_loop(img_or_blk, i)
                self.__mount_dev("/dev/loop0", self.mount_dir)
            if (part.name == "boot"):
                self.__install_boot(self.mount_dir)
            if (part.name == "rw"):
                self.__install_rw(self.mount_dir)
            self.__umount_dev(self.mount_dir)
            if not is_blk:
                self.__umount_loop()
            i += 1

    def install(self, dir_or_dev):
        self.__relaunch_as_sudo()
        Logger.install(f"Install to '{dir_or_dev}'")
        is_blk = False
        dir_ch = Path(dir_or_dev)
        self.__part_prepare()
        if (not dir_ch.is_dir()) and (stat.S_ISBLK(os.stat(dir_or_dev).st_mode)):
            is_blk = True
            Logger.install(f"\tBlock device, need to use a sudo.")
        if (self.board.installs["target"] == "image"):
            if (not is_blk):
                dir_or_dev = self.__prepare_img(dir_or_dev)
        else:
            Logger.error("Unsupported instalation type!")
        self.out_path = dir_or_dev
        self.__create_parts(dir_or_dev, is_blk)
        self.__create_fs(dir_or_dev, is_blk)
        self.__do_boot(dir_or_dev, is_blk)
        Logger.install(f"Finished!")

if __name__ == '__main__':
    f = open("/proc/sys/fs/binfmt_misc/register","wb")
    if (len(sys.argv) < 2) or (sys.argv[1] == "aarch64"):
        name = "aarch64"
        interp = f"/usr/bin/qemu-{name}"
        magic  = b"\\x7fELF\\x02\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\xb7\\x00"
        mask   = b"\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\x00\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xfe\\xff\\xff\\xff"
    else:
        print("Invalid arguments!")
        exit(1)
    _REGISTER_FORMAT = b":qemu-%(name)s:M::%(magic)s:%(mask)s:%(interp)s:%(flags)s"
    s = _REGISTER_FORMAT % {
        b"name": name.encode("utf-8"),
        b"magic": magic,
        b"mask": mask,
        b"interp": interp.encode("utf-8"),
        b"flags": b"",
    }
    f.write(s)

import subprocess, os, sys, datetime, getpass, shutil
from pathlib import Path
if __name__ != '__main__':
    from . import *

class OS:
    def __init__(self):
        self.root_dir = f"{ROOT_DIR}/root"
        self.actions = [
            [ "chroot",    self.chroot      ],
            [ "sync",      self.sync_repo   ],
            [ "update",    self.update_all  ],
            [ "reinstall", self.rebuild_all ],
            [ "pack",      self.pack        ],
            [ "sqh",       self.sqh         ]
        ]

    def actions_list(self):
        lst = []
        for act in self.actions:
            lst.append(act[0])
        return lst

    def set_board(self, board):
        self.board = board
        self.arch = board.parse_variables("%{ARCH}%")

    def __sudo(self, args, cwd=None, env=None):
        args.insert(0, "sudo")
        p = subprocess.Popen(args, cwd=cwd, env=env)
        if (p.wait() != 0):
            Logger.error(f"Command '{args[1]}' finished with error code!")

    def __prepare(self):
        qemu_f = Path(f"/proc/sys/fs/binfmt_misc/qemu-{self.arch}")
        if (not qemu_f.is_file()):
            self.__sudo(["python", os.path.abspath(__file__), self.arch])
        self.__sudo(["cp", f"{ROOT_DIR}/files/qemu/qemu-{self.arch}", f"{self.root_dir}/bin/"])

    def __chroot(self, command, dir=""):
        self.__prepare()
        if (dir == ""):
            dir = self.root_dir
        Logger.os(f"Start chroot'ed command '{command}' into '{dir}'")
        self.__sudo(["bash", f"{ROOT_DIR}/scripts/chroot.sh", dir, command])

    def umount_safe(self):
        self.__sudo(["umount", "--all-targets", "--recursive", self.root_dir])

    def bind(self, dir, path):
        self.__sudo(["mkdir", "-p", f"{self.root_dir}/{path}"])
        self.__sudo(["mount", "--bind", dir, f"{self.root_dir}/{path}"])

    def unbind(self, path):
        self.__sudo(["umount", f"{self.root_dir}/{path}"])

    def chroot(self):
        self.__chroot("")

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

    def __fix_xorg(self):
        Logger.os("Fix Xorg permissions")
        self.__sudo(["chmod", "u+s", f"{self.root_dir}/usr/bin/Xorg"])

    def  __tmp_clean(self, path):
        Logger.os("Clean temporary directory...")
        t_dir = Path(path)
        if (t_dir.is_dir()):
            self.__sudo(["rm", "-rf", path])

    def __extract_tar(self, arch_fn, to_path):
        Logger.os("Extract to temporary directory...")
        os.makedirs(to_path, exist_ok=True)
        self.__sudo(["tar", "xf", arch_fn], cwd=to_path)

    def __make_sqh(self, root_path, to_file):
        Logger.os("Create squashed archive...")
        t_file = Path(to_file)
        if (t_file.is_file()):
            shutil.move(to_file, f"{to_file}.bak")
        self.__sudo(["mksquashfs", root_path, to_file, "-comp", "xz", "-xattrs-exclude", "^system.nfs"])
        user = getpass.getuser()
        self.__sudo(["chown", user + ":" + user, to_file])

    def __remove_bdeps(self, temp_dir):
        # pack full system via tar
        arch_full_path = self.pack()
        self.__extract_tar(arch_full_path, temp_dir)
        # remove unneccessarry packages
        list_to_rm  = " virtual/perl-JSON-PP virtual/perl-podlators"
        list_to_rm += " virtual/perl-Getopt-Long virtual/perl-Parse-CPAN-Meta"
        list_to_rm += " virtual/perl-ExtUtils-CBuilder virtual/perl-ExtUtils-ParseXS"
        list_to_rm += " virtual/perl-Unicode-Collate virtual/perl-Text-ParseWords"
        list_to_rm += " virtual/perl-ExtUtils-MakeMaker virtual/perl-Module-Metadata"
        list_to_rm += " virtual/perl-version virtual/perl-CPAN-Meta"
        list_to_rm += " virtual/perl-File-Spec perl-core/Getopt-Long"
        list_to_rm += " dev-perl/Module-Build"
        list_to_rm += " x11-base/xcb-proto x11-libs/xtrans"
        list_to_rm += " app-alternatives/ninja app-eselect/eselect-rust"
        list_to_rm += " dev-libs/vala-common dev-util/glib-utils"
        list_to_rm += " dev-util/gdbus-codegen media-fonts/font-util"
        list_to_rm += " dev-libs/libxslt"
        list_to_rm += " dev-build/gtk-doc-am sys-apps/help2man"
        list_to_rm += " app-text/docbook-xsl-ns-stylesheets"
        list_to_rm += " app-text/docbook-xsl-stylesheets app-text/docbook-xml-dtd:4.1.2"
        list_to_rm += " app-text/docbook-xml-dtd:4.2 app-text/docbook-xml-dtd:4.3"
        list_to_rm += " app-text/docbook-xml-dtd:4.4 app-text/docbook-xml-dtd:4.5"
        list_to_rm += " app-text/build-docbook-catalog app-text/xmlto"
        list_to_rm += " app-text/asciidoc app-text/sgml-common"
        list_to_rm += " dev-lang/rust-common dev-lang/rust"
        list_to_rm += " llvm-core/llvm llvm-core/llvm-toolchain-symlinks"
        list_to_rm += " llvm-core/llvmgold dev-libs/oniguruma"
        list_to_rm += " llvm-core/llvm-common sys-libs/binutils-libs"
        list_to_rm += " dev-build/ninja dev-build/meson dev-build/meson-format-array"
        list_to_rm += " dev-cpp/eigen"
        list_to_rm += " "
        self.__chroot(f"emerge -aC {list_to_rm} && ldconfig", temp_dir)
        self.__do_archive("excl_min", "FULL_min_bdeps", temp_dir)

    def sqh(self):
        self.__fix_xorg()
        date = datetime.datetime.today().strftime('%Y_%m_%d')
        temp_dir = f"{ROOT_DIR}/build/tmp"
        self.__tmp_clean(temp_dir)
        self.__remove_bdeps(temp_dir)
        # pack a minimal archive
        arch_path = self.__do_archive("excl", "OS", temp_dir)
        # remove temp directory
        self.__tmp_clean(temp_dir)
        self.__extract_tar(arch_path, temp_dir)
        sqh_fn = f"{ROOT_DIR}/out/root_{date}.sqh"
        self.__make_sqh(temp_dir, sqh_fn)
        #os.symlink(sqh_fn, f"{ROOT_DIR}/out/root.sqh")
        self.__tmp_clean(temp_dir)

    def action(self, action):
        for act in self.actions:
            if (act[0] == action):
                act[1]()
                break

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

import json, os, stat, re
from pathlib import Path
from . import *

units = { "B": 1, "K": 2**10, "M": 2**20, "G": 2**30 }

class Board:
    def __init__(self, name, js_fn, targets_meta):
        self.name = name
        self.out_dir = f"{ROOT_DIR}/out/{name}"
        self.out_sh = f"{ROOT_DIR}/out"
        with open(js_fn) as json_data:
            self.json = json.load(json_data)
            json_data.close()
        self.build_list = self.json["build"]
        self.installs = self.json["install"]
        self.targets = []
        self.variables = []
        self.__load_vars()
        for target in self.json["targets"]:
            t = self.__find_meta(targets_meta, target["parent"])
            if (t == 0):
                Logger.error("Unable to find parent for package!")
            t.load_detail(self.name, target, self.parse_variables)
            self.targets.append(t)
        self.__scan_deps()

    def __scan_deps(self):
        # scan for dependencies
        for target in self.targets:
            for dep_name in target.dep_names:
                dep = self.__find_target(dep_name)
                if (dep == 0):
                    Logger.error(f"Unable to find package '{dep_name}'!")
                target.depends.append(dep)

    def __find_meta(self, targets_meta, name):
        for meta in targets_meta:
            if (meta.name == name):
                t = meta
                t.depends = []
                return t
        return 0

    def __find_target(self, name):
        for target in self.targets:
            if (target.name == name):
                return target
        return 0

    def __load_vars(self):
        for var_def in self.json["variables"]:
            self.variables.append(var_def.split(":"))
        self.variables.append(["board_name", self.name])
        self.variables.append(["build_dir", f"{ROOT_DIR}/build/{self.name}"])
        self.variables.append(["out_dir", self.out_dir])
        self.variables.append(["out_sh", self.out_sh])

    def parse_variables(self, string):
        for var_d in self.variables:
            string = string.replace("%{"+var_d[0]+"}%", var_d[1])
        #out_dir
        return string

    def sync(self):
        for target in self.targets:
            target.source_sync()

    def build(self, target_name):
        sub_target = ""
        if (target_name == "all"):
            target_list = self.build_list
        else:
            targets = target_name.split('-')
            target_list = [ targets[0] ]
            if (len(targets) > 1):
                sub_target = targets[1]
        is_finded = False
        for t_name in target_list:
            for target in self.targets:
                if (t_name == target.name):
                    is_finded = True
                    for dep in target.depends:
                        if (sub_target == ""):
                            #when run sub-target - not need to check a deps
                            dep.build("", self.out_dir)
                    target.build(sub_target, self.out_dir)
                    break
        if (not is_finded):
            Logger.error("Don't find target!")

    def __do_cmd(self, args, cwd=None, env=None, stdin=None):
        if (stdin != None):
            p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE, text=True)
        else:
            p = subprocess.Popen(args, cwd=cwd, env=env)
        if (stdin != None):
            p.communicate(input=stdin)
        if (p.wait() != 0):
            Logger.error(f"Command '{args[0]}' finished with error code!")

    def __make_blk_struct(self, dev):
        Logger.install("\tBlock device. Prepare and mount it...")

    def __create_img_file(self, path, size):
        Logger.install("\tCreate image file...")
        img_f = Path(path)
        if (img_f.is_file()):
            shutil.rmtree(path, ignore_errors=True)
        blk_size = 1024*1024
        blk_count = int(size / blk_size)
        self.__do_cmd(["dd", "if=/dev/zero", f"of={path}", f"bs={blk_size}", f"count={blk_count}"])

    def __parse_size(elf, size):
        size = size.upper()
        if not re.match(r' ', size):
            size = re.sub(r'([KMGT])', r' \1', size)
        number, unit = [string.strip() for string in size.split()]
        return int(float(number)*units[unit])

    def __create_parts(self, img_or_dev):
        args = ""
        args += "o\n"
        for part in self.installs["partitions"]:
            part_sz = part["size"]
            args += "n\n"
            args += "p\n"
            args += "\n"
            args += "\n"
            args += f"+{part_sz}\n"
        args += "w\n"
        args += "q\n"
        self.__do_cmd(["fdisk", img_or_dev], stdin=args)

    def __install_to_img(self):
        Logger.install("\tImage. Prepare and mount it...")
        img_fn = f"{self.out_dir}/all.img"
        # basic image offset - space for partition table and bootloader
        img_sz = 1024*1024 + 512
        parts = self.installs["partitions"]
        for part in parts:
            img_sz += self.__parse_size(part["size"])
        self.__create_img_file(img_fn, img_sz)
        self.__create_parts(img_fn)

    def install(self, dir):
        Logger.install(f"Install to '{dir}'")
        if (self.installs["target"] == "image"):
            self.__install_to_img()
        else:
            Logger.error("Unsupported instalation type!")
        #is_blk = False
        #if (stat.S_ISBLK(os.stat(dir).st_mode)):
        #    dir = self.__make_blk_struct(dir)

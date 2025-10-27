import json, os, re, datetime
from pathlib import Path
from . import *

class Board:
    def __init__(self, name, js_fn, targets_meta):
        self.name = name
        self.out_dir = f"{OUT_DIR}/{name}"
        self.out_sh = f"{OUT_DIR}"
        with open(js_fn) as json_data:
            self.json = json.load(json_data)
            json_data.close()
        self.build_list = self.json["build"]
        self.installs = self.json["install"]
        self.targets = []
        self.variables = []
        self.__load_vars()
        for target in self.json["targets"]:
            if ("parent" in target):
                t = self.__find_meta(targets_meta, target["parent"])
                if (t == 0):
                    Logger.error("Unable to find parent for package!")
                t.load_detail(self.name, target)
                self.targets.append(t)
                for module in t.modules:
                    m = self.__find_meta(targets_meta, module)
                    if (m == 0):
                        Logger.error("Unable to find parent for module!")
                    m.load_detail(self.name, None)
                    self.targets.append(m)
            else:
                t = targets_meta[0].wo_parent(target)
                t.load_detail(self.name, target)
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
        add_vars(self.json["variables"])
        add_var("board_name", self.name)
        add_var("build_root", BUILD_DIR)
        add_var("build_dir", f"{BUILD_DIR}/{self.name}")
        add_var("common_dir", "%{build_root}%/common_%{ARCH}%")
        add_var("out_dir", self.out_dir)
        add_var("cfg_dir", f"cfg/{self.name}")
        add_var("out_sh", self.out_sh)
        add_var("ROOT_DIR", ROOT_DIR)
        add_var("DATE", datetime.datetime.today().strftime('%Y_%m_%d'))

    def targets_list(self):
        lst = []
        lst.append("all")
        lst.append("initramfs")
        for target in self.targets:
            lst.append(target.name)
        return lst

    def sync(self):
        for target in self.targets:
            target.source_sync()

    def __build(self, target_list, sub_target):
        is_finded = False
        for t_name in target_list:
            for target in self.targets:
                if (t_name == target.name):
                    is_finded = True
                    if (target.is_shared):
                        out_dir = self.out_sh
                    else:
                        out_dir = self.out_dir
                    for dep in target.depends:
                        if (sub_target == ""):
                            #when run sub-target - not need to check a deps
                            dep.build("", out_dir)
                    target.build(sub_target, out_dir)
                    if (sub_target == ""):
                        #when run sub-target - not need to build a modules
                        for module in target.modules:
                            self.__build([module], "")
                    break
        return is_finded

    def build(self, target_name):
        sub_target = ""
        if (target_name == "all"):
            target_list = self.build_list
        else:
            targets = target_name.split('-')
            target_list = [ targets[0] ]
            if (len(targets) > 1):
                sub_target = targets[1]
        is_finded = self.__build(target_list, sub_target)
        if (not is_finded):
            Logger.error(f"Don't find target! Available: {self.targets_list()}")

    def scan_kernel(self):
        target = self.get_kernel()
        if (target != None):
            target.source_sync()
            cfg_scn = ConfigScan(parse_variables("%{KERNEL_ARCH}%"))
            cfg_scn.scan(target.sources.work_dir)
            cfg_scn.save()

    def get_kernel(self):
        for target in self.targets:
            if (target.name == "kernel"):
                return target
        return None

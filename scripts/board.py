import json, os
from pathlib import Path
from . import *

class Board:
    def __init__(self, name, js_fn, targets_meta):
        self.name = name
        self.out_dir = f"{ROOT_DIR}/out/{name}"
        self.out_sh = f"{ROOT_DIR}/out"
        with open(js_fn) as json_data:
            self.json = json.load(json_data)
            json_data.close()
        self.build_list = self.json["build"]
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
                    Logger.error("Unable to find package!")
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

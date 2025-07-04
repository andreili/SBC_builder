import json, os
from pathlib import Path
from . import *

class Target:
    def __init__(self, meta_js):
        self.name = ''
        for key in meta_js.keys():
            if (self.name != ''):
                raise "Invalid target definition!"
            self.name = key
            self.sources = Sources(self.name, meta_js[key]["url"])
            self.have_config = meta_js[key]["config"]
            if (self.have_config):
                self.config_target = meta_js[key]["config_target"]
            else:
                self.config_target = ""
            self.is_shared = meta_js[key]["is_shared"]

    def load_meta(meta_fn):
        with open(meta_fn) as json_data:
            js_data = json.load(json_data)
            json_data.close()
        res = []
        for meta in js_data:
            t = Target(meta)
            res.append(t)
        return res

    def load_detail(self, board_name, detail_js, parse_variables):
        self.board_name = board_name
        self.sources.init_source_path(board_name, self.is_shared)
        self.sources.set_git_params(detail_js["version"], detail_js["version_type"])
        self.target = detail_js["target"]
        self.version = detail_js["version"]
        if (self.is_shared):
            self.config_name = f"{ROOT_DIR}/cfg/{self.name}"
        else:
            self.config_name = f"{ROOT_DIR}/cfg/{board_name}/{self.name}"
        if (self.version != "") and (self.version != "@"):
            self.config_name += f"_{self.version}"
        if ("patch_dir" in detail_js):
            self.patch_dir = detail_js["patch_dir"]
        else:
            self.patch_dir = ""
        if ("deps" in detail_js):
            self.dep_names = detail_js["deps"]
        else:
            self.dep_names = []
        if ("makeopts" in detail_js):
            self.makeopts = parse_variables(detail_js["makeopts"])
        else:
            self.makeopts = ""
        if ("config_def" in detail_js):
            self.defconfig = detail_js["config_def"]
        else:
            self.defconfig = ""
        if ("no_build" in detail_js):
            self.no_build = True
        else:
            self.no_build = False
        _artifacts = detail_js["artifacts"]
        self.artifacts = []
        for art in _artifacts:
            art["file"] = parse_variables(art["file"])
            self.artifacts.append(art)
    
    def source_sync(self):
        Logger.build(f"'{self.name}': Source prepare")
        self.sources.sync()
        self.sources.do_patch(self.board_name, self.patch_dir)

    def build(self, sub_target, out_dir):
        #self.source_sync()
        if (not self.no_build):
            opts = self.makeopts.split(" ")
            config = ""
            targets = [""]
            if (sub_target == "") or (not self.have_config):
                targets = self.target
            else:
                if (sub_target == "config"):
                    shutil.copyfile("cfg/printer_defconfig", "build/common/kernel/arch/arm64/configs/printer_defconfig")
                    opts.append(self.defconfig)
                    opts.append(self.config_target)
                else:
                    Logger.error("Invalid sub-target!")
            for target in targets:
                opts_tmp = opts.copy()
                opts_tmp.append(target)
                self.sources.compile(opts_tmp, self.config_name)
        if (sub_target != "config"):
            self.sources.copy_artifacts(self.artifacts, out_dir)

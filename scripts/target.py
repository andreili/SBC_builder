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
        self.sources.init_source_path(board_name)
        self.sources.set_git_params(detail_js["version"], detail_js["version_type"])
        self.target = detail_js["target"]
        self.version = detail_js["version"]
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
        self.source_sync()
        opts = self.makeopts.split(" ")
        if (sub_target == "") or (not self.have_config):
            opts += self.target
        else:
            if (sub_target == "config"):
                opts.append(self.config_target)
            else:
                Logger.error("Invalid sub-target!")
        self.sources.compile(opts, self.config_name)
        self.sources.copy_artifacts(self.artifacts, out_dir)

import json, os
from pathlib import Path
from . import *

class Target:
    def __init__(self, meta_js):
        self.name = ''
        self.config_target = ""
        self.patch_dir = ""
        self.dep_names = []
        self.makeopts = ""
        self.defconfig = ""
        self.version = ""
        self.no_build = False
        self.artifacts = []
        self.modules = []
        self.have_config = False
        for key in meta_js.keys():
            if (self.name != ''):
                raise "Invalid target definition!"
            self.name = key
            meta_info = meta_js[key]
            self.sources = Sources(self.name, meta_info["url"])
            self.have_config = meta_info["config"]
            if (self.have_config):
                self.config_target = meta_info["config_target"]
            self.is_shared = meta_info["is_shared"]
            self.__load_info(meta_info)

    def load_meta(meta_fn):
        with open(meta_fn) as json_data:
            js_data = json.load(json_data)
            json_data.close()
        res = []
        for meta in js_data:
            t = Target(meta)
            res.append(t)
        return res

    def __load_info(self, info_js, parse_variables=None):
        if ("version" in info_js):
            self.sources.set_git_params(info_js["version"], info_js["version_type"])
            self.target = info_js["target"]
            self.version = info_js["version"]
        if ("patch_dir" in info_js):
            self.patch_dir = info_js["patch_dir"]
        if ("deps" in info_js):
            self.dep_names = info_js["deps"]
        if ("makeopts" in info_js):
            self.makeopts = info_js["makeopts"]
        if ("config_def" in info_js):
            self.defconfig = info_js["config_def"]
        if ("no_build" in info_js):
            self.no_build = True
        if ("artifacts" in info_js):
            _artifacts = info_js["artifacts"]
            for art in _artifacts:
                self.artifacts.append(art)
        if ("modules" in info_js):
            self.modules = info_js["modules"]

    def load_detail(self, board_name, detail_js, parse_variables):
        self.board_name = board_name
        self.sources.init_source_path(board_name, self.is_shared)
        if (detail_js != None):
            self.__load_info(detail_js, parse_variables)
        if (self.is_shared):
            self.config_name = f"{ROOT_DIR}/cfg/{self.name}"
        else:
            self.config_name = f"{ROOT_DIR}/cfg/{board_name}/{self.name}"
        if (self.version != "") and (self.version != "@"):
            self.config_name += f"_{self.version}"
        self.makeopts = parse_variables(self.makeopts)
        for art in self.artifacts:
            art["file"] = parse_variables(art["file"])
    
    def source_sync(self):
        Logger.build(f"'{self.name}': Source prepare")
        self.sources.sync()
        self.sources.do_patch(self.board_name, self.patch_dir)

    def build(self, sub_target, out_dir):
        self.source_sync()
        self.sources.prepare_artifacts(self.artifacts, out_dir)
        if (not self.no_build):
            opts = self.makeopts.split(" ")
            config = ""
            targets = [""]
            if (sub_target == "") or (not self.have_config):
                targets = self.target
            else:
                if (sub_target == "config"):
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

    def install_files(self, dir, tmp_dir, part_name, on_file, on_dd):
        Logger.install(f"'{self.name}': Install artifacts")
        for art in self.artifacts:
            art_fn = os.path.basename(art["file"])
            if (art["store_type"] == part_name):
                if "subdir" in art:
                    subdir = art["subdir"] + "/"
                    destdir = art["destdir"] + "/"
                    on_file(f"{tmp_dir}/{subdir}", f"{dir}/{destdir}")
                else:
                    on_file(f"{tmp_dir}/{art_fn}", f"{dir}/")
            if (art["store_type"] == "dd"):
                on_dd(f"{tmp_dir}/{art_fn}", art["block_size"], int(art["img_offset"]))

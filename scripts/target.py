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
            self.have_config = meta_info["config"]
            if (self.have_config):
                self.config_target = meta_info["config_target"]
            self.is_shared = meta_info["is_shared"]
            self.__load_info(meta_info)

    def wo_parent(self, meta_js):
        js = dict()
        t_name = meta_js["name"]
        js[t_name] = meta_js
        t = Target(js)
        t.depends = []
        return t

    def load_meta(meta_fn):
        with open(meta_fn) as json_data:
            js_data = json.load(json_data)
            json_data.close()
        res = []
        for meta in js_data:
            t = Target(meta)
            res.append(t)
        return res

    def __load_info(self, info_js):
        if ("url" in info_js):
            if ("bare_dir" in info_js):
                self.sources = Sources(self.name, info_js["url"], info_js["bare_dir"])
            else:
                self.sources = Sources(self.name, info_js["url"])
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
            self.defconfig_name = parse_variables(info_js["config_def"])
        if ("config_set" in info_js):
            self.config_set = info_js["config_set"]
        if ("no_build" in info_js):
            self.no_build = True
        if ("artifacts" in info_js):
            self.artifacts = []
            _artifacts = info_js["artifacts"]
            for art in _artifacts:
                self.artifacts.append(art)
        if ("modules" in info_js):
            self.modules = info_js["modules"]
        if ("is_shared" in info_js):
            self.is_shared = info_js["is_shared"]
        if ("target" in info_js):
            self.target = info_js["target"]

    def load_detail(self, board_name, detail_js):
        self.board_name = board_name
        if (detail_js != None):
            self.__load_info(detail_js)
        self.sources.init_source_path(board_name, self.is_shared)
        if (self.is_shared):
            arch = parse_variables("%{ARCH}%")
            self.config_name = f"{ROOT_DIR}/cfg/{arch}_{self.name}"
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

    def do_uboot_spi_env(self, env_val):
        if (env_val == None):
            return
        Logger.install(f"\tCreate SPI install files")
        spi_layout = ""
        spi_idx_uboot = env_val["u-boot-spi-idx"]
        spi_idx_kernel = env_val["kernel-spi-idx"]
        env_fn = f"{self.sources.work_dir}/{parse_variables(env_val["name"])}"
        idx = 0
        cmd_sh = "#!/bin/sh\n"
        cmd_sh += f"FILE_DIR=$(dirname $(readlink -f $0))\n"
        for part in env_val["partitions"]:
            spi_layout += f"{part["size"]}({part["name"]}),"
            cmd_sh += f"dd if=${{FILE_DIR}}/{parse_variables(part["file"])} of=/dev/mtdblock{idx}\n"
            idx += 1
        spi_parts_u_boot = f"spi{spi_idx_uboot}.0:{spi_layout[:-1]}"
        spi_parts_kernel = f"spi{spi_idx_kernel}.0:{spi_layout[:-1]}"
        cmd  = f"mtdids=nor0=spi{spi_idx_uboot}.0\n"
        cmd += f"mtdparts={spi_parts_u_boot}\n"
        cmd += f"bootcmd=bootflow scan -lb\n"
        cmd += f"bootargs=mtdparts={spi_parts_kernel}\n"
        cmd += f"preboot=sf probe\n"
        cmd += f"bootmenu_delay=5\n"
        cmd += f"bootmenu_0=Default=run bootcmd\n"
        cmd += f"bootmenu_1=Live=run live\n"
        cmd += f"bootmenu_3=Recovery=run recovery\n"
        cmd += f"bootmenu_4=Console=run console\n"
        cmd +=  "rec_env=setenv bootargs emergency\n"
        cmd +=  "rec_load=mtd read kernel ${kernel_addr_r}; mtd read initrd ${ramdisk_addr_r}; mtd read dtb ${fdt_addr_r}\n"
        cmd +=  "rec_boot=booti ${kernel_addr_r} ${ramdisk_addr_r} ${fdt_addr_r}\n"
        cmd +=  "recovery=run rec_load; run rec_env; run rec_boot\n"
        cmd +=  "live=run rec_load; run rec_boot\n"
        with open(env_fn, "w") as f:
            f.write(cmd)
            f.close()
        self.spi_install = cmd_sh
        self.spi_env = cmd

    def build(self, sub_target, out_dir, spi_env_val):
        self.source_sync()
        self.spi_install = None
        self.do_uboot_spi_env(spi_env_val)
        if (sub_target != "config"):
            self.sources.prepare_artifacts(self.artifacts, out_dir)
        if (not self.no_build):
            opts = self.makeopts.split(" ")
            config = ""
            targets = [""]
            if (sub_target == "") or (not self.have_config):
                targets = self.target
            else:
                if (sub_target == "defconfig"):
                    if (self.name == "kernel"):
                        # initialize without arch - required only for parsing
                        cfg_scn = ConfigScan(parse_variables("%{KERNEL_ARCH}%"))
                        cfg_scn.load()
                        cfg_scn.defconfig_start()
                        if (isinstance(self.defconfig_name, str)):
                            cfg_scn.defconfig_append(self.defconfig_name, self.config_set)
                        else:
                            for cfg_name in self.defconfig_name:
                                cfg_scn.defconfig_append(cfg_name, self.config_set)
                        cfg_scn.defconfig_save(self.sources.work_dir, "gen_config_set")
                        opts.append("gen_config_set_defconfig")
                    else:
                        opts.append(self.defconfig_name)
                elif (sub_target == "config"):
                    opts.append(self.config_target)
                else:
                    Logger.error("Invalid sub-target!")
            for target in targets:
                opts_tmp = opts.copy()
                opts_tmp.append(target)
                self.sources.compile(opts_tmp, self.config_name)
        if (not fnmatch.fnmatch(sub_target, "*config")):
            self.sources.copy_artifacts(self.artifacts, out_dir)
            if (self.spi_install != None):
                Logger.install(f"\tCreate SPI install files")
                spi_fn = f"{out_dir}/spi_install.sh"
                with open(spi_fn, "w") as f:
                    f.write(self.spi_install)
                    f.close()
                with open(f"{out_dir}/spi_env.txt", "w") as f:
                    f.write(self.spi_env)
                    f.close()

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

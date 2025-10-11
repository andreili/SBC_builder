from . import *

class CfgOpt:
    def __init__(self, s_value):
        if ("=" in s_value):
            # have a value, parse
            val = s_value.split("=")
            self.name = val[0]
            self.value = val[1]
        else:
            self.name = s_value
            self.value = ""

class CfgSet:
    def __init__(self, js_info):
        self.save_path = ""
        self.depends = []
        self.options = []
        self.opt_tmp = []
        self.name = js_info["name"]
        if ("save_path" in js_info):
            self.save_path = js_info["save_path"]
        if ("depends" in js_info):
            self.depends = js_info["depends"]
        if ("options" in js_info):
            opts = js_info["options"]
            for opt in opts:
                opt_o = CfgOpt(opt)
                self.options.append(opt_o)
        #Logger.build(f"Loaded config {self.name} with {len(self.options)} options")

class Defconfig:
    def __init__(self, name=""):
        self.sets = []
        self.configs = []
        if (name != ""):
            meta_fn = f"{ROOT_DIR}/config/{name}_meta.json"
            with open(meta_fn) as json_data:
                js_data = json.load(json_data)
                json_data.close()
            self.load_json(name, js_data)

    def load_json(self, name, js_data):
        if ("includes" in js_data):
            includes = js_data["includes"]
            for inc_name in includes:
                inc_fn = f"{ROOT_DIR}/config/{name}/{inc_name}.json"
                with open(inc_fn) as inc_data:
                    inc_js = json.load(inc_data)
                    inc_data.close()
                for inc in inc_js:
                    cfg = CfgSet(inc)
                    if (self.__if_set_exists(cfg.name) == True):
                        Logger.error(f"Duplicate configuration set '{cfg.name}!")
                    self.sets.append(cfg)
        if ("configs" in js_data):
            configs = js_data["configs"]
            for cfg in configs:
                cfg_o = CfgSet(cfg)
                self.sets.append(cfg_o)

    def __if_set_exists(self, name):
        for s in self.sets:
            if (s.name == name):
                return True
        return False

    def __find_set(self, name):
        for s in self.sets:
            if (s.name == name):
                return s
        Logger.error(f"Unable to find set '{name}!")
        return None

    def __append_opt_or_change_value(self, opt):
        for o in self.opt_tmp:
            if (o.name == opt.name):
                o.value = opt.value
                return
        self.opt_tmp.append(opt)

    def __scan_opts(self, cfg_set):
        # recursive add depends
        for dep in cfg_set.depends:
            self.__scan_opts(self.__find_set(dep))
        # get options list
        for opt in cfg_set.options:
            # if options already on list - only need to update value
            self.__append_opt_or_change_value(opt)

    def save(self, dir):
        for cfg in self.sets:
            if (cfg.save_path != ""):
                self.opt_tmp = []
                self.__scan_opts(cfg)
                save_fn = f"{dir}/{cfg.save_path}"
                Logger.build(f"Saving config set '{cfg.name}', contains {len(self.opt_tmp)} options")
                with open(save_fn, "w") as f:
                    for opt in self.opt_tmp:
                        if (opt.value != ""):
                            f.write(f"{opt.name}={opt.value}\n")
                        else:
                            f.write(f"{opt.name}\n")
                    f.close()

    def save_custom(self, dir):
        print("custom - todo")

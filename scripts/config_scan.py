#!/bin/python
import re, json, os.path, fnmatch
from rich.progress import Progress
from . import *

CFG_NAME=f"{CONFIG_DIR}/kernel_cfg.json"

class ConfigCondition:
    def __init__(self, line):
        self.opt_str = ""
        self.is_not = False
        self.is_or = False
        self.is_and = False
        self.is_br_op = False
        self.is_br_cl = False
        self.is_eq = False
        self.is_neq = False
        self.is_force = False
        self.is_flex = False
        self.val = None
        if (line == "||"):
            self.is_or = True
        elif (line == "&&"):
            self.is_and = True
        elif (line == "!"):
            self.is_not = True
        elif (line == "("):
            self.is_br_op = True
        elif (line == ")"):
            self.is_br_cl = True
        else:
            m_eq = re.findall(r'(\w+)(\!=|=)"*(\w*)"*', line)
            if (m_eq):
                self.opt_str = m_eq[0][0]
                eq_op        = m_eq[0][1]
                self.val     = m_eq[0][2]
                if (eq_op == "="):
                    self.is_eq = True
                elif (eq_op == "!="):
                    self.is_neq = True
            else:
                self.opt_str = line
    def set_val(self, val):
        if (val != ""):
            self.is_eq = True
            if (val[0] == "!"):
                self.is_force = True
                self.val = val[1:]
            elif (val[0] == "?"):
                self.is_flex = True
                self.val = val[1:]
            elif (not self.is_force):
                self.val = val
                self.is_flex = False
    def serialize(self):
        if (self.is_not):
            return "!"
        elif (self.is_or):
            return "||"
        elif (self.is_and):
            return "&&"
        elif (self.is_br_op):
            return "("
        elif (self.is_br_cl):
            return ")"
        elif (self.is_eq):
            return f"{self.opt_str}={self.val}"
        elif (self.is_neq):
            return f"{self.opt_str}!={self.val}"
        else:
            return self.opt_str

class ConfigOpt:
    def __init__(self, name):
        self.name = name
        self.deps = []
    def __parse_dep(self, line):
        #print(line)
        m_cond = re.findall(r'(\|\|)|(&&)|(!)|(\()|(\))|([\w=!\"]+)', line)
        for cond in m_cond:
            for cc in cond:
                if (cc == ""):
                    # empty match - skip
                    continue
                if (cc == "#"):
                    # commentary - end of options
                    break
                #print(cc)
                self.deps.append(ConfigCondition(cc))
    def opt_body_parse(self, body, if_opt):
        if ((len(self.deps) == 0) and (if_opt != "")):
            # global "if..endif" into Kconfig
            ifs = if_opt.split(",")
            for if_o in ifs:
                self.deps.append(ConfigCondition(if_o))
                self.deps.append(ConfigCondition("&&"))
        if (len(self.deps) > 0) and (self.deps[-1].is_and):
            # remove last AND operator
            self.deps = self.deps[:-1]
        m_dep = re.match(r'depends on (.+)$', body)
        if (m_dep):
            dep = m_dep[1]
            if (dep[0] == '$'):
                return
            if (len(self.deps) != 0):
                # not a first dependency - use AND
                self.deps.append(ConfigCondition("&&"))
            self.deps.append(ConfigCondition("("))
            self.__parse_dep(dep)
            self.deps.append(ConfigCondition(")"))
    def serialize(self):
        deps = ""
        for dep in self.deps:
            deps += dep.serialize()
        return { "name":self.name,
                 "deps":deps }
    def deserialize(self, js):
        self.name = js["name"]
        self.__parse_dep(js["deps"])

class KconfigScan:
    def __init__(self, path, cb_var, cb_on_opt):
        self.path = path
        self.cb_var = cb_var
        self.cb_on_opt = cb_on_opt
    def scan(self, sub_dir="", if_opt=""):
        full_path = f"{self.path}/{sub_dir}"
        f = open(f"{full_path}/Kconfig", "rt")
        while (f):
            line = f.readline()
            if (line == ""):
                # EOF detector
                break
            m_source = re.match(r'^source\s+\"(\S+)/Kconfig\"', line)
            if (m_source):
                # current line - include another config
                inc_parsed = self.cb_var(m_source[1])
                self.scan(inc_parsed, if_opt)
            m_cfg = re.match(r'^(?:config|menuconfig)\s+(\S+)', line)
            if (m_cfg):
                # read required lines and pass to parser
                opt_name = m_cfg[1]
                opt = ConfigOpt(opt_name)
                while (1):
                    ll = f.readline()
                    if ((ll == "") or (ll == "\n")):
                        # EOF detector
                        break
                    m_body = re.match(r'^\t(.+)$', ll)
                    if (m_body):
                        opt.opt_body_parse(m_body[1], if_opt)
                self.cb_on_opt(opt)
            # processing for "if..endif" into Kconfig
            m_if = re.match(r'^if (\S+)$', line)
            if (m_if):
                if (if_opt != ""):
                    if_opt += "," + m_if[1]
                else:
                    if_opt = m_if[1]
            m_endif = re.match(r'^endif', line)
            if (m_endif):
                ifs = if_opt.split(",")
                if (len(ifs) > 1):
                    if_opt = ",".join(ifs[:-1])
                else:
                    if_opt = ""
        f.close()

r_km_obj_mask = r'[\w\.\-/]+'
r_km_ignores = r'(?!.*flags)(?!.*flag)(?!^#)'
r_rm_prefix = r'^(\S+)-(?:objs|y|(?:(?:\$\([\s\S]+)*\$\(CONFIG_(\S+)\)(?:\))*))'
r_km_obj_cfg = re.compile(r_km_ignores + r_rm_prefix + r'\s*[ :\+]=((?: *' + r_km_obj_mask + r')*)')
r_km_comp = re.compile(r'(?:(?:OF_DECLARE\S*|IRQCHIP_DECLARE)\(\S+,\s+\"(\S+)\",.+\))|' +
    r'(?:\.compatible\s+=\s+\"(\S+)\")|' +
    r'(?:of_device_is_compatible\(\S+,\s+\"(\S+)\"\))')

class KmakefileScan:
    def __init__(self, path, cb_var, on_comp):
        self.path = path
        self.cb_var = cb_var
        self.on_comp = on_comp
        self.sources = []
    def __do_fn(self,  sub_dir, cond, fn):
        if (fn.endswith("/")):
            # include subdirectory
            self.scan(f"{sub_dir}/{fn[:-1]}", cond)
        else:
            # object file name - add to list
            self.sources.append({ "path":f"{sub_dir}/{fn[:-2]}.c",
                                  "cond":cond})
    def __do_line(self, f, sub_dir, cond, line, rec=False):
        line = self.cb_var(line)
        if (rec):
            m_obj_cfg = re.findall(r'^(\s+)(\s*)((?:\s*' + r_km_obj_mask + r')+)', line)
        else:
            m_obj_cfg = r_km_obj_cfg.findall(line)
        if (len(m_obj_cfg) == 0):
            # can't find any valid elements, skip
            return
        m_obj_cfg = m_obj_cfg[0]
        cond_loc = ""
        syn = ["",""]
        #print(m_obj_cfg)
        if ((not rec) and (m_obj_cfg[1] != "")):
            cond_loc = m_obj_cfg[1]
            if (cond_loc[-1] == ")"):
                cond_loc = cond_loc[:-1]
        else:
            cond_loc = cond
        obj = m_obj_cfg[2]
        #print(f":{cond_loc}:{m_obj_cfg}:{line[-2]}+{rec}")
        if (len(obj) == 0) and (line[-2] != "\\"):
            return
        if (obj != ""):
            while (obj[0] == " "):
                obj = obj[1:]
            objs = obj.split(" ")
            for o in objs:
                self.__do_fn(sub_dir, cond_loc, o)
        if ((not rec) and (line[-2] == "\\")):
            # slash - need to scan next line
            while (1):
                line = f.readline()
                if (len(line) < 3):
                    break
                self.__do_line(f, sub_dir, cond_loc, line, True)
                if (line[-2] != "\\"):
                    break
        if (m_obj_cfg[0] == "obj"):
            # next line is a synonym?
            line = f.readline()
            m_obj_next = r_km_obj_cfg.findall(line)
            if (m_obj_next):
                target_name = m_obj_next[0][0] + ".o"
                obj_new = m_obj_next[0][2]
                if (target_name == obj) and (obj_new != ""):
                    while (obj_new[0] == " "):
                        obj_new = obj_new[1:]
                    self.__do_fn(sub_dir, cond_loc, obj_new)
                else:
                    # not a synonym - process line again
                    self.__do_line(f, sub_dir, cond_loc, line)
            else:
                # not a synonym - process line again
                self.__do_line(f, sub_dir, cond_loc, line)
    def scan(self, sub_dir="", cond=""):
        if (sub_dir == ""):
            full_path = self.path
        else:
            full_path = f"{self.path}/{sub_dir}"
        #print(f"\tDir: {sub_dir}")
        mk_fn1 = f"{full_path}/Kbuild"
        mk_fn2 = f"{full_path}/Makefile"
        if (os.path.isfile(mk_fn1)):
            f = open(mk_fn1, "rt")
        elif (os.path.isfile(mk_fn2)):
            f = open(mk_fn2, "rt")
        else:
            print(f"Unable to find build file at '{full_path}'!!!")
            exit(1)
        while 1:
            line = f.readline()
            if (line == ""):
                # EOF detector
                break
            #print(line)
            if (re.match(r'(tests\/)', line)):
                continue
            self.__do_line(f, sub_dir, cond, line)
        f.close()
    def scan_compatible(self):
        progress = Progress()
        progress.start()
        task = progress.add_task("Scanning object files...", total=len(self.sources))
        for obj in self.sources:
            progress.update(task, advance=1)
            fn = f"{self.path}/{obj["path"]}"
            if (not os.path.isfile(fn)):
                continue
            f = open(fn, "r")
            while (1):
                line = f.readline()
                if (line == ""):
                    # EOF detector
                    break
                m_o = r_km_comp.findall(line)
                if (len(m_o) == 0) and ("of_device_is_compatible" in line):
                    # multiline, concatenate
                    line += f.readline()
                    m_o = r_km_comp.findall(line)
                if not ("!of_device_is_compatible" in line):
                    for oo in m_o:
                        for o in oo:
                            if (o != ""):
                                self.on_comp(o, obj["cond"])
            f.close()
        progress.stop()

r_dt_skip = [
    "arm,cortex-*",
    "cache",
]

class DTSScan:
    def __init__(self, path, arch, find_comp, on_defcfg):
        self.path = path
        self.arch = arch
        self.find_comp = find_comp
        self.on_defcfg = on_defcfg
    def __parse_dts(self, dir, fn):
        f = open(fn, "r", encoding='ISO-8859-1')
        par = ""
        while (1):
            line = f.readline()
            if (line == ""):
                # EOF detector
                break
            m_inc = re.match(r'#include \"(\S+\.dtsi)\"', line)
            if (m_inc):
                new_fn = f"{dir}/{m_inc[1]}"
                if (os.path.isfile(new_fn)):
                    self.__parse_dts(dir, new_fn)
                #else:
                #    print(f"Unable to find inlude file '{m_inc[1]}'")
            m_par = re.findall(r'(\S+) {$', line)
            if (m_par):
                par = m_par[0]
            if (par == '/'):
                # skip root node properties
                continue
            if (re.findall(r'(compatible = \")', line)):
                finded = False
                m_comp = re.findall(r'(?:\"(\S+)\")+', line)
                for comp in m_comp:
                    #find compatible and opt
                    cc = self.find_comp(comp)
                    if (cc == False):
                        continue
                    finded = True
                    cc = cc.split("&&")
                    for c in cc:
                        if (not c in self.def_opts) and (c != ""):
                            self.def_opts.append(c)
                if (not finded):
                    ll = " ".join(m_comp)
                    self.def_opts.append(f"#{ll}")
                    #print(f"Unable to find compatible '{m_comp}'!")
                    #exit(1)
        f.close()
    def __scan_dts(self):
        progress = Progress()
        progress.start()
        task = progress.add_task("DTS files", total=len(self.dts_fn))
        for dts_el in self.dts_fn:
            self.def_opts = []
            dts_n = os.path.splitext(os.path.basename(dts_el[1]))[0]
            self.__parse_dts(dts_el[0], dts_el[1])
            self.on_defcfg(dts_n, self.def_opts)
            progress.update(task, advance=1)
        progress.stop()
    def __find_dts(self, dir):
        for dir_i in os.listdir(dir):
            fn = f"{dir}/{dir_i}"
            if (os.path.isfile(fn)):
                # file
                if (fnmatch.fnmatch(fn, "*.dts")):
                    self.dts_fn.append([dir, fn])
            else:
                # recursive on directories
                self.__find_dts(fn)
    def scan(self):
        self.dts_fn = []
        self.__find_dts(f"{self.path}/arch/{self.arch}/boot/dts")
        self.__scan_dts()

class ConfigSolver:
    def __init__(self, opt, on_cfg_set, on_cfg_get, pos=0):
        self.opt = opt
        self.on_cfg_set = on_cfg_set
        self.on_cfg_get = on_cfg_get
        self.stack = []
        self.pos = pos
        self.is_or = False
        self.is_and = False
    def __prepare(self):
        processed = 0
        while (self.pos < len(self.opt.deps)):
            cur_dep = self.opt.deps[self.pos]
            if (cur_dep.is_br_op):
                self.pos += 1
                processed += 1
                new_solv = ConfigSolver(self.opt, self.on_cfg_set, self.on_cfg_get, self.pos)
                self.stack.append(new_solv)
                cnt = new_solv.__prepare()
                self.pos += cnt
                processed += cnt
            elif (cur_dep.is_br_cl):
                return (processed + 1)
            else:#if (cur_dep.is_and or cur_dep.is_and or cur_dep.is_not):
                self.stack.append(cur_dep)
                self.pos += 1
                processed += 1
            if (cur_dep.is_or):
                if (self.is_and):
                    print(f"Error: mixing AND/OR operators at {self.pos}!")
                    exit(1)
                self.is_or = True
            if (cur_dep.is_and):
                if (self.is_or):
                    print(f"Error: mixing OR/AND operators at {self.pos}!")
                    exit(1)
                self.is_and = True
        return processed
    def __solve(self):
        not_op = False
        if (self.is_or):
            already_set = False
            for s in self.stack:
                if (isinstance(s, ConfigCondition)) and (s.opt_str != ""):
                    val = self.on_cfg_get(s.opt_str)
                    #print(f"\tcfg='{s.opt_str}' val='{val}'")
                    if ((val == "y") or (val == "m")):
                        # already set - skip
                        already_set = True
                        break
            if (not already_set):
                if (len(self.stack) == 4):
                    # check for "X||!X" conditions
                    if ((isinstance(self.stack[0], ConfigCondition)) and
                        (isinstance(self.stack[1], ConfigCondition)) and (self.stack[1].is_or) and
                        (isinstance(self.stack[2], ConfigCondition)) and (self.stack[2].is_not) and
                        (isinstance(self.stack[3], ConfigCondition)) and
                        (self.stack[0].opt_str == self.stack[3].opt_str)):
                        return
                if (len(self.stack) == 3):
                    # check for "X||X=n" conditions
                    if ((isinstance(self.stack[0], ConfigCondition)) and
                        (isinstance(self.stack[1], ConfigCondition)) and (self.stack[1].is_or) and
                        (isinstance(self.stack[2], ConfigCondition)) and
                        (self.stack[0].opt_str == self.stack[2].opt_str) and
                        (self.stack[2].is_eq and (self.stack[0].val == None) and (self.stack[2].val == "n"))):
                        return
                print(f"\tCondition not met: '{self.opt.serialize()['deps']}' for '{self.opt.name}'")
                return
        elif (self.is_and or (len(self.stack) < 3)):
            # both conditions must be true
            for s in self.stack:
                if (isinstance(s, ConfigSolver)):
                    # recursive solver
                    s.solve()
                elif (s.is_not):
                    not_op = True
                elif (s.opt_str != ""):
                    #option
                    if (not_op):
                        self.on_cfg_set(f"{s.opt_str}=n")
                        not_op = False
                    else:
                        self.on_cfg_set(f"{s.opt_str}=y")
    def solve(self):
        self.__prepare()
        self.__solve()

class ConfigScan:
    def __init__(self, arch):
        self.arch = arch
        self.arch_list = []
        self.opts = []
        self.compatible = dict()
        self.defconfig = dict()
        add_var("SRCARCH", self.arch)
    def __scan_arch_list(self, path):
        for dir_i in os.listdir(f"{path}/arch"):
            fn = f"{path}/arch/{dir_i}"
            if (os.path.isdir(fn)):
                self.arch_list.append(dir_i)
    def __find_opt(self, name):
        for opt in self.opts:
            if (opt.name == name):
                return opt
        return None
    def __insert_comp(self, key, value):
        if (key in self.compatible) and (self.compatible[key] != value):
            vals = self.compatible[key].split("&&")
            if (not (value in vals)) and (value != ""):
                self.compatible[key] = self.compatible[key] + "&&" + value
        else:
            self.compatible[key] = value
    def __find_comp(self, val):
        if (val in self.compatible):
            return self.compatible[val]
        # check to skip list
        for sk in r_dt_skip:
            if (fnmatch.fnmatch(val, sk)):
                return ""
        return False
    def __apply_fixes(self):
        with open(f"{CONFIG_DIR}/kernel_fix.json") as json_data:
            js_data = json.load(json_data)
            compatibles = js_data["compatibles"]
            for key in compatibles:
                self.compatible[key] = compatibles[key]
            deps = js_data["deps"]
            for key in deps:
                opt = self.__find_opt(key)
                if (opt == None):
                    opt = ConfigOpt(key)
                    opt.opt_body_parse(deps[key], "")
                    self.opts.append(opt)
                else:
                    opt.opt_body_parse(f"depends on {deps[key]}", "")
            self.systems = js_data["systems"]
            self.sets = js_data["sets"]
            json_data.close()
    def on_config_opt(self, opt):
        self.opts.append(opt)
    def add_defconfig(self, name, list):
        self.defconfig[name] = list
    def scan(self, path):
        path = parse_variables(path)
        print(f"Start scanning for options, directory '{path}'...")
        print("Step #1 - Scan Kconfig files")
        self.__scan_arch_list(path)
        KconfigScan(path, parse_variables, self.on_config_opt).scan()
        print("Step #2 - Scan Makefile for source files")
        obj = KmakefileScan(path, parse_variables, self.__insert_comp)
        obj.scan()
        print("Step #3 - Scan 'compatible' strings")
        obj.scan_compatible()
        print("Step #4 - Apply fixes")
        self.__apply_fixes()
        print("Step #5 - Scan DTS and make defconfigs")
        DTSScan(path, self.arch, self.__find_comp, self.add_defconfig).scan()
    def serialize(self):
        opts = []
        for opt in self.opts:
            opts.append(opt.serialize())
        obj = { "arch":self.arch,
                "arch_list":self.arch_list,
                "compatible":self.compatible,
                "defconfig": self.defconfig,
                #"sources":self.sources,
                "opts":opts }
        return obj
    def deserialize(self, js):
        self.arch = js["arch"]
        set_var("SRCARCH", self.arch)
        self.arch_list = js["arch_list"]
        self.compatible = js["compatible"]
        for o in js["opts"]:
            opt = ConfigOpt("")
            opt.deserialize(o)
            self.opts.append(opt)
        self.defconfig = js["defconfig"]
    def save(self):
        f = open(CFG_NAME, "w")
        json.dump(self.serialize(), f, indent=1)
        f.close()
    def load(self):
        with open(CFG_NAME) as json_data:
            js_data = json.load(json_data)
            self.deserialize(js_data)
            json_data.close()
        self.__apply_fixes()
    def __cfg_get_default(self, cfg):
        #if (cfg.lower() in self.arch_list):
        #    return None
        return "y"
    def __cfg_add_cfg(self, cfg, val):
        # TODO - check a config override, conditions, value
        def_val = self.__cfg_get_default(cfg)
        val = parse_variables(val)
        if (def_val == None):
            return
        opt = ConfigCondition(cfg)
        opt.set_val(val)
        for o in self.def_cfg:
            if (o.opt_str == cfg):
                if (o.val != "") and (val == "?n"):
                    return
                if (val != "n") and (o.val == "n") and (not o.is_force) and (not o.is_flex):
                    # override "no" value only
                    print(f"Override 'NO' value for config '{cfg}'!!! (new='{val}')")
                    exit(1)
                o.set_val(val)
                return
        self.def_cfg.append(opt)
    def __cfg_get(self, cfg):
        for o in self.def_cfg:
            if (o.opt_str == cfg):
                return o.val
        return ""
    def __check_cfg_exists(self, cfg):
        for o in self.def_cfg:
            if (o.opt_str == cfg):
                return True
        return False
    def __cfg_recursive(self, cfg):
        if (cfg[0] == "#"):
            self.__cfg_add_cfg(cfg, "")
        else:
            is_enabled = False
            is_new = False
            cfg_val = "y"
            if ("=" in cfg):
                # config have a predefined value
                oo = cfg.split("=")
                is_new = not (self.__check_cfg_exists(oo[0]))
                #print(f"Process config '{cfg}', is_new={is_new}")
                cfg = oo[0]
                cfg_val = oo[1]
                if (not ("n" in oo[1])) and (oo[1] != ""):
                    is_enabled = True
                cfg = oo[0]
            else:
                # config have a default "yes" value
                is_new = not (self.__check_cfg_exists(cfg))
                is_enabled = True
            opt = self.__find_opt(cfg)
            if (opt and is_enabled and is_new):
                # solve dependencies only for enabled and new options
                solver = ConfigSolver(opt, self.__cfg_recursive, self.__cfg_get)
                solver.solve()
            self.__cfg_add_cfg(cfg, cfg_val)
    def __get_system(self, name):
        for sys in self.systems:
            if (sys["name"] == name):
                return sys
        return None
    def _add_system(self, name):
        sys = self.__get_system(name)
        if (sys == None):
            print(f"Unable to find system '{name}'!")
            exit(1)
        for cfg in sys["options"]:
            self.__cfg_recursive(cfg)
    def __add_set(self, name):
        sys_lst = self.sets[name]
        for sys_name in sys_lst:
            if (sys_name in self.sets):
                # recursive set
                self.__add_set(sys_name)
            else:
                # add all systems for selected set
                sys = self.__get_system(sys_name)
                if (sys == None):
                    print(f"Unable to find system '{sys_name}'!")
                    exit(1)
                for cfg in sys["options"]:
                    self.__cfg_recursive(cfg)
    def __add_sets(self, sets):
        lst = sets.split(",")
        for s in lst:
            if (self.__get_system(s)):
                self._add_system(s)
            elif (not (s in self.sets)):
                print(f"Unable to find set '{s}'!")
                exit(1)
            else:
                self.__add_set(s)
    def __apply_defconfig(self, cfg_name, config_set):
        cfgs = self.defconfig[cfg_name]
        # add architecture option
        self.__cfg_recursive(f"{self.arch.upper()}=y")
        # activate default configurations first
        self.__add_sets(config_set)
        for cfg in cfgs:
            # walk through all platform configs
            self.__cfg_recursive(cfg)
    def defconfig_start(self):
        self.def_cfg = []
    def defconfig_append(self, name, config_set):
        print(f"Append defconfig for '{name}'")
        self.__apply_defconfig(name, config_set)
    def defconfig_save(self, path, name):
        path = f"{path}/arch/{self.arch}/configs/{name}_defconfig"
        print(f"Save defconfig for '{name}' into '{path}'")
        f = open(path, "w")
        for opt in self.def_cfg:
            s = opt.serialize()
            if (s[0] == "#"):
                f.write(f"{s}\n")
            else:
                f.write(f"CONFIG_{s}\n")
        f.close()
    def save_defconfig(self, path, name, config_set):
        self.defconfig_start()
        self.__apply_defconfig(name, config_set)
        self.defconfig_save(path, name)

if __name__ == '__main__':
    cfg_scn = ConfigScan("arm64")
    cfg_scn.scan("%{common_dir}%/kernel")
    cfg_scn.save()

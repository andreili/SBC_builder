#!/bin/python
import re, json, os.path, fnmatch
from rich.progress import Progress

r_kc_source = re.compile(r'^source\s+\"(\S+)/Kconfig\"$')
r_kc_cfg_start = re.compile(r'^config\s+(\S+)$')
r_kc_cfg_body = re.compile(r'^\t(.+)$')
r_kc_opt_dep = re.compile(r'depends on (.+)$')
r_kc_opt_cond = re.compile(r'(\|\|)|(&&)|(!)|(\()|(\))|(\S+)')
r_kc_cfg_if = re.compile(r'^if (\S+)$')
r_kc_cfg_endif = re.compile(r'^endif$')

r_km_obj_mask = r'[\w\.\-/]+'
r_km_ignores = r'(?!.*flags)(?!.*flag)(?!^#)'
r_km_obj_cfg = re.compile(r_km_ignores + r'^\S+-(?:y|\$\(CONFIG_(\S+)\))\s*[:\+]=((?: ' + r_km_obj_mask + r')+)')
r_km_obj_lst = re.compile(r'^(\s+)((?: ' + r_km_obj_mask + r')+)')
r_km_obj_not_allowed = re.compile(r'(tests\/)')
r_km_comp = re.compile(r'\.compatible = \"(\S+)\",')

r_dt_inc = re.compile(r'#include \"(\S+\.dtsi)\"')
r_dt_parent = re.compile(r'(\S+) {$')
r_dt_comp1 = re.compile(r'(compatible = \")')
r_dt_comp2 = re.compile(r'(?:\"(\S+)\")+')
r_dt_skip = [
    "arm,cortex-*",
    "cache"
]

class ConfigCondition:
    def __init__(self, line):
        self.opt_str = ""
        self.is_not = False
        self.is_or = False
        self.is_and = False
        self.is_br_op = False
        self.is_br_cl = False
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
            self.opt_str = line
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
        else:
            return self.opt_str

class ConfigOpt:
    def __init__(self, name):
        self.name = name
        self.deps = []
    def opt_body_parse(self, body, if_opt):
        if ((len(self.deps) == 0) and (if_opt != "")):
            # global "if..endif" into Kconfig
            self.deps.append(ConfigCondition(if_opt))
        m_dep = r_kc_opt_dep.match(body)
        if (m_dep):
            dep = m_dep[1]
            if (dep[0] == '$'):
                return
            if (len(self.deps) != 0):
                # not a first dependency - use AND
                self.deps.append(ConfigCondition("&&"))
            self.deps.append(ConfigCondition("("))
            m_cond = r_kc_opt_cond.findall(dep)
            for cond in m_cond:
                for cc in cond:
                    if (cc == ""):
                        # empty match - skip
                        continue
                    if (cc == "#"):
                        # commentary - end of options
                        break
                    self.deps.append(ConfigCondition(cc))
            self.deps.append(ConfigCondition(")"))
    def serialize(self):
        deps = ""
        for dep in self.deps:
            deps += dep.serialize();
        return { "name":self.name,
                 "deps":deps }
    def deserialize(self, js):
        self.name = js["name"]
        for d in js["deps"]:
            dep = ConfigCondition(d)
            #dep.deserialize(d)
            self.deps.append(dep)

class ConfigScan:
    def __init__(self, arch):
        self.arch = arch
        self.opts = []
        self.incl_path = []
        self.sources = []
        self.compatible = []
        self.vars = [
            [ "SRCARCH", self.arch ],
        ]
    def __parse_variables(self, string):
        while True:
            for var_d in self.vars:
                string = string.replace("$("+var_d[0]+")", str(var_d[1]))
            if not re.compile(r'$\(\S+\)').match(string):
                break
        return string
    def __find_opt(self, name):
        for opt in self.opts:
            if (opt.name == name):
                return opt
        return None
    def __scan_kconfig(self, path, sub_dir=""):
        full_path = f"{path}/{sub_dir}"
        if_opt = ""
        if (sub_dir == ""):
            print(f"Start scanning for options, directory '{full_path}'...")
        f = open(f"{full_path}/Kconfig", "rt")
        while (f):
            line = f.readline()
            if (line == ""):
                # EOF detector
                break
            m_source = r_kc_source.match(line)
            if (m_source):
                # current line - include another config
                inc_parsed = self.__parse_variables(m_source[1])
                if (sub_dir == ""):
                    # for root Kconfig - add all include patches
                    self.incl_path.append({ "path":inc_parsed, "cond":"" })
                self.__scan_kconfig(path, inc_parsed)
            m_cfg = r_kc_cfg_start.match(line)
            if (m_cfg):
                # read required lines and pass to parser
                opt_name = m_cfg[1]
                opt = ConfigOpt(opt_name)
                while (1):
                    ll = f.readline()
                    if ((ll == "") or (ll == "\n")):
                        # EOF detector
                        break
                    m_body = r_kc_cfg_body.match(ll)
                    if (m_body):
                        opt.opt_body_parse(m_body[1], if_opt)
                self.opts.append(opt)
            # processing for "if..endif" into Kconfig
            m_if = r_kc_cfg_if.match(line)
            if (m_if):
                if_opt = m_if[1]
            m_endif = r_kc_cfg_endif.match(line)
            if (m_endif):
                if_opt = ""
        f.close()
    def __do_makefile_fn(self, path, sub_dir, cond, fn):
        if (fn.endswith("/")):
            # include subdirectory
            self.__scan_makefiles(path, f"{sub_dir}/{fn[:-1]}", cond)
        else:
            # object file name - add to list
            self.sources.append({ "path":f"{sub_dir}/{fn[:-2]}.c",
                                  "cond":cond})
    def __do_makefile_line(self, f, path, sub_dir, cond, line, rec=False):
        if (rec):
            m_obj_cfg = r_km_obj_lst.findall(line)
        else:
            m_obj_cfg = r_km_obj_cfg.findall(line)
        if (len(m_obj_cfg) == 0):
            # can't find any valid elements, skip
            return
        m_obj_cfg = m_obj_cfg[0]
        cond_loc = ""
        #print(m_obj_cfg)
        if ((not rec) and (m_obj_cfg[0] != "")):
            cond_loc = m_obj_cfg[0]
        else:
            cond_loc = cond
        obj = m_obj_cfg[1][1:]
        #print(f":{cond_loc}:{obj}:{line[-2]}:")
        if (obj != ""):
            #print(obj)
            objs = obj.split(" ")
            for o in objs:
                self.__do_makefile_fn(path, sub_dir, cond_loc, o)
        if ((not rec) and (line[-2] == "\\")):
            # slash - need to scan next line
            while (1):
                line = f.readline()
                if (len(line) < 3):
                    break
                self.__do_makefile_line(f, path, sub_dir, cond_loc, line, True)
                if (line[-2] != "\\"):
                    break
    def __scan_makefiles(self, path, sub_dir="", cond=""):
        full_path = f"{path}/{sub_dir}"
        #print(f"\tDir: {full_path}")
        mk_fn1 = f"{full_path}/Makefile"
        mk_fn2 = f"{full_path}/Kbuild"
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
            if (r_km_obj_not_allowed.match(line)):
                continue
            self.__do_makefile_line(f, path, sub_dir, cond, line)
        f.close()
    def __scan_compatible(self, path):
        progress = Progress()
        progress.start()
        task = progress.add_task("Scanning object files...", total=len(self.sources))
        for obj in self.sources:
            progress.update(task, advance=1)
            fn = f"{path}/{obj["path"]}"
            if (not os.path.isfile(fn)):
                continue
            f = open(fn, "r")
            while (1):
                line = f.readline()
                if (line == ""):
                    # EOF detector
                    break
                m_o = r_km_comp.findall(line)
                if (len(m_o) > 0):
                    self.compatible.append({
                        "val": m_o[0],
                        "cond": obj["cond"]
                    })
            f.close()
        progress.stop()
    def __find_comp(self, val):
        for comp in self.compatible:
            if (comp["val"] == val):
                return comp
        # check to skip list
        for sk in r_dt_skip:
            if (fnmatch.fnmatch(val, sk)):
                return {"val":"", "cond":""}
        print(f"Unable to find compatible '{val}', exit!")
        exit(1)
    def __parse_dts(self, dir, fn):
        f = open(fn, "r", encoding='ISO-8859-1')
        par = ""
        while (1):
            line = f.readline()
            if (line == ""):
                # EOF detector
                break
            m_inc = r_dt_inc.match(line)
            if (m_inc):
                new_fn = f"{dir}/{m_inc[1]}"
                if (not os.path.isfile(new_fn)):
                    print(f"Unable to find inlude file '{m_inc[1]}'")
                else:
                    self.__parse_dts(dir, new_fn)
            m_par = r_dt_parent.findall(line)
            if (m_par):
                par = m_par[0]
            if (par == '/'):
                # skip root node properties
                continue
            if (r_dt_comp1.findall(line)):
                m_comp = r_dt_comp2.findall(line)
                for comp in m_comp:
                    #find compatible and opt
                    c = self.__find_comp(comp)
                    if (c["cond"] != ""):
                        self.def_opts.append(c["cond"])
        f.close()
    def __find_dts(self, dir):
        for dir_i in os.listdir(dir):
            fn = f"{dir}/{dir_i}"
            if (os.path.isfile(fn)):
                # file
                self.dts_fn.append([dir, fn])
            else:
                # recursive on directories
                self.__find_dts(fn)
    def __scan_dts(self):
        progress = Progress()
        progress.start()
        task = progress.add_task("DTS files", total=len(self.dts_fn))
        for dts_el in self.dts_fn:
            self.def_opts = []
            self.__parse_dts(dts_el[0], dts_el[1])
            progress.update(task, advance=1)
        progress.stop()
    def scan_dts(self, path):
        self.dts_fn = []
        self.__find_dts(f"{path}/arch/{self.arch}/boot/dts")
        self.__scan_dts()
    def scan(self, path):
        print("Step #1 - Scan Kconfig files")
        self.__scan_kconfig(path, "")
        print("Step #2 - Scan Makefile for source files")
        for inc in self.incl_path:
            self.__scan_makefiles(path, inc["path"], inc["cond"])
        print("Step #3 - Scan 'compatible' strings")
        self.__scan_compatible(path)
        print("Step #4 - Scan DTS and make defconfigs")
        self.scan_dts(path)
    def serialize(self):
        opts = []
        for opt in self.opts:
            opts.append(opt.serialize())
        obj = { "arch":self.arch,
                "compatible":self.compatible,
                "opts":opts }
        return obj
    def deserialize(self, js):
        self.arch = js["arch"]
        self.compatible = js["compatible"]
        for o in js["opts"]:
            opt = ConfigOpt("")
            opt.deserialize(o)
            self.opts.append(opt)
    def save(self, path):
        f = open(path, "w")
        json.dump(self.serialize(), f, indent=1)
        f.close()
    def load(self, path):
        with open(path) as json_data:
            js_data = json.load(json_data)
            self.deserialize(js_data)
            json_data.close()

if __name__ == '__main__':
    cfg_scn = ConfigScan("arm64")
    cfg_scn.scan("/home/andreil/universal/build/common/kernel")
    cfg_scn.save("./config/kernel_cfg.json")

#!/bin/python
import re

r_kc_source = re.compile(r'^source\s+\"(\S+)/Kconfig\"$')
r_kc_cfg_start = re.compile(r'^config\s+(\S+)$')
r_kc_cfg_body = re.compile(r'^\t(.+)$')
r_kc_opt_dep = re.compile(r'depends on (.+)$')
r_kc_opt_cond = re.compile(r'(\|\|)|(&&)|(!)|(\()|(\))|(\S+)')

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


class ConfigOpt:
    def __init__(self, name):
        self.name = name
        self.deps = []
    def opt_body_parse(self, body):
        m_dep = r_kc_opt_dep.match(body)
        if (m_dep):
            dep = m_dep[1]
            m_cond = r_kc_opt_cond.findall(dep)
            for cond in m_cond:
                if (cond == "#"):
                    # commentary - end of options
                    break
                self.deps.append(ConfigCondition(cond))
            #print(f"Opt '{self.name}' depends on: '{m_dep[1]}'")

class ConfigScan:
    def __init__(self, arch):
        self.arch = arch
        self.opts = []
        self.incl_path = []
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
        if (sub_dir == ""):
            print(f"Start scanning for options, directory '{full_path}'...")
        self.incl_path.append(full_path)
        f = open(f"{full_path}/Kconfig", "rt")
        while (f):
            line = f.readline()
            if (line == ""):
                # EOF detector
                break
            m_source = r_kc_source.match(line)
            m_cfg = r_kc_cfg_start.match(line)
            if (m_source):
                # current line - include another config
                inc_parsed = self.__parse_variables(m_source[1])
                #print(f"\tSource file linked: {inc_parsed}")
                self.__scan_kconfig(path, inc_parsed)
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
                        opt.opt_body_parse(m_body[1])
                self.opts.append(opt)
        f.close()
    def scan(self, path):
        print("Step #1 - Scan Kconfig files")
        self.__scan_kconfig(path, "")

if __name__ == '__main__':
    cfg_scn = ConfigScan("arm64")
    cfg_scn.scan("/home/andreil/universal/build/common/kernel")

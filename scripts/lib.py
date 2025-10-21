import os
from pathlib import Path

ROOT_DIR=Path(os.path.abspath(__file__)).parent.parent
CONFIG_DIR=f"{ROOT_DIR}/config"
BUILD_DIR=f"{ROOT_DIR}/build"
OUT_DIR=f"{ROOT_DIR}/out"
__variables = []

def add_var(key, value):
    __variables.append([key, value])

def add_vars(lst):
    for var_def in lst:
        __variables.append(var_def.split(":"))

def parse_variables(string):
    finded = True
    while finded:
        finded = False
        for var_d in __variables:
            s_var = "%{"+var_d[0]+"}%"
            if (s_var in string):
                finded = True
                string = string.replace(s_var, str(var_d[1]))
    return string

def marker_check(name, board):
    name = parse_variables(name)
    print(f"Checking marker: {name}")
    fn = f"{BUILD_DIR}/.{name}_marker"
    marker = Path(fn)
    if (marker.is_file()):
        return True
    return False

def marker_set(name, board):
    name = parse_variables(name)
    fn = f"{BUILD_DIR}/.{name}_marker"
    Path(fn).touch()

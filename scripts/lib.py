import os
from pathlib import Path

ROOT_DIR=Path(os.path.abspath(__file__)).parent.parent
CONFIG_DIR=f"{ROOT_DIR}/config"
BUILD_DIR=f"{ROOT_DIR}/build"
OUT_DIR=f"{ROOT_DIR}/out"

def marker_check(name, board):
    name = board.parse_variables(name)
    print(f"Checking marker: {name}")
    fn = f"{BUILD_DIR}/.{name}_marker"
    marker = Path(fn)
    if (marker.is_file()):
        return True
    return False

def marker_set(name, board):
    name = board.parse_variables(name)
    fn = f"{BUILD_DIR}/.{name}_marker"
    Path(fn).touch()

import os
from pathlib import Path

ROOT_DIR=Path(os.path.abspath(__file__)).parent.parent

def marker_check(name):
    fn = f"{ROOT_DIR}/build/.{name}_marker"
    marker = Path(fn)
    if (marker.is_file()):
        return True
    return False

def marker_set(name):
    fn = f"{ROOT_DIR}/build/.{name}_marker"
    Path(fn).touch()

import json, os
from pathlib import Path
from . import *

class Software:
    def __init__(self):
        js_fn = f"{ROOT_DIR}/config/software.json"
        with open(js_fn) as json_data:
            json = json.load(json_data)
            json_data.close()
        self.user = json["user"]

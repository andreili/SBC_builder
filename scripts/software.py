import json, os
from pathlib import Path
from . import *

class Software:
    def __init__(self, os):
        self.os = os
        js_fn = f"{ROOT_DIR}/config/software.json"
        with open(js_fn) as json_data:
            js = json.load(json_data)
            json_data.close()
        self.user = js["user"]
    
    def finalize(self, dir):
        cmd_user = f"useradd -m -G wheel,video,audio,disk,usb {self.user} --password {self.user}"
        cmd_klipper = "sudo klipper 'cd ~ && git clone https://github.com/dw-0/kiauh.git --depth=1'"
        cmd_venv = "sudo klipper 'cd ~ && python -m venv ~/venv'"
        self.os.chroot_ext(cmd_user, dir)
        self.os.chroot_ext(cmd_klipper, dir)
        self.os.chroot_ext(cmd_venv, dir)

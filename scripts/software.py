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
        self.user_groups = js["user_groups"]
        self.repos = js["repos"]
        self.make_venv = js["make_venv"]
    
    def finalize(self, dir):
        home_dir = f"/home/{self.user}"
        cmds = []
        # create user
        cmds.push_back(f"useradd -m -G {self.user_groups} {self.user} --password {self.user}")
        #make password for user
        cmds.push_back(f"echo '{self.user}:{self.user}' | chpasswd")
        for repo in self.repos:
            #clone repos from configuration
            repo_dir = repo["directory"]
            repo_url = repo["url"]
            cmds.push_back(f"sudo -i -u klipper git clone {repo_url} --depth=1 {home_dir}/{repo_dir}")
        if (self.make_venv):
            # make python environment
            cmds.push_back(f"sudo -i -u klipper python -m venv {home_dir}/venv")
        for cmd in cmds:
            self.os.chroot_ext(cmd, dir)

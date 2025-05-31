from pathlib import Path
import shutil, git, os, subprocess, glob
from rich import console, progress
from .logger import Logger

ROOT_DIR = Path(os.path.abspath(__file__)).parent.parent

class GitRemoteProgress(git.RemoteProgress):
    OP_CODES = [
        "BEGIN",
        "CHECKING_OUT",
        "COMPRESSING",
        "COUNTING",
        "END",
        "FINDING_SOURCES",
        "RECEIVING",
        "RESOLVING",
        "WRITING",
    ]
    OP_CODE_MAP = {
        getattr(git.RemoteProgress, _op_code): _op_code for _op_code in OP_CODES
    }

    def __init__(self) -> None:
        super().__init__()
        self.progressbar = progress.Progress(
            progress.SpinnerColumn(),
            # *progress.Progress.get_default_columns(),
            progress.TextColumn("[progress.description]{task.description}"),
            progress.BarColumn(),
            progress.TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            "eta",
            progress.TimeRemainingColumn(),
            progress.TextColumn("{task.fields[message]}"),
            console=console.Console(),
            transient=False,
        )
        self.progressbar.start()
        self.active_task = None

    def __del__(self) -> None:
        # logger.info("Destroying bar...")
        self.progressbar.stop()

    @classmethod
    def get_curr_op(cls, op_code: int) -> str:
        """Get OP name from OP code."""
        # Remove BEGIN- and END-flag and get op name
        op_code_masked = op_code & cls.OP_MASK
        return cls.OP_CODE_MAP.get(op_code_masked, "?").title()

    def update(
        self,
        op_code: int,
        cur_count: str | float,
        max_count: str | float | None = None,
        message: str | None = "",
    ) -> None:
        # Start new bar on each BEGIN-flag
        if op_code & self.BEGIN:
            self.curr_op = self.get_curr_op(op_code)
            # logger.info("Next: %s", self.curr_op)
            self.active_task = self.progressbar.add_task(
                description=self.curr_op,
                total=max_count,
                message=message,
            )

        self.progressbar.update(
            task_id=self.active_task,
            completed=cur_count,
            message=message,
        )

        # End progress monitoring on each END-flag
        if op_code & self.END:
            # logger.info("Done: %s", self.curr_op)
            self.progressbar.update(
                task_id=self.active_task,
                message=f"[bright_black]{message}",
            )

class Sources:
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.bare_dir = f"{ROOT_DIR}/bare_git/{name}"
        self.bare_done_marker = f"{self.bare_dir}/.git_done_marker"

    def init_source_path(self, board_name):
        self.board_name = board_name
        self.worktree = f"{self.name}_{board_name}"
        self.worktree_dir = f"{self.bare_dir}/.git/worktrees/{self.worktree}"
        self.work_dir = f"{ROOT_DIR}/build/{board_name}/{self.worktree}"
        self.work_done_marker = f"{self.work_dir}/.git_done_marker"

    def set_git_params(self, version, _type):
        self.version = version
        self.type = _type

    def sync(self):
        self.git_bare_check()
        self.git_work_clone()
        #git_bare_check "${git_url}" "${git_dir}"
        #git_bare_clone "${git_dir}" "${git_work}" "${git_tag}"
        #source_patch "${patch_dir}" ${source_dir}

    def git_bare_clone(self):
        Logger.download(f"\tClone dedicated repo '{self.url}'")
        git.Repo.clone_from(self.url, self.bare_dir, multi_options=["--tags", "--no-checkout"],
            progress=GitRemoteProgress())
        repo = git.Repo(self.bare_dir)
        cfg_wr = repo.config_writer()
        cfg_wr.add_value("remote \"origin\"", "fetch", "+refs/tags/*:refs/remotes/origin/*").release()
        Path(self.bare_done_marker).touch()

    def git_bare_check(self):
        Logger.git(f"Check a bare repo for '{self.name}'")
        bare_dir = Path(self.bare_dir)
        bare_marker = Path(self.bare_done_marker)
        if (not bare_dir.is_dir()) or (not bare_marker.is_file()):
            if (bare_dir.is_dir()):
                Logger.git("\tRemove GIT bare directory - don't find 'finish' marker!")
                shutil.rmtree(self.bare_dir)
            self.git_bare_clone()
        Logger.download("\tFetch updates from dedicated repo")
        git.Repo(self.bare_dir).remote("origin").fetch(progress=GitRemoteProgress())

    def git_work_tree_init(self):
        if (not Path(f"{self.work_dir}/.git").is_file()):
            Logger.git("\tAdd to worktree")
            self.repo_bare.git.worktree("add", self.work_dir, "master", "--no-checkout", "--force")
        git_rel_dir = os.path.relpath(self.worktree_dir, start=self.work_dir)
        with open(f"{self.work_dir}/.git", 'w') as f:
            f.write(f"gitdir: {git_rel_dir}")
            f.close()
        with open(f"{self.worktree_dir}/gitdir", 'w') as f:
            f.write(f"{self.work_dir}/.git")
            f.close()

    def git_work_get_hash_remote(self):
        if (self.type == "branch"):
            exit(1)
        elif (self.type == "head"):
            exit(1)
        elif (self.type == "commit"):
            exit(1)
        elif (self.type == "tag"):
            tags = self.repo_bare.git.ls_remote("--tags", "origin", f"tags/{self.version}")
            return tags.split('\t')[0]

    def git_work_reset_state(self):
        hash_local = self.repo.git.rev_parse("@")
        hash_remote = self.git_work_get_hash_remote()
        if (hash_local == "") or (hash_local == "@") or (hash_local != hash_remote):
            Logger.git(f"\tUpdate references: {hash_local}->{hash_remote}")
            self.repo.git.fetch("--no-tags", self.bare_dir, self.version)
            #git fetch --no-tags "${repo_local}" "${ref_name}"
        Logger.git(f"\tCheckout: {hash_remote}")
        self.repo.git.checkout("-f", "-q", hash_remote)
        Logger.git(f"\tClean-up")
        self.repo.git.clean("-q", "-d", "-f")

    def git_work_clone(self):
        Logger.git(f"Update and reset work repo '{self.name}' '{self.version}'")
        self.repo_bare = git.Repo(self.bare_dir)
        work_marker = Path(self.work_done_marker)
        if (not work_marker.is_file()):
            Logger.git("\tRemove GIT work directory - don't find 'finish' marker!")
            shutil.rmtree(self.work_dir, ignore_errors=True)
        self.git_work_tree_init()
        self.repo = git.Repo(self.work_dir)
        self.git_work_reset_state()
        Path(self.work_done_marker).touch()

    def __patch_apply(self, file, work_dir):
        patch_bn = os.path.basename(file)
        Logger.build(f"\tApply patch '{patch_bn}'")
        p = subprocess.Popen(["patch", "--batch", "-p1", "-N",
            f"--input={file}", "--quiet"], cwd=work_dir)
        p.wait()

    def do_patch(self, board_name, dir):
        Logger.build(f"Patch...")
        dirs = [
            f"{ROOT_DIR}/patch/{dir}/..",
            f"{ROOT_DIR}/patch/{dir}",
            f"{ROOT_DIR}/patch/{dir}/board_{board_name}"
        ]
        for dir_p in dirs:
            conf_fn = f"{dir_p}/series.conf"
            conf_f = Path(conf_fn)
            if (conf_f.is_file()):
                with open(conf_fn, 'r') as f:
                    for line in f:
                        if (len(line)>10) and (line[0] != "#") and (line[0] != "-"):
                            file_n = line.strip()
                            self.__patch_apply(f"{dir_p}/{file_n}", self.work_dir)
                    f.close()
            for patch_file in Path(dir_p).glob('*.patch'):
                self.__patch_apply(patch_file, self.work_dir)

    def compile(self, opts, cfg_name):
        #print(f"opts:{opts} target:{target}")
        Logger.build(f"Compile...")
        work_cfg_name = f"{self.work_dir}/.config"
        cfg_or = Path(cfg_name)
        cfg_wr = Path(cfg_name)
        if (cfg_or.is_file()):
            # copy configuration, if exists
            shutil.copyfile(cfg_name, work_cfg_name)
        opts.insert(0, "make")
        opts.append("-j16")
        p = subprocess.Popen(opts, cwd=self.work_dir)
        p.wait()
        if (p.returncode != 0):
            Logger.error("Failed to compile!")
        if (cfg_or.is_file()):
            # backup old configuration
            shutil.copyfile(cfg_name, f"{cfg_name}.bak")
        if (cfg_wr.is_file()):
            # copy new configurtion, if exists
            shutil.copyfile(work_cfg_name, cfg_name)

    def copy_artifacts(self, artifacts, out_dir):
        for art in artifacts:
            file_name = self.work_dir + "/" + art["file"]
            if ("subdir" in art):
                dir_o = out_dir + "/" + art["subdir"] + "/"
            else:
                dir_o = out_dir + "/"
            os.makedirs(dir_o, exist_ok=True)
            if (file_name.find("*") == -1):
                shutil.copy(file_name, dir_o)
            else:
                for file in glob.glob(file_name):
                    shutil.copy(file, dir_o)

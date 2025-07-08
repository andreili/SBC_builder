#!/bin/python
import sys, os, subprocess

def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

class Tree:
    def __init__(self):
        self.childs = []
        self.size = 0
        self.name = ""

    def add(self, fn, size):
        path = fn.split("/")
        if (len(path) == 1):
            ch = Tree()
            ch.name = path[0]
            ch.size = size
            self.size += size
            self.childs.append(ch)
            return
        for ch in self.childs:
            if (ch.name == path[0]):
                ch.add("/".join(path[1:]), size)
                self.size += size
                return
        ch = Tree()
        ch.name = path[0]
        ch.add("/".join(path[1:]), size)
        self.size += size
        self.childs.append(ch)

    def print(self, level, level_max, minsz):
        self.childs = sorted(self.childs, key=lambda x: x.size, reverse=True)
        if (level > level_max) or (self.size == 0) or (self.size < minsz):
            return
        s = "\t" * level
        sz = sizeof_fmt(self.size)
        s += f"+[{sz}] {self.name}"
        print(s)
        for ch in self.childs:
            ch.print(level + 1, level_max, minsz)

path = sys.argv[1]
bn = os.path.dirname(path)
root = Tree()
root.name = "."
p = subprocess.Popen(f"size {path}", shell=True, stdout=subprocess.PIPE)
for line in p.stdout:
    parts = line.split()
    if (parts[0] == b'text'):
        continue
    size = parts[3]
    fn = parts[5].decode("utf-8").replace(f"{bn}/", "")
    root.add(fn, int(size))
root.print(0, 3, 1024*80)

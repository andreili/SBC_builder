#!/bin/python

import argparse, json
from scripts import *

os = OS()
#os.umount_safe()
os_actions = ",".join(os.actions_list())
targets = "uboot,kernel,initramfs"

parser = argparse.ArgumentParser()
parser.add_argument('--board', type=str, default='', help='Select board to build')
parser.add_argument('--target', type=str, default='', help=f'Target to build, default "{targets}".' +
    ' Kernel target supports sub-targets: "kernel-defconfig,kernel-config"')
parser.add_argument('--sync', action='store_true', help='Sync all source with latest')
parser.add_argument('--kernel-sync', action='store_true', help='Sync all kernel drivers with DTS')
parser.add_argument('--os_act', type=str, default='', help=f'Actions to OS ({os_actions}), comma separated list')
parser.add_argument('--install', type=str, default='', help='Install to selected directory/device')
args = parser.parse_args()

if (args.board == ''):
    parser.print_help()
    exit(1)

targets_meta = Target.load_meta(f"config/target_meta.json")
target_board = Board(args.board, f"config/board/{args.board}.json", targets_meta)
os.set_board(target_board)
os.load_info()

os.check_rootfs()

if (args.sync):
    target_board.sync()
elif (args.target != ""):
    if (args.target == "initramfs"):
        init = Initramfs()
        init.build(os)
    else:
        if (args.kernel_sync):
            target_board.sync_kernel()
        target_board.build(args.target)

if (args.os_act != ""):
    acts = args.os_act.split(",")
    for act in acts:
        os.action(act)

if (args.install != ""):
    os.install(args.install)

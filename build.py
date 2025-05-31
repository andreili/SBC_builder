#!/bin/python

import argparse, json
from scripts import *

parser = argparse.ArgumentParser()
parser.add_argument('--board', type=str, default='', help='Select board to build')
parser.add_argument('--target', type=str, default='all', help='Target to build, default "%(default)s"')
parser.add_argument('--sync', action='store_true', help='Sync all source with latest')
args = parser.parse_args()

if (args.board == ''):
    parser.print_help()
    exit(1)

targets_meta = Target.load_meta(f"config/target_meta.json")
target_board = Board(args.board, f"config/board/{args.board}.json", targets_meta)

if (args.sync):
    target_board.sync()
else:
    target_board.build(args.target)

#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import trio


import argparse
import argcomplete


def ws_from_controller(args):
    ws = trio.Workspace(trio.Trio(args.ip))
    ws.new_from_controller(args.wsfile, folder=args.folder, delete=args.delete)


parser = argparse.ArgumentParser(description="Trio Workspace handling")
parser.add_argument('--ip', type=str, help="Controller IP/hostname")

subparsers = parser.add_subparsers()


# `ws` subcommand

ws_parser = subparsers.add_parser('ws_from_controller')
ws_parser.add_argument('wsfile', type=str, help="Create workspace from controller")
ws_parser.add_argument('--folder', default=None, help="Folder in which to create the workspace, default cwd")
ws_parser.add_argument('--delete', action='store_true', help="Delete extra files in the local folder")
ws_parser.set_defaults(func=ws_from_controller)




argcomplete.autocomplete(parser)

args = parser.parse_args()
if 'func' in args.__dict__:
    args.func(args)
else:
    parser.print_usage()

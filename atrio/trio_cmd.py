#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import atrio

import argparse
import argcomplete


def construct_trio(args):
    return atrio.Trio(args.ip, args.trace)


def construct_workspace(args):
    ws = atrio.Workspace(construct_trio(args))
    return ws


def controller_cmd(args):
    t = construct_trio(args)
    print(t.commandS(' '.join(args.command)))


def controller_list(args):
    t = construct_trio(args)
    return atrio.prettyprint_progtable(t.list_files())


def controller_show(args):
    t = construct_trio(args)
    print(t.read_program(atrio.program_from_filename(args.progname, allow_progname=True)[0]))


def controller_restart(args):
    t = construct_trio(args)
    return t.restart()


def controller_halt(args):
    t = construct_trio(args)
    return t.halt()


def ws_create(args):
    ws = construct_workspace(args)
    return ws.new_from_controller(args.wsfile, args.folder)


def ws_check(args):
    ws = construct_workspace(args)
    ws.load(args.wsfile)
    return ws.check_controller_filelist(check_extra=args.check_extra)


def ws_upload(args):
    ws = construct_workspace(args)
    ws.load(args.wsfile)
    return ws.write_to_controller(args.clear)


def ws_from_controller(args):
    ws = construct_workspace(args)
    return ws.new_from_controller(args.wsfile, folder=args.folder, delete=args.delete)

def ws_download(args):
    ws = construct_workspace(args)
    return ws.update_from_controller(args.wsfile, interactive=True)


"""
---
atrio --ip <controllerIP> [--trace] <subcommand>

atrio cmd <trio cmd>
atrio list
atrio show <prog>


- bonus :
atrio download <prog> [<file>]
atrio download --all

atrio upload <file> [<file> [...]]
atrio autorun <prog> <proc>

atrio ethercat ....


---

atrio ws create <wsfile> [--folder=<folder>] [--delete]
atrio ws check <wsfile> [--check_extra]
atrio ws upload <wsfile> [--delete]

- bonus :
atrio ws download --delete=false
atrio ws sync --interactive=true


"""


def main():

    parser = argparse.ArgumentParser(description="Trio controller management tool")
    parser.add_argument('--ip', type=str, help="Controller IP/hostname")
    parser.add_argument('--trace', action='store_true', help="Enable tracing of all interaction with the controller.")

    subparsers = parser.add_subparsers()

    cmd_parser = subparsers.add_parser('cmd', help="Execute a trio command like ?version or 'ethercat(0,0)'")
    cmd_parser.add_argument('command', type=str, nargs='+', help="Command to give to the drive")
    cmd_parser.set_defaults(func=controller_cmd)

    list_parser = subparsers.add_parser('list', help="List files in the controller")
    list_parser.set_defaults(func=controller_list)

    show_parser = subparsers.add_parser('show', help="Display a file from the controller")
    show_parser.add_argument('progname', type=str, help="Programe name to show")
    show_parser.set_defaults(func=controller_show)

    restart_parser = subparsers.add_parser('restart', help="Restart the controller (special call to EX)")
    restart_parser.set_defaults(func=controller_restart)

    halt_parser = subparsers.add_parser('halt', help="Halt programs in the controller ensuring communication channel is clean")
    halt_parser.set_defaults(func=controller_halt)

    # `ws` subcommand

    ws_parser = subparsers.add_parser('ws', help="Workspace management subcommands")
    ws_parser.add_argument('wsfile', type=str, help="Workspace yaml file")

    ws_sub_parsers = ws_parser.add_subparsers()

    ws_create_parser = ws_sub_parsers.add_parser('create', help="Create a workspace from the controller")
    ws_create_parser.add_argument('--folder', default=None,
                                  help="Folder in which to create the workspace, default same as wsfile")
    ws_create_parser.set_defaults(func=ws_create)


    ws_check_parser = ws_sub_parsers.add_parser('check', help="Check workspace is in sync with the controller")
    ws_check_parser.add_argument('--check_extra', action="store_true",
                                 help="Check for extra files in the controller")
    ws_check_parser.set_defaults(func=ws_check)


    ws_upload_parser = ws_sub_parsers.add_parser('upload', help="Upload workspace to the controller")
    ws_upload_parser.add_argument('--clear', action="store_true",
                                  help="Start from scratch removing everything in the controller first")
    ws_upload_parser.set_defaults(func=ws_upload)

    ws_download_parser = ws_sub_parsers.add_parser('download', help="Download changes from the controller")
    ws_download_parser.set_defaults(func=ws_download)




    # ws_parser.add_argument('--folder', default=None, help="Folder in which to create the workspace, default cwd")
    
    # ws_parser.add_argument('--delete', action='store_true', help="Delete extra files in the local folder")
    # ws_parser.set_defaults(func=ws_from_controller)



    argcomplete.autocomplete(parser)

    args = parser.parse_args()
    if 'func' in args.__dict__:
        return args.func(args)
    else:
        return parser.print_usage()


if __name__ == "__main__":
    exit(main())

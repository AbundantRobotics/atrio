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
    output = t.commandS(' '.join(args.command))
    if output:
        print(output)


def controller_ls(args):
    t = construct_trio(args)
    return atrio.prettyprint_progtable(t.list_files())

def controller_top(args):
    t = construct_trio(args)
    print(t.process_load())

def controller_ethercat(args):
    t = construct_trio(args)
    print(getattr(t, 'ethercat_' + args.subfunc)())

def controller_ethercat_set(args):
    t = construct_trio(args)
    s = atrio.EthercatState[args.state]
    t.ethercat_set_state(s)
    print(t.ethercat_list())



def controller_show(args):
    t = construct_trio(args)
    print(t.read_program(atrio.program_from_filename(args.progname, allow_progname=True)[0]))


def controller_restart(args):
    t = construct_trio(args)
    return t.restart(wait=not args.no_wait)


def controller_halt(args):
    t = construct_trio(args)
    return t.halt()


def ws_create(args):
    ws = construct_workspace(args)
    return ws.new_from_controller(args.wsfile, args.folder)


def ws_check(args):
    ws = construct_workspace(args)
    ws.load(args.wsfile)
    diff = ws.controller_diff()
    return ws.summarize_diff(diff, print_summary=True, ignore_extras=args.no_extra, print_diff=not args.no_diff)


def ws_upload(args):
    ws = construct_workspace(args)
    ws.load(args.wsfile)
    return ws.write_to_controller(clear=args.clear)


def ws_download(args):
    ws = construct_workspace(args)
    return ws.update_from_controller(args.wsfile, interactive=True)



def main():

    parser = argparse.ArgumentParser(description="Trio controller management tool")
    parser.add_argument('--drives_file', '-d', type=str,
                        help="A yaml file with each controller descriptions with field 'ip'")
    parser.add_argument('--ip', type=str, help="Controller IP/hostname")

    parser.add_argument('--trace', action='store_true', help="Enable tracing of all interaction with the controller.")
    parser.add_argument('--folder', help="Folder in which to create files, default same as wsfile")

    subparsers = parser.add_subparsers()

    cmd_parser = subparsers.add_parser('cmd', help="Execute a trio command like ?version or 'ethercat(0,0)'")
    cmd_parser.add_argument('command', type=str, nargs='+', help="Command to give to the drive")
    cmd_parser.set_defaults(func=controller_cmd)

    ls_parser = subparsers.add_parser('ls', help="List files in the controller")
    ls_parser.set_defaults(func=controller_ls)

    top_parser = subparsers.add_parser('top', help="List process and cpu usage in the controller")
    top_parser.set_defaults(func=controller_top)

    ethercat_parser = subparsers.add_parser('ethercat', help="trio ethercat commands")
    ethercat_subparsers = ethercat_parser.add_subparsers()
    for f in ["list", "state", "start", "stop"]:
        sp = ethercat_subparsers.add_parser(f)
        sp.set_defaults(subfunc=f)
        sp.set_defaults(func=controller_ethercat)
    ethercat_set_parser = ethercat_subparsers.add_parser("set_state", help='Change ethercat status')
    ethercat_set_parser.add_argument("state", choices=[str(s.name) for s in atrio.EthercatState])
    ethercat_set_parser.set_defaults(func=controller_ethercat_set)

    show_parser = subparsers.add_parser('show', help="Display a file from the controller")
    show_parser.add_argument('progname', type=str, help="Programe name to show")
    show_parser.set_defaults(func=controller_show)

    restart_parser = subparsers.add_parser('restart', help="Restart the controller (special call to EX)")
    restart_parser.add_argument('--no-wait', action='store_true', help="Do not wait for the controller to come back online")
    restart_parser.set_defaults(func=controller_restart)

    halt_parser = subparsers.add_parser('halt', help="Halt programs in the controller ensuring communication channel is clean")
    halt_parser.set_defaults(func=controller_halt)

    # `ws` subcommand

    ws_parser = subparsers.add_parser('ws', help="Workspace management subcommands")
    ws_parser.add_argument('wsfile', type=str, help="Workspace yaml file")

    ws_sub_parsers = ws_parser.add_subparsers()

    ws_create_parser = ws_sub_parsers.add_parser('create', help="Create a workspace from the controller")
    ws_create_parser.set_defaults(func=ws_create)

    ws_check_parser = ws_sub_parsers.add_parser('check', help="Check workspace is in sync with the controller")
    ws_check_parser.add_argument('--no-extra', action="store_true",
                                 help="Do not check for extra files in the controller")
    ws_check_parser.add_argument('--no-diff', action="store_true",
                                 help="Do not print full diff of files")
    ws_check_parser.set_defaults(func=ws_check)

    ws_upload_parser = ws_sub_parsers.add_parser('upload', help="Upload workspace to the controller")
    ws_upload_parser.add_argument('--clear', action="store_true",
                                  help="Start from scratch removing everything in the controller first")
    ws_upload_parser.set_defaults(func=ws_upload)

    ws_download_parser = ws_sub_parsers.add_parser('download', help="Download changes from the controller")
    ws_download_parser.set_defaults(func=ws_download)


    argcomplete.autocomplete(parser)

    args = parser.parse_args()
    if 'func' in args.__dict__:
        return args.func(args)
    else:
        return parser.print_usage()


if __name__ == "__main__":
    exit(main())

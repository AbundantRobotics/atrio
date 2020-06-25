
import yaml

from .trio import *


class Workspace:
    """ Workspace yaml file is 2 parts:
    controller:
      checksum: <checksum value>
    files:
      - { filename: <progname>, autorun: <autorun> }
      - <...>
    """
    def __init__(self, trio):
        self.trio = trio
        self.ws = None
        self.wsfiledir = Path()

    def save(self, wsfile):
        with open(wsfile, 'w') as f:
            yaml.dump(self.ws, f)

    def load(self, wsfile):
        with open(wsfile) as f:
            self.ws = yaml.load(f, Loader=yaml.Loader)
            self.wsfiledir = Path(wsfile).parent

    def entry_from_list_file(self, folder, ll):
        """ Workspace entry from a file listing entry from trio.list_files() """
        filename = folder + '/' + ll['progname'] + extension_from_code_type(ll['codetype'])
        return {'filename': filename, 'autorun': ll['autorun']}

    def load_controller(self, folder='.'):
        """ Create a workspace to match the controller one """
        files = []
        for ll in self.trio.list_files().values():
            files.append(self.entry_from_list_file(folder, ll))
        self.ws = {
            'files': files
        }

    def new_from_controller(self, wsfile, folder=None):
        """ Create a workspace from the controller content.
        Save the workspace file as wsfile, and the programs in folder.
        If folder is not given, puts the programs in the same folder as the workspace.
        If delete then clears the folder.
        """
        if folder is None:
            d = Path(wsfile).parent
        else:
            d = Path(folder)
        if not d.exists():
            d.mkdir(parents=True)

        d = d.relative_to(Path(wsfile).parent)

        self.load_controller(str(d))

        for f in self.ws.get('files', []):
            self.trio.download_file(f['filename'])

        self.save(wsfile)

    def update_from_controller(self, wsfile, interactive=False):
        """ Update the programs of the workspace """
        if interactive:
            def prompt(msg):
                r = input(msg + " Y/n?\n")
                return (r == '' or r == 'Y' or r == 'y')
        else:
            def prompt(msg):
                print(msg)
                return True

        self.load(wsfile)

        cfiles = self.trio.list_files()

        new_files = []

        for f in list(self.ws.get('files', [])):
            filename = f['filename']
            progname, prog_type = program_from_filename(f['filename'])
            autorun = f.get('autorun', None)

            if progname not in cfiles:
                print('File {} removed from the controller.'.format(filename))
                if prompt('Remove from workspace'):
                    Path(filename).unlink()
                continue

            if not self.check_controller_filecontent(filename):
                print('File {} is different'.format(filename))
                if prompt("Download form controller"):
                    self.trio.download_file(filename)

            if str(cfiles[progname]['autorun']) != str(autorun):
                print('File {} has different autorun'.format(filename))
                if prompt('Updating it'):
                    f['autorun'] = cfiles[progname]['autorun']

            new_files.append(f)
            cfiles.pop(progname)

        if cfiles:
            if prompt("Download extra files from controller"):
                for cf in cfiles.values():
                    new_file = self.entry_from_list_file('.', cf)
                    if prompt("Downloading new file {}".format(cf['progname'])):
                        self.trio.download_file(new_file['filename'])
                        new_files.append(new_file)

        self.ws['files'] = new_files

        self.save(wsfile)


    def write_to_controller(self, remove_extra=True, clear=False, auto_restart=True):
        """ Write the current workspace to the controller.
        If clear, it will clear everything in the controller before uploading.
        If remove_extra, it will remove extra files in the controller.
        """
        self.trio.halt()  # Trio will fail when there are running progs and we write some
        if clear:
            self.trio.commandS('NEW "ALL"')
            #for f in self.trio.list_files():
            #    self.trio.delete_program(f)

        cdiff = self.controller_diff()

        changed = self.summarize_diff(cdiff, print_summary=True,
                                      ignore_extras=not remove_extra, print_diff=True)

        if not changed:
            return 0

        if remove_extra:
            for p in cdiff['extra_progs']:
                self.trio.delete_program(p)

        restart_needed = False

        to_upload = cdiff['missing'] + cdiff['wrong_type'] + cdiff['different']

        for f in self.ws.get('files', []):
            filename = self.wsfiledir / f['filename']
            progname, prog_type = program_from_filename(filename)
            autorun = f.get('autorun', None)
            update_autorun = False

            if filename in to_upload:
                print(f"Updating {filename}")
                self.trio.upload_file(filename)
                if prog_type == program_types['.MCC']:
                    print(f"Restart needed after change of MC_CONFIG.MCC")
                    restart_needed = True
                elif prog_type == program_types['.BAS']:
                    update_autorun = True

            if update_autorun or filename in cdiff["autorun_changed"]:
                self.trio.autorun_program(progname, prog_type, autorun)
                if autorun:
                    print(f"Restart needed to autorun {filename}")
                    restart_needed = True

        if restart_needed and auto_restart:
            self.trio.restart()

        return 1 if restart_needed else 2


    def check_controller_filecontent(self, filename):
        """ Check that a file is the same as in the controller (using checksum).
        """
        fcrc = crc_file(filename)
        progname, prog_type = program_from_filename(filename)
        try:
            ccrc = self.trio.checksum_program(progname)
            return fcrc == ccrc
        except Exception:
            return False

    def controller_diff(self):
        if self.ws is None:
            raise AtrioError("Workspace is empty, please load a workspace.")

        cfiles = self.trio.list_files()
        extras = set(cfiles.keys())
        missing = []
        wrong_type = []
        different = []
        autorun_changed = []

        for f in self.ws.get('files', []):
            filename = self.wsfiledir / f['filename']
            progname, prog_type = program_from_filename(filename)
            if progname not in cfiles:
                missing.append(filename)
            else:
                extras.remove(progname)
                ll = cfiles[progname]
                cprog_type = program_types.get(extension_from_code_type(ll['codetype']))
                if prog_type != cprog_type:
                    wrong_type.append(filename)
                if not self.check_controller_filecontent(filename):
                    different.append(filename)
                if str(ll['autorun']) != str(f.get('autorun', None)):
                    autorun_changed.append(filename)

        return {'missing': missing, 'wrong_type': wrong_type, 'different': different,
                'autorun_changed': autorun_changed, 'extra_progs': extras}


    def summarize_diff(self, cdiff, ignore_extras=False, print_summary=False, print_diff=False):
        changed = False

        if not print_summary:
            def print(*_): pass
            def print_list(*_): pass
        else:
            def print(*args): global print; print(*args)
            def print_list(l):
                global print
                for x in l:
                    print("    " + str(x))

        if cdiff['missing']:
            changed = True
            print("Missing programs:")
            print_list(cdiff['missing'])

        if cdiff['wrong_type']:
            changed = True
            print("Programs with wrong type:")
            print_list(cdiff['wrong_type'])

        if cdiff['different']:
            changed = True
            print("Programs have changed:")
            if print_diff:
                import difflib
                for f in cdiff['different']:
                    p, _ = program_from_filename(f)
                    with open(f, 'r') as l:
                        ll = l.read().splitlines()
                    cl = self.trio.read_program(p).splitlines()
                    print(f'@@@@')
                    print_list(difflib.unified_diff(ll, cl , str(f), 'controller', n=1, lineterm=''))
            else:
                print_list(cdiff['different'])

        if cdiff['autorun_changed']:
            changed = True
            print("Programs with wrong autorun:")
            print_list(cdiff['autorun_changed'])

        if cdiff['extra_progs'] and not ignore_extras:
            changed = True
            print("Extra programs in the controller:")
            print_list(cdiff['extra_progs'])

        return changed



    def download_all(self):
        for f in self.ws.get('files', []):
            self.trio.download_file(self.wsfiledir / f['filename'])


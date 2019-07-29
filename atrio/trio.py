import re
import telnetlib
import socket
import atexit
import sys
from pathlib import Path

import yaml


program_types = {
    ".BAS": 0,
    ".TXT": 3,
    ".MCC": 9,
    ".BAL": 12,
}


def extension_from_prog_type(prog_type):
    """ Returns file extension from a trio prog_type """
    return next(k for (k, v) in program_types.items() if v == prog_type)


code_types = {
    "Normal": ".BAS",
    "BASIC Lib": ".BAL",
    "Text": ".TXT",
    "MC_CONFIG": ".MCC"
}


def extension_from_code_type(code_type):
    return code_types[code_type]


autorun_types = {
    "None": False,
    "Manual": False,
    "Power Up": False,
    "Auto\((?P<autorun>[\-\d]+)\)": True
}


progtable_regex = \
    re.compile(
        "^(?P<progname>[^\s]+)\s+(?P<source>\d+)\s+(?P<code>\d+)"
        "\s+({})"
        "\s+(?P<codetype>{})"
        .format(
            "|".join(autorun_types.keys()),
            "|".join(code_types.keys())
        ),
        re.MULTILINE
    )


def prettyprint_progtable(list_files):
    for k in list_files.values():
        autorun = k.get('autorun', None)
        if autorun:
            autorunstr = " ({})".format(autorun)
        else:
            autorunstr = ""
        print("{}{}{}".format(
            k['progname'],
            extension_from_code_type(k['codetype']),
            autorunstr)
        )


def program_from_filename(filename, allow_progname=False):
    """ Returns the trio filename and associated prog_type """
    p = Path(filename)
    extension = p.suffix.upper()
    t = program_types.get(extension)
    if not allow_progname and t is None:
        raise Exception("File {} extension is unknown".format(filename))
    return p.stem.upper(), t




import crcmod
trioCRC16 = crcmod.Crc(0x18005, initCrc=0, rev=False, xorOut=0)


def crc_lines(lines):
    """ Expect a list of lines with no endings """
    crc = trioCRC16.new()
    for l in lines:
        crc.update(l.strip(b'\r\n'))
        crc.update(b'\xaa')
    return crc.crcValue


def crc_file(filename):
    with open(filename, 'rb') as f:
        return crc_lines(f.readlines())


class Trio:
    """
    Can be used simply as an object
    (in which case it will release the telnet port only when program exits)
    or can be used in a contextmanager (`with`)
    """

    def __init__(self, ip, trace=False):
        try:
            t = telnetlib.Telnet(ip, timeout=1)
        except socket.timeout:
            t = None
        if not t:
            raise Exception("Could not connect to " + ip + ", verify that nothing is already connected to it.")
        self.t = t
        self.ip = ip
        self.name = ip
        self.trace = trace
        atexit.register(Trio.__del__, self)

        # flush the starting stuff
        self.t.write(b'\r\n\r\n')
        while self.t.read_until(b'>>', 0.1):
            pass

    def __del__(self):
        if 't' in self.__dict__:
            self.t.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.t:
            self.t.close()
        return False

    def command(self, cmd, timeout=30):
        cmd = cmd.encode('ascii')
        self.t.read_very_eager() # try to recover from past errors
        self.t.write(cmd + b'\r\n')
        if self.trace:
            print('-> ', cmd + b'\r\n')

        end_re = re.compile(b"Control char : (.*)\r\n>>", re.MULTILINE)
        (_, _, answer) = self.t.expect([end_re], timeout)
        if self.trace:
            print('<- ', answer)
        if not answer:
            raise Exception("Trio {} (cmd: {}) doesn't respond".format(self.name, repr(cmd)))
        resp = b'(.*?)\r\n(.*)>>\nControl char : (.*)\r\n>>'
        r = re.match(resp, answer, re.MULTILINE | re.DOTALL)
        if not r:
            raise Exception("Trio {} (cmd: {}) Cannot parse answer: {}".format(self.name, repr(cmd), answer))
        if r.group(1) != cmd:
            raise Exception("Expected echo of command, got: {}".format(r.group(1)))
        err = re.match(b'.*%(\[[^\n]+)\r', r.group(2), re.MULTILINE | re.DOTALL)
        if err:
            raise Exception("Command Error {}".format(err.group(1)))
        if r.group(3) != b'0x10000000A':
            raise Exception("Trio {} (cmd: {}) bad return code: {}".format(self.name, repr(cmd), r.group(3)))
        return re.sub(b'\r\n$', b'', r.group(2))  # Remove ending \r\n if answer is not empty

    def commandI(self, cmd, timeout=30):
        return int(self.command(cmd, timeout))

    def commandS(self, cmd, timeout=30):
        """ Execute command and return the result as a string. """
        s = self.command(cmd, timeout).decode().replace('\r\n', '\n')
        return s

    def restart(self):
        try:
            self.command('EX', timeout=1)
        except Exception as e:
            if re.match(r'.*EX\\r\\nOK\\xb0>>', str(e.args[0])):
                print("Restarting... wait time is about 15sec")
                return
            else:
                raise

    def quote(self, s):
        """ Trio quoting is using \" and "" is quote of \" """
        return '"{}"'.format(s.replace('"', '""'))

    def read_program(self, progname):
        return self.commandS("LIST \"{}\"".format(progname))

    def write_program(self, progname, prog_type, lines, compile=True):
        self.delete_program(progname)
        self.command("SELECT {},{}".format(self.quote(progname), prog_type))
        for (n, l) in enumerate(lines):
            self.command("!{},{}R{}".format(progname, n, l.strip("\n\r")))
        if compile:
            self.commandS("COMPILE", 60)


    def delete_program(self, progname):
        progname = self.quote(progname)
        if self.commandI("?IS_PROG {}".format(progname)):
            self.command("DEL {}".format(progname))


    def download_file(self, filename, with_file_extension=True):
        """ Download a file like TEST.BAS or MC_CONFIG.MCC from the controller.
        If the type of the file is unknown, it is possible to simply ask for TEST and set with_file_extension=False
        To let the file type from the controller decide.
        """
        if with_file_extension:
            progname, prog_type = program_from_filename(filename)
            r_prog_type = self.commandI("?PROG_TYPE \"{}\"".format(progname))
            if r_prog_type == -1:
                raise Exception("Controller is missing program {}".format(progname))
            if r_prog_type != prog_type:
                raise Exception("Remote program is of wrong type {}".format(r_prog_type))
        else:
            progname = Path(filename).name
            progname.upper()
            r_prog_type = self.commandI("?PROG_TYPE \"{}\"".format(progname))
            filename = Path(filename).parent / (progname + extension_from_prog_type(r_prog_type))
        with open(filename, 'w') as f:
            f.write(self.read_program(progname) + '\n')

    def upload_file(self, filename):
        progname, prog_type = program_from_filename(filename)
        with open(filename, 'r') as f:
            self.write_program(progname, prog_type, f)

    def list_files(self):
        dirlist = self.commandS("DIR")
        progtable = re.match(".*---------\n(.*)OK", dirlist, re.MULTILINE | re.DOTALL).group(1)
        r = {}
        for line in progtable.splitlines():
            m = re.match(progtable_regex, line)
            if not m:
                raise Exception("Could not parse dir line: " + line)
            r[m.group('progname')] = m.groupdict()
        return r

    def download_all(self, directory='.'):
        for p in self.list_files():
            filename = str(Path(directory) / p)
            self.download_file(filename, with_file_extension=False)

    def upload_all(self, directory='.'):
        for f in Path(directory).iterdir():
            if f.is_file():
                self.upload_file(str(f))

    def checksum_controller(self):
        self.command("COMPILE_ALL", 120)
        return self.commandI("?CHECKSUM")

    def checksum_program(self, progname):
        return self.commandI("EDPROG{},10".format(self.quote(progname)))

    def autorun_program(self, progname, prog_type, process):
        """ Process -1 is automatic process selection, None removes the autorun"""
        if prog_type != 0:
            return  # Only programs are autorunable, trio will fail to set no autorun on non autorunable...
        prog = self.quote(progname)
        autorun = process is not None
        if autorun:
            self.command("RUNTYPE{},{},{}".format(prog, 1, process))
        else:
            self.command("RUNTYPE{},{},{}".format(prog, 0, -1))



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
            self.ws = yaml.load(f)
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
                r = input(msg + " Y/n?")
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
                print('File removed from the controller.')
                if prompt('Removing it from workspace'):
                    Path(filename).unlink()
                continue

            if not self.check_controller_filecontent(filename):
                print('File {} is different'.format(filename))
                if prompt("Downloading form controller"):
                    self.trio.download_file(filename)

            if str(cfiles[progname]['autorun']) != str(autorun):
                print('File {} has different autorun'.format(filename))
                if prompt('Updating it'):
                    f['autorun'] = cfiles[progname]['autorun']

            new_files.append(f)
            cfiles.pop(progname)

        if cfiles:
            print("Extra files are in the controller")
            if prompt("Downloading them"):
                for cf in cfiles.values():
                    new_file = self.entry_from_list_file('.', cf)
                    if prompt("Downloading new file {}".format(cf['progname'])):
                        self.trio.download_file(new_file['filename'])
                        new_files.append(new_file)

        self.ws['files'] = new_files

        self.save(wsfile)


    def write_to_controller(self, clear=False):
        """ Write the current workspace to the controller.
        If clear, it will clear everything in the controller before uploading.
        """
        if self.ws is None:
            raise Exception("Trying to write empty workspace to controller.")
        self.trio.command("HALT")  # Trio will fail when there are running progs and we write some
        if clear:
            for f in self.trio.list_files():
                self.trio.delete_program(f)

        for f in self.ws.get('files', []):
            filename = self.wsfiledir / f['filename']
            if not self.check_controller_filecontent(filename):
                print("Updating {}".format(filename))
                self.trio.upload_file(filename)
                progname, prog_type = program_from_filename(filename)
                self.trio.autorun_program(progname, prog_type, f.get('autorun', None))
                if prog_type == program_types['.MCC']:
                    print("MC_CONFIG.MCC got update, you will need to restart the controller")


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

    def check_controller_filelist(self, check_extra=False):
        if self.ws is None:
            raise Exception("Workspace is empty, please load a workspace.")

        r = False

        cfiles = self.trio.list_files()
        extras = set(cfiles.keys())

        for f in self.ws.get('files', []):
            filename = self.wsfiledir / f['filename']
            progname, prog_type = program_from_filename(filename)
            if progname not in cfiles:
                print("File {} is missing in the controller".format(progname))
                r = True
            else:
                ll = cfiles[progname]
                cprog_type = program_types.get(extension_from_code_type(ll['codetype']))
                if prog_type != cprog_type:
                    print("File {} is of wrong type in the controller".format(progname))
                    r = True
                if not self.check_controller_filecontent(filename):
                    print("File {} content is different in the controller".format(progname))
                    r = True
                if str(ll['autorun']) != str(f.get('autorun', None)):
                    print("File {} autorun state is different in the controller".format(progname))
                extras.remove(progname)

        if extras:
            print("Extra files are in the controller ({})".format(', '.join(extras)))
            if check_extra:
                r = True

        return r

    def download_all(self):
        for f in self.ws.get('files', []):
            self.trio.download_file(self.wsfiledir / f['filename'])


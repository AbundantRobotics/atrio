import re
import telnetlib
import atexit
import time
import enum
import random
random.seed()
from pathlib import Path


class AtrioError(Exception):
    pass


program_types = {
    ".BAS": 0,  # Program type
    ".TXT": 3,  # Text type
    ".MCC": 9,  # MC_CONFIG
    ".BAL": 12,  # Basic library
    ".PROJ": 7,  # Project type
}

def extension_from_prog_type(prog_type):
    """ Returns file extension from a trio prog_type """
    return next(k for (k, v) in program_types.items() if v == prog_type)


code_types = {
    "Normal": ".BAS",
    "BASIC Lib": ".BAL",
    "Text": ".TXT",
    "MC_CONFIG": ".MCC",
    "Project": ".PROJ"
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


class SystemError(enum.Flag):
    RamError = 0x000001
    BatteryError = 0x000002
    InvalidModuleError = 0x000004
    VrTableCorruptEntry = 0x000008
    MC_CONFIGError = 0x000010
    WatchdogTripError = 0x000020
    FPGAError = 0x000040
    FlashMemoryError = 0x000080
    UnitError = 0x000100
    StationError = 0x000200
    IOConfigurationError = 0x000400
    AxesConfigurationError = 0x000800
    UnitLost = 0x010000
    UnitTerminatorLost = 0x020000
    UnitStationLost = 0x040000
    InvalidUnitError = 0x080000
    UnitStationError = 0x100000
    ProcessorException = 0x01000000
    RFIDCircuitIdentificationError = 0x02000000

class EthercatState(enum.Enum):
    Initial = 0
    PreOprational = 1
    SafeOperational = 2
    Operational = 3

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

    def connect(self, timeout=1, retry=3):
        if self.t:
            self.t.close()
        else:
            self.t = telnetlib.Telnet(timeout=timeout)
        self.t.open(self.ip, timeout=timeout)
        for _ in range(retry + 1):
            try:
                x = str(int(1000000*random.random()))
                output = self.commandS(f'?{x}', timeout=timeout)
                if output != x:
                    print(re.sub('^', '    ', output, re.MULTILINE))
                else:
                    break
            except AtrioError:
                pass
        else:
            raise AtrioError("Could not connect: Motion Perfect probably open?")

        if self.commandI("?MPE") != 0:
            raise AtrioError("Motion Perfect probably open (MPE != 0)")





    def __init__(self, ip, trace : bool=False):
        self.t = None
        self.ip = ip
        self.name = ip
        self.trace = trace
        atexit.register(Trio.__del__, self)
        self.connect(timeout=1)

    def __del__(self):
        if 't' in self.__dict__:
            self.t.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.t:
            self.t.close()
        return False

    def decode(self, trio_str):
        return trio_str.decode(errors="ignore").replace('\r\n', '\n').replace('\r', '\n')

    def print_extra_output(self, bytes):
        print('    ', self.decode(bytes).replace('\n', '\n    '), sep='')

    def command(self, cmd : str, timeout : float=30):
        cmd = cmd.encode('ascii')
        self.t.write(cmd + b'\r\n')
        if self.trace:
            print('-> ', cmd + b'\r\n')

        resp = b'(.*?)' + re.escape(cmd) + b'\r\n(.*)>>\nControl char : ((?-s:.*))\r\n>>'

        end_re = re.compile(resp, re.MULTILINE | re.DOTALL)
        (_, r, answer) = self.t.expect([end_re], timeout)
        if self.trace:
            print('<- ', answer)
        if not answer:
            raise AtrioError("No response to {}".format(repr(cmd)))
        if not r:
            self.print_extra_output(answer)
            raise AtrioError("Cannot parse answer to {}: {}".format(repr(cmd), answer))

        # We have extra output before our command, let's display it
        if r.group(1):
            self.print_extra_output(r.group(1))

        err = re.match(b'.*%(\[COMMAND[^\n]+)\r', r.group(2), re.MULTILINE | re.DOTALL)
        if err:
            raise AtrioError("Command Error {}".format(err.group(1)))
        if r.group(3) != b'0x10000000A':
            raise AtrioError("Trio {} (cmd: {}) bad return code: {}".format(self.name, repr(cmd), r.group(3)))
        return re.sub(b'\r\n$', b'', r.group(2))  # Remove ending \r\n if answer is not empty

    def commandI(self, cmd, timeout=30):
        return int(self.command(cmd, timeout))

    def commandF(self, cmd, timeout=30):
        return float(self.command(cmd, timeout))

    def commandS(self, cmd, timeout=30):
        """ Execute command and return the result as a string. """
        s = self.decode(self.command(cmd, timeout))
        return s

    def restart(self, wait=True):
        try:
            self.command('EX', timeout=1)
        except AtrioError as e:
            if not re.match(r"Cannot parse answer to b'EX': b'EX\\r\\n.*'", str(e.args[0])):
                raise
        print("Restarting (may take up to 30sec)", end='', flush=True)
        if wait:
            for _ in range(30):
                try:
                    self.connect(timeout=1)
                    print("Restarted")
                    print(self.commandS("AUTORUN"))
                    break
                except:
                    print('.', end='', flush=True)
                    pass
            else:
                raise AtrioError("Failed to restart")
        else:
            print()


    def halt(self):
        try:
            self.command("HALT", timeout=0.5)
        except Exception as e:
            pass # We do not really know what to do if there are process printing to channel #0 ...

    def quote(self, s):
        """ Trio quoting is using \" and "" is quote of \" """
        return '"{}"'.format(s.replace('"', '""'))

    def read_program(self, progname):
        return self.commandS("LIST \"{}\"".format(progname))

    def write_program(self, progname, prog_type=None, lines=None):
        if prog_type is None:
            prog_type = program_types['.BAS']
        if not lines:
            lines = ['']
        try:
            self.delete_program(progname)
            self.command("SELECT {},{}".format(self.quote(progname), prog_type))
            for (n, l) in enumerate(lines):
                self.command("!{},{}R{}".format(progname, n, l.strip("\n\r")))
            self.command("!{},M".format(progname))
            # Try to commit things..
            self.command("!{},Z".format(progname))
            for _ in range(60):
                if self.commandI("?FLASH_STATUS"):
                    self.command("!{},Z".format(progname))
                    time.sleep(0.03)
                else:
                    break
            else:
                raise AtrioError("Flash Status never off, program might be corrupted")

            self.commandS("COMPILE", 60) # Compiling is needed to not have strange failures with communication to trio
        except Exception as e:
            e.args = ("Error writing {} program: {} ".format(progname, e.args[0]),) + e.args[1:]
            raise

    def delete_program(self, progname):
        progname = self.quote(progname)
        if self.commandI("?IS_PROG {}".format(progname)):
            self.command("DEL {}".format(progname))
            self.command("&M") # commit to flash

    def download_file(self, filename, with_file_extension=True):
        """ Download a file like TEST.BAS or MC_CONFIG.MCC from the controller.
        If the type of the file is unknown, it is possible to simply ask for TEST and set with_file_extension=False
        To let the file type from the controller decide.
        """
        if with_file_extension:
            progname, prog_type = program_from_filename(filename)
            r_prog_type = self.commandI("?PROG_TYPE \"{}\"".format(progname))
            if r_prog_type == -1:
                raise AtrioError("Controller is missing program {}".format(progname))
            if r_prog_type != prog_type:
                raise AtrioError("Remote program is of wrong type {}".format(r_prog_type))
        else:
            progname = Path(filename).name
            progname.upper()
            r_prog_type = self.commandI("?PROG_TYPE \"{}\"".format(progname))
            filename = Path(filename).parent / (progname + extension_from_prog_type(r_prog_type))
        with open(filename, 'w', newline='\r\n') as f:
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
                raise AtrioError("Could not parse dir line: " + line)
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
        print(self.commandS("COMPILE_ALL", 120))
        return self.commandI("?CHECKSUM")

    def checksum_program(self, progname):
        return self.commandI("EDPROG{},10".format(self.quote(progname)))

    def autorun_program(self, progname, process):
        """ Process -1 is automatic process selection, None removes the autorun"""
        prog = self.quote(progname)
        autorun = process is not None
        if autorun:
            self.command("RUNTYPE{},{},{}".format(prog, 1, process))
        else:
            self.command("RUNTYPE{},{},{}".format(prog, 0, -1))


    def system_error(self):
        return SystemError(self.commandI("?SYSTEM_ERROR"))

    def system_load(self):
        """ Returns the max system load in percent since previous call or since powerup.
         System load is the load associated to the trio system excluding user programs,
         It should be bellow 50% according to trio help."""
        load_percent = self.commandF("?SYSTEM_LOAD_MAX")
        self.command("SYSTEM_LOAD_MAX=0")
        return load_percent

    def process_load(self):
        return self.commandS("PROCESS")


    def ethercat_list(self):
        return self.commandS("ETHERCAT($87,0)")

    def ethercat_state(self):
        return EthercatState(self.commandI("ETHERCAT($22,0,-1)")).name

    def ethercat_set_state(self, state : EthercatState):
        return self.commandS(f"ETHERCAT($21, 0, {state.value}, 0) ")

    def ethercat_reinitialize(self):
        return self.commandS("ETHERCAT(0, 0)")

    def ethercat_start(self):
        return self.ethercat_state(EthercatState.Operational)

    def ethercat_stop(self):
        return self.commandS("ETHERCAT(1, 0)")

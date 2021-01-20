import atrio
import pytest


def test_version(trio):
    """ We have not tested with older firmware versions """
    assert trio.commandF("?version") >= 2.0297


@pytest.mark.tmp_prog_lines(['BASE(0)'])
def test_manual_autorun(trio, trio_tmp_prog):
    """
    Command like `autorun` return some special output looking like usual errors.
    """
    trio.autorun_program(trio_tmp_prog, -1)
    assert f"Program {trio_tmp_prog}] - Running" in trio.commandS("AUTORUN")


def test_list_files(trio, trio_tmp_prog):
    trio.autorun_program(trio_tmp_prog, 10)
    ls = trio.list_files()
    assert trio_tmp_prog in ls
    assert ls[trio_tmp_prog]['progname'] == trio_tmp_prog
    assert ls[trio_tmp_prog]['code'] == '0'  # empty program
    assert ls[trio_tmp_prog]['autorun'] == '10'
    assert atrio.code_types[ls[trio_tmp_prog]['codetype']] == '.BAS'


@pytest.mark.slow
@pytest.mark.tmp_prog_lines(['VR(42) = 42'])
def test_restart_autorun_trigger(trio, trio_tmp_prog):
    """
    Command like `autorun` return some special output looking like usual errors.
    Testing create a file, set it as autorun, call autorun, delete it.
    """
    trio.autorun_program(trio_tmp_prog, -1)

    trio.command("VR(42) = 40")
    assert trio.commandF("?VR(42)") == 40
    trio.restart()
    assert trio.commandF("?VR(42)") == 42


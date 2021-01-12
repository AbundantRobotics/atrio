import atrio


def test_version(trio):
    assert trio.commandF("?version") >= 2.0297


def test_manual_autorun(trio):
    """
    Command like `autorun` return some special output looking like usual errors.
    Testing create a file, set it as autorun, call autorun, delete it.
    """
    rnds = "TMP_ATIYVANSERIJFH"
    prgtype = atrio.program_types[".BAS"]
    trio.write_program(rnds, prgtype, [f'BASE(0)'])
    trio.autorun_program(rnds, prgtype, -1)
    assert f"Program {rnds}] - Running" in trio.commandS("AUTORUN")
    trio.delete_program(rnds)


def test_restart_autorun_trigger(trio):
    """
    Command like `autorun` return some special output looking like usual errors.
    Testing create a file, set it as autorun, call autorun, delete it.
    """
    rnds = "TMP_HGASUEOVJXKK"
    prgtype = atrio.program_types[".BAS"]
    trio.command("VR(42) = 40")
    trio.write_program(rnds, prgtype, [f'VR(42) = 42'])
    trio.autorun_program(rnds, prgtype, -1)

    assert trio.commandF("?VR(42)") == 40
    trio.restart()
    assert trio.commandF("?VR(42)") == 42

    trio.delete_program(rnds)


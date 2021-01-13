"""
We provide the `trio` fixture which needs to connect to an hardware
trio controller. To run the tests with hardware, you need to provide the ip
of the trio with `--trio-ip` like:

    pytest --trio-ip 192.168.0.1

Not providing the ip will skip the tests using the trio fixture.
"""

import pytest

""" Setup similar to the runslow example of pytest """


def pytest_addoption(parser):
    parser.addoption(
        "--trio-ip", default="", help="If an IP is provided, test needing hardware will be run using it."
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "hw: mark test as needing hardware (a trio ip)")


def pytest_collection_modifyitems(config, items):
    ip = config.getoption("--trio-ip", None)
    if ip:
        print("Running HW tests on " + ip)
        return
    skip_hw = pytest.mark.skip(reason="need hardware to run (use --trio-ip option)")
    for item in items:
        if 'trio' in item.fixturenames:
            item.add_marker(skip_hw)


import atrio

@pytest.fixture
def trio(pytestconfig):
    ip = pytestconfig.getoption("--trio-ip", None)
    assert ip
    with atrio.Trio(ip) as t:
        yield t




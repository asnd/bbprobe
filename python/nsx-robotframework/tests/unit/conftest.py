import pytest
import requests_mock as rm_module

from nsx_robotframework import NSXClient, NSXLibrary

NSX_URL = "https://nsx.example.local"


@pytest.fixture
def nsx_url():
    return NSX_URL


@pytest.fixture
def m():
    with rm_module.Mocker() as mocker:
        yield mocker


@pytest.fixture
def client(m):
    m.post(f"{NSX_URL}/api/v1/session/create", json={}, status_code=200)
    c = NSXClient(NSX_URL, "admin", "pass", verify=False, timeout=5, retries=1, backoff=0)
    c.connect()
    return c


@pytest.fixture
def library(m):
    m.post(f"{NSX_URL}/api/v1/session/create", json={}, status_code=200)
    lib = NSXLibrary()
    lib.connect_to_nsx(NSX_URL, "admin", "pass", verify="${False}")
    return lib

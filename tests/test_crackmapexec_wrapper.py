import pytest
from unittest.mock import patch, MagicMock
from spectrenet.wrappers.builtin.crackmapexec import CrackMapExecWrapper


@pytest.fixture
def wrapper():
    return CrackMapExecWrapper()


SAMPLE_SUCCESS = """\
SMB         10.0.0.1    445    DC01    [*] Windows Server 2019 (name:DC01) (domain:CORP.LOCAL)
SMB         10.0.0.1    445    DC01    [+] CORP.LOCAL\\admin:Password123 (Pwn3d!)
SMB         10.0.0.1    445    DC01    [+] CORP.LOCAL\\guest:guest
"""

SAMPLE_HASHES = """\
SMB         10.0.0.1    445    DC01    Administrator:500:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0:::
SMB         10.0.0.1    445    DC01    username: bob
"""


def test_tool_name(wrapper):
    assert wrapper.tool_name == "crackmapexec"


def test_schema(wrapper):
    schema = wrapper.schema
    assert "successes" in schema
    assert "shares"    in schema
    assert "hashes"    in schema
    assert "users"     in schema


def test_is_available_false(wrapper):
    with patch("shutil.which", return_value=None):
        assert wrapper.is_available() is False


def test_is_available_netexec(wrapper):
    def which_mock(name):
        return "/usr/bin/netexec" if name == "netexec" else None
    with patch("shutil.which", side_effect=which_mock):
        assert wrapper.is_available() is True


def test_is_available_nxc(wrapper):
    def which_mock(name):
        return "/usr/bin/nxc" if name == "nxc" else None
    with patch("shutil.which", side_effect=which_mock):
        assert wrapper.is_available() is True


def test_run_parses_successes(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_SUCCESS
    mock_result.stderr = ""
    def which_mock(name):
        return "/usr/bin/crackmapexec" if name == "crackmapexec" else None
    with patch("shutil.which", side_effect=which_mock), \
         patch("subprocess.run", return_value=mock_result):
        result = wrapper.run(protocol="smb", target="10.0.0.1", username="admin", password="Password123")
    assert len(result["successes"]) >= 1
    assert any("admin" in s or "guest" in s for s in result["successes"])


def test_run_parses_hashes(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_HASHES
    mock_result.stderr = ""
    def which_mock(name):
        return "/usr/bin/crackmapexec" if name == "crackmapexec" else None
    with patch("shutil.which", side_effect=which_mock), \
         patch("subprocess.run", return_value=mock_result):
        result = wrapper.run(protocol="smb", target="10.0.0.1")
    assert len(result["hashes"]) >= 1


def test_run_parses_users(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_HASHES
    mock_result.stderr = ""
    def which_mock(name):
        return "/usr/bin/crackmapexec" if name == "crackmapexec" else None
    with patch("shutil.which", side_effect=which_mock), \
         patch("subprocess.run", return_value=mock_result):
        result = wrapper.run(protocol="smb", target="10.0.0.1")
    assert "bob" in result["users"]


def test_run_raw_in_result(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_SUCCESS
    mock_result.stderr = ""
    def which_mock(name):
        return "/usr/bin/crackmapexec" if name == "crackmapexec" else None
    with patch("shutil.which", side_effect=which_mock), \
         patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("smb", "10.0.0.1")
    assert "DC01" in result["raw"]

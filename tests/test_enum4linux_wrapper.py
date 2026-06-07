import pytest
from unittest.mock import patch, MagicMock
from spectrenet.wrappers.builtin.enum4linux import Enum4linuxWrapper


@pytest.fixture
def wrapper():
    return Enum4linuxWrapper()


SAMPLE_OUTPUT = """\
 ================================( Users on 10.0.0.1 )================================
user:[alice] rid:[0x3e8]
user:[bob] rid:[0x3e9]
user:[admin] rid:[0x1f4]

 ================================( Groups on 10.0.0.1 )================================
group:[Domain Users] rid:[0x201]
group:[Administrators] rid:[0x220]

 ================================( Share Enumeration on 10.0.0.1 )================================
Sharename       Type      Comment
ADMIN$          Disk      Remote Admin
IPC$            IPC       Remote IPC
Mapping: \\\\10.0.0.1\\share1
Mapping: \\\\10.0.0.1\\share2

 OS=[Windows 7 SP1] Server=[Samba 4.6.0]
"""


def test_schema(wrapper):
    schema = wrapper.schema
    assert "users" in schema
    assert "groups" in schema
    assert "shares" in schema
    assert "os" in schema


def test_tool_name(wrapper):
    assert wrapper.tool_name == "enum4linux"


def test_is_available_false(wrapper):
    with patch("shutil.which", return_value=None):
        assert wrapper.is_available() is False


def test_is_available_true(wrapper):
    with patch("shutil.which", return_value="/usr/bin/enum4linux"):
        assert wrapper.is_available() is True


def test_run_parses_users(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert "alice" in result["users"]
    assert "bob"   in result["users"]
    assert "admin" in result["users"]


def test_run_parses_groups(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    groups = result["groups"]
    assert any("Domain Users" in g for g in groups)
    assert any("Administrators" in g for g in groups)


def test_run_parses_shares(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    shares = result["shares"]
    assert len(shares) >= 1


def test_run_parses_os(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert "Windows 7 SP1" in result["os"]


def test_run_raw_output(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert SAMPLE_OUTPUT in result["raw"]


def test_run_no_os_info(wrapper):
    output = "user:[alice] rid:[0x3e8]\n"
    mock_result = MagicMock()
    mock_result.stdout = output
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert result["os"] == ""

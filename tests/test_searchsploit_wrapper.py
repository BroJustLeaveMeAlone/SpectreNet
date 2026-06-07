import json
import pytest
from unittest.mock import patch, MagicMock
from spectrenet.wrappers.builtin.searchsploit import SearchsploitWrapper


@pytest.fixture
def wrapper():
    return SearchsploitWrapper()


JSON_OUTPUT = json.dumps({
    "RESULTS_EXPLOIT": [
        {
            "Title":    "Apache 2.4.49 - Path Traversal & Remote Code Execution (RCE)",
            "EDB-ID":   "50383",
            "Path":     "/usr/share/exploitdb/exploits/linux/webapps/50383.py",
            "Type":     "remote",
            "Platform": "linux",
            "Date":     "2021-10-05",
        },
        {
            "Title":    "Apache mod_cgi - Remote Command Execution",
            "EDB-ID":   "31000",
            "Path":     "/usr/share/exploitdb/exploits/linux/remote/31000.sh",
            "Type":     "remote",
            "Platform": "linux",
            "Date":     "2014-01-01",
        },
    ],
    "RESULTS_SHELLCODE": [],
})

PLAIN_OUTPUT = """\
 ----- Exploit Title -----                                           |  Path
-------------------------------------------------------------------- ---------
Apache 2.4.49 - Path Traversal & RCE                                  linux/webapps/50383.py
Apache mod_cgi - Remote Command Execution                              linux/remote/31000.sh
Shellcodes: No Result
"""


def test_tool_name(wrapper):
    assert wrapper.tool_name == "searchsploit"


def test_schema(wrapper):
    assert "exploits" in wrapper.schema


def test_is_available_false(wrapper):
    with patch("shutil.which", return_value=None):
        assert wrapper.is_available() is False


def test_is_available_true(wrapper):
    with patch("shutil.which", return_value="/usr/bin/searchsploit"):
        assert wrapper.is_available() is True


def test_run_json_parse(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = JSON_OUTPUT
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("apache 2.4.49")
    exploits = result["exploits"]
    assert len(exploits) == 2
    assert exploits[0]["edb_id"] == "50383"
    assert "Path Traversal" in exploits[0]["title"]


def test_run_json_fields(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = JSON_OUTPUT
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("apache 2.4.49")
    e = result["exploits"][0]
    assert "title"    in e
    assert "edb_id"   in e
    assert "path"     in e
    assert "type"     in e
    assert "platform" in e
    assert "date"     in e


def test_run_fallback_plain_text(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = PLAIN_OUTPUT
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("apache", flags="")
    exploits = result["exploits"]
    assert len(exploits) >= 1


def test_run_empty_json(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = json.dumps({"RESULTS_EXPLOIT": [], "RESULTS_SHELLCODE": []})
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("nonexistent-tool-xyz")
    assert result["exploits"] == []


def test_run_raw_in_result(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = JSON_OUTPUT
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("apache")
    assert result["raw"] == JSON_OUTPUT

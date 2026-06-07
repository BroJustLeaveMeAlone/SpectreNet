import pytest
from unittest.mock import patch, MagicMock
from spectrenet.wrappers.builtin.whatweb import WhatWebWrapper


@pytest.fixture
def wrapper():
    return WhatWebWrapper()


SAMPLE_OUTPUT = """\
http://10.0.0.1 [200] Apache[2.4.49], Bootstrap[4.5.0], HTTPServer[Apache/2.4.49], IP[10.0.0.1], PHP[7.4.3], Title[Welcome]
https://10.0.0.1:443 [200] Apache[2.4.49], Strict-Transport-Security[max-age=31536000], Title[Secure Site]
"""


def test_tool_name(wrapper):
    assert wrapper.tool_name == "whatweb"


def test_schema(wrapper):
    assert "fingerprints" in wrapper.schema


def test_is_available_false(wrapper):
    with patch("shutil.which", return_value=None):
        assert wrapper.is_available() is False


def test_is_available_true(wrapper):
    with patch("shutil.which", return_value="/usr/bin/whatweb"):
        assert wrapper.is_available() is True


def test_run_parses_fingerprints(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("http://10.0.0.1")
    fps = result["fingerprints"]
    assert len(fps) >= 1
    first = fps[0]
    assert "url"          in first
    assert "status"       in first
    assert "technologies" in first


def test_run_parses_apache_version(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("http://10.0.0.1")
    fps = result["fingerprints"]
    # Find Apache entry
    apache = next(
        (t for fp in fps for t in fp["technologies"] if t["name"] == "Apache"),
        None
    )
    assert apache is not None
    assert "2.4.49" in apache["version"]


def test_run_status_code(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("http://10.0.0.1")
    assert result["fingerprints"][0]["status"] == "200"


def test_run_raw_in_result(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("http://10.0.0.1")
    assert "Apache" in result["raw"]


def test_empty_output(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("http://10.0.0.1")
    assert result["fingerprints"] == []

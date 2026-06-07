import pytest
from unittest.mock import patch, MagicMock
from spectrenet.wrappers.builtin.shodan import ShodanWrapper


@pytest.fixture
def wrapper():
    return ShodanWrapper()


SAMPLE_OUTPUT = """\
10.0.0.1
Hostnames:    example.com, www.example.com
Country:      United States
Organization: Acme Corp
Operating System: Linux 4.x
Ports:        22, 80, 443, 8080
Vulnerabilities:  CVE-2021-44228, CVE-2017-0144
"""


def test_tool_name(wrapper):
    assert wrapper.tool_name == "shodan"


def test_schema(wrapper):
    schema = wrapper.schema
    assert "ports" in schema
    assert "vulns" in schema
    assert "country" in schema
    assert "hostnames" in schema


def test_is_available_false(wrapper):
    with patch("shutil.which", return_value=None):
        assert wrapper.is_available() is False


def test_is_available_true(wrapper):
    with patch("shutil.which", return_value="/usr/bin/shodan"):
        assert wrapper.is_available() is True


def test_run_parses_ports(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert 22  in result["ports"]
    assert 80  in result["ports"]
    assert 443 in result["ports"]


def test_run_parses_country(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert "United States" in result["country"]


def test_run_parses_org(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert "Acme Corp" in result["org"]


def test_run_parses_hostnames(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert "example.com" in result["hostnames"]


def test_run_parses_vulns(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert "CVE-2021-44228" in result["vulns"]
    assert "CVE-2017-0144"  in result["vulns"]


def test_run_raw_included(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert SAMPLE_OUTPUT in result["raw"]


def test_run_ip_in_result(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert result["ip"] == "10.0.0.1"


def test_empty_output(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("10.0.0.1")
    assert result["ports"] == []
    assert result["vulns"] == []

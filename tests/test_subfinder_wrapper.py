import pytest
from unittest.mock import patch, MagicMock
from spectrenet.wrappers.builtin.subfinder import SubfinderWrapper


@pytest.fixture
def wrapper():
    return SubfinderWrapper()


SAMPLE_OUTPUT = """\
api.example.com
www.example.com
mail.example.com
dev.example.com
staging.example.com
"""


def test_tool_name(wrapper):
    assert wrapper.tool_name == "subfinder"


def test_schema(wrapper):
    schema = wrapper.schema
    assert "domain"     in schema
    assert "subdomains" in schema
    assert "count"      in schema


def test_is_available_false(wrapper):
    with patch("shutil.which", return_value=None):
        assert wrapper.is_available() is False


def test_is_available_true(wrapper):
    with patch("shutil.which", return_value="/usr/bin/subfinder"):
        assert wrapper.is_available() is True


def test_run_parses_subdomains(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("example.com")
    subs = result["subdomains"]
    assert "api.example.com"     in subs
    assert "www.example.com"     in subs
    assert "mail.example.com"    in subs
    assert "staging.example.com" in subs


def test_run_count(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("example.com")
    assert result["count"] == len(result["subdomains"])
    assert result["count"] == 5


def test_run_domain_in_result(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = SAMPLE_OUTPUT
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("example.com")
    assert result["domain"] == "example.com"


def test_deduplication(wrapper):
    output = "api.example.com\napi.example.com\nwww.example.com\n"
    mock_result = MagicMock()
    mock_result.stdout = output
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("example.com")
    assert result["count"] == 2


def test_filters_non_domain_lines(wrapper):
    output = "[subfinder] Starting scan...\napi.example.com\n[INFO] done\nwww.example.com\n"
    mock_result = MagicMock()
    mock_result.stdout = output
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("example.com")
    # Should only have valid domain lines
    for sub in result["subdomains"]:
        assert sub in ("api.example.com", "www.example.com")


def test_empty_output(wrapper):
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = wrapper.run("example.com")
    assert result["subdomains"] == []
    assert result["count"] == 0

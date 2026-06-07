import pytest
from spectrenet.wrappers.builtin.nikto import NiktoWrapper

NIKTO_OUTPUT = """\
- Nikto v2.1.6
---------------------------------------------------------------------------
+ Target IP:          10.10.10.5
+ Target Port:        80
---------------------------------------------------------------------------
+ Server: Apache/2.2.14 (Ubuntu)
+ OSVDB-3268: /icons/: Directory indexing found.
+ OSVDB-3233: /icons/README: Apache default file found.
+ 8345 requests: 0 error(s) and 2 item(s) reported on remote host
"""

EMPTY_OUTPUT = "- Nikto v2.1.6\n0 items reported"


def test_parse_returns_two_findings():
    result = NiktoWrapper().parse(NIKTO_OUTPUT)
    assert len(result["findings"]) == 2


def test_parse_finding_has_id_and_msg():
    findings = NiktoWrapper().parse(NIKTO_OUTPUT)["findings"]
    assert findings[0]["id"] == "OSVDB-3268"
    assert "Directory indexing" in findings[0]["msg"]


def test_parse_target_captured():
    result = NiktoWrapper().parse(NIKTO_OUTPUT)
    assert result["target"] == "10.10.10.5"


def test_parse_empty_returns_no_findings():
    assert NiktoWrapper().parse(EMPTY_OUTPUT)["findings"] == []


def test_schema_present():
    assert "findings" in NiktoWrapper().schema

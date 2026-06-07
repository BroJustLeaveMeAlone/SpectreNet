import pytest
from spectrenet.wrappers.builtin.nuclei import NucleiWrapper

NUCLEI_OUTPUT = """\
[2024-01-01 12:00:00] [cve-2021-44228] [http] [critical] http://10.10.10.5/api/log?input= ["log4shell"]
[2024-01-01 12:00:01] [xss-generic] [http] [medium] http://10.10.10.5/search?q= ["XSS"]
"""

EMPTY_OUTPUT = ""


def test_parse_detects_two_vulns():
    result = NucleiWrapper().parse(NUCLEI_OUTPUT)
    assert len(result["vulnerabilities"]) == 2


def test_parse_critical_severity():
    vulns = NucleiWrapper().parse(NUCLEI_OUTPUT)["vulnerabilities"]
    assert any(v["severity"].lower() == "critical" for v in vulns)


def test_parse_template_id():
    vulns = NucleiWrapper().parse(NUCLEI_OUTPUT)["vulnerabilities"]
    assert any(v["template_id"] == "cve-2021-44228" for v in vulns)


def test_parse_empty_returns_no_vulns():
    assert NucleiWrapper().parse(EMPTY_OUTPUT)["vulnerabilities"] == []


def test_schema_present():
    assert "vulnerabilities" in NucleiWrapper().schema

import pytest
from spectrenet.ai.output_interpreter import OutputInterpreter

RECON_RESULT = {
    "hosts": [
        {
            "ip": "10.10.10.5",
            "ports": [
                {"port": 445, "service": "microsoft-ds", "version": "Samba 4.6.3"},
                {"port": 22,  "service": "ssh",          "version": "OpenSSH 7.4"},
            ],
        }
    ]
}

WEB_VULN_RESULT = {
    "vulnerabilities": [
        {
            "severity": "HIGH",
            "type":     "sqli",
            "url":      "http://10.10.10.5/login",
            "evidence": "1=1",
        }
    ]
}


def test_from_recon_returns_finding_per_port():
    findings = OutputInterpreter().from_recon(RECON_RESULT)
    assert len(findings) == 2


def test_from_recon_finding_schema():
    finding = OutputInterpreter().from_recon(RECON_RESULT)[0]
    assert finding["type"] == "open_port"
    assert finding["ip"] == "10.10.10.5"
    assert finding["port"] == 445
    assert finding["service"] == "microsoft-ds"
    assert finding["version"] == "Samba 4.6.3"
    assert finding["severity"] == "INFO"
    assert "detail" in finding


def test_from_recon_empty_hosts_returns_empty_list():
    assert OutputInterpreter().from_recon({"hosts": []}) == []


def test_from_web_vuln_returns_finding():
    findings = OutputInterpreter().from_web_vuln(WEB_VULN_RESULT)
    assert len(findings) == 1
    assert findings[0]["type"] == "vulnerability"
    assert findings[0]["severity"] == "HIGH"
    assert findings[0]["service"] == "sqli"


def test_from_session_output_fallback_without_model():
    findings = OutputInterpreter().from_session_output(
        "getuid", "Server username: NT AUTHORITY\\SYSTEM"
    )
    assert len(findings) == 1
    assert findings[0]["type"] == "post_ex"
    assert "SYSTEM" in findings[0]["detail"]


def test_from_session_output_uses_model_when_available():
    class FakeModel:
        def complete(self, system_prompt, user_prompt):
            return '[{"type":"credential","detail":"SYSTEM shell","severity":"CRITICAL","ip":"","port":null,"service":"","version":"","raw":""}]'

    findings = OutputInterpreter(model=FakeModel()).from_session_output(
        "getuid", "Server username: NT AUTHORITY\\SYSTEM"
    )
    assert findings[0]["type"] == "credential"
    assert findings[0]["severity"] == "CRITICAL"


def test_from_session_output_falls_back_when_model_returns_invalid_json():
    class BadModel:
        def complete(self, system_prompt, user_prompt):
            return "not json at all"

    findings = OutputInterpreter(model=BadModel()).from_session_output(
        "sysinfo", "Computer: TARGET-PC"
    )
    assert findings[0]["type"] == "post_ex"

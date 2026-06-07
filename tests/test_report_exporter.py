import pytest
from spectrenet.tui.report_exporter import generate_report
from spectrenet.workspace import Workspace
from spectrenet.loot import LootVault


@pytest.fixture
def workspace(tmp_path):
    ws = Workspace(str(tmp_path / "ws.json"))
    ws.add_target("10.0.0.1")
    ws.add_target("10.0.0.2")
    ws.add_note("Tested login form — weak credentials")
    ws.add_command("nmap 10.0.0.1 -sV")
    ws.add_finding("Open SMB with MS17-010 vulnerability")
    return ws


@pytest.fixture
def loot(tmp_path):
    v = LootVault(str(tmp_path / "loot.json"))
    v.add("cred",   "admin:password123")
    v.add("hash",   "aad3b435b51404eeaad3b435b51404ee")
    v.add("secret", "API_KEY=sk-abc123")
    return v


def test_report_contains_header(workspace, loot):
    report = generate_report(workspace, loot, {})
    assert "# SpectreNet Pentest Report" in report
    assert "operator" in report.lower()


def test_report_contains_targets(workspace, loot):
    report = generate_report(workspace, loot, {})
    assert "10.0.0.1" in report
    assert "10.0.0.2" in report


def test_report_contains_loot(workspace, loot):
    report = generate_report(workspace, loot, {})
    assert "admin:password123" in report
    assert "aad3b435b51404eeaad3b435b51404ee" in report
    assert "API_KEY=sk-abc123" in report


def test_report_contains_notes(workspace, loot):
    report = generate_report(workspace, loot, {})
    assert "weak credentials" in report


def test_report_contains_command_timeline(workspace, loot):
    report = generate_report(workspace, loot, {})
    assert "nmap 10.0.0.1 -sV" in report


def test_report_contains_findings(workspace, loot):
    report = generate_report(workspace, loot, {})
    assert "MS17-010" in report


def test_report_network_findings(workspace, loot):
    hosts = {
        "10.0.0.1": [
            {"port": "22",  "proto": "tcp", "service": "ssh",   "version": "OpenSSH 8.0"},
            {"port": "80",  "proto": "tcp", "service": "http",  "version": "Apache 2.4"},
            {"port": "445", "proto": "tcp", "service": "smb",   "version": ""},
        ]
    }
    report = generate_report(workspace, loot, hosts)
    assert "## Network Findings" in report
    assert "22" in report
    assert "ssh" in report
    assert "OpenSSH 8.0" in report


def test_report_empty_workspace(tmp_path):
    ws   = Workspace(str(tmp_path / "ws.json"))
    loot = LootVault(str(tmp_path / "loot.json"))
    report = generate_report(ws, loot, {})
    assert "# SpectreNet Pentest Report" in report
    assert "Always one step ahead" in report


def test_report_custom_operator(workspace, loot):
    report = generate_report(workspace, loot, {}, operator="Spectre-01")
    assert "Spectre-01" in report


def test_report_is_markdown_string(workspace, loot):
    report = generate_report(workspace, loot, {})
    assert isinstance(report, str)
    assert len(report) > 100

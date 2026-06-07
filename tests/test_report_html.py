import pytest
from spectrenet.tui.report_exporter import generate_report_html
from spectrenet.workspace import Workspace
from spectrenet.loot import LootVault


@pytest.fixture
def workspace(tmp_path):
    ws = Workspace(str(tmp_path / "ws.json"))
    ws.add_target("10.0.0.1")
    ws.add_target("10.0.0.2")
    ws.add_note("Found open SMB with no authentication")
    ws.add_command("nmap 10.0.0.1 -sV")
    ws.add_finding("EternalBlue — MS17-010 confirmed")
    return ws


@pytest.fixture
def loot(tmp_path):
    v = LootVault(str(tmp_path / "loot.json"))
    v.add("cred",   "admin:password123")
    v.add("hash",   "aad3b435b51404eeaad3b435b51404ee:31d6cfe0")
    v.add("secret", "AWS_KEY=AKIAIOSFODNN7EXAMPLE")
    return v


def test_returns_html_string(workspace, loot):
    html = generate_report_html(workspace, loot, {})
    assert isinstance(html, str)
    assert html.startswith("<!DOCTYPE html>")


def test_contains_title(workspace, loot):
    html = generate_report_html(workspace, loot, {})
    assert "SpectreNet" in html


def test_contains_targets(workspace, loot):
    html = generate_report_html(workspace, loot, {})
    assert "10.0.0.1" in html
    assert "10.0.0.2" in html


def test_contains_loot(workspace, loot):
    html = generate_report_html(workspace, loot, {})
    assert "admin:password123" in html
    assert "AWS_KEY=AKIAIOSFODNN7EXAMPLE" in html


def test_contains_note(workspace, loot):
    html = generate_report_html(workspace, loot, {})
    assert "open SMB" in html


def test_contains_command(workspace, loot):
    html = generate_report_html(workspace, loot, {})
    assert "nmap 10.0.0.1 -sV" in html


def test_contains_finding(workspace, loot):
    html = generate_report_html(workspace, loot, {})
    assert "EternalBlue" in html


def test_network_findings_table(workspace, loot):
    hosts = {
        "10.0.0.1": [
            {"port": "22",  "proto": "tcp", "service": "ssh",  "version": "OpenSSH 8.0"},
            {"port": "445", "proto": "tcp", "service": "smb",  "version": ""},
        ]
    }
    html = generate_report_html(workspace, loot, hosts)
    assert "<table>" in html
    assert "22" in html
    assert "ssh" in html
    assert "OpenSSH 8.0" in html


def test_xss_escaping(tmp_path):
    ws   = Workspace(str(tmp_path / "ws.json"))
    loot = LootVault(str(tmp_path / "loot.json"))
    ws.add_note("<script>alert('xss')</script>")
    loot.add("cred", "<img src=x onerror=alert(1)>")
    html = generate_report_html(ws, loot, {})
    # Literal unescaped tags must not be present
    assert "<script>alert('xss')</script>" not in html
    assert '<img src=x onerror=alert(1)>' not in html
    # Script tag must be HTML-escaped
    assert "&lt;script&gt;" in html


def test_custom_operator(workspace, loot):
    html = generate_report_html(workspace, loot, {}, operator="Spectre-01")
    assert "Spectre-01" in html


def test_footer_present(workspace, loot):
    html = generate_report_html(workspace, loot, {})
    assert "Always one step ahead" in html


def test_self_contained_no_external_deps(workspace, loot):
    html = generate_report_html(workspace, loot, {})
    # No external stylesheet or script src links
    assert 'href="http' not in html
    assert 'src="http'  not in html

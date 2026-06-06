# tests/test_command_parser.py
from spectrenet.tui.command_parser import parse_command, Command


def test_parse_simple_verb_and_arg():
    cmd = parse_command("scan 192.168.1.0/24")
    assert cmd == Command(verb="scan", args=["192.168.1.0/24"], flags={})


def test_parse_flags():
    cmd = parse_command("scan 10.0.0.1 --tool nmap --ports 1-1000")
    assert cmd.verb == "scan"
    assert cmd.args == ["10.0.0.1"]
    assert cmd.flags == {"tool": "nmap", "ports": "1-1000"}


def test_parse_empty_returns_none():
    assert parse_command("   ") is None

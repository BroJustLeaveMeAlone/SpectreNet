# tests/test_nmap_wrapper.py
from pathlib import Path
from spectrenet.wrappers.builtin.nmap import NmapWrapper

FIX = Path(__file__).parent / "fixtures" / "nmap_sample.xml"

def test_nmap_parses_xml_into_normalized_schema():
    w = NmapWrapper()
    result = w.parse(FIX.read_text())
    assert result == {
        "hosts": [
            {
                "ip": "192.168.1.45",
                "ports": [
                    {"port": 445, "service": "microsoft-ds", "version": "Samba 4.6"},
                    {"port": 22, "service": "ssh", "version": "OpenSSH 7.4"},
                ],
            }
        ]
    }

def test_nmap_tool_name_and_schema():
    w = NmapWrapper()
    assert w.tool_name == "nmap"
    assert "hosts" in w.schema

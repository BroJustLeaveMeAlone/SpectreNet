# tests/test_masscan_wrapper.py
from pathlib import Path
from spectrenet.wrappers.builtin.masscan import MasscanWrapper

FIX = Path(__file__).parent / "fixtures" / "masscan_sample.json"

def test_masscan_parses_json_into_normalized_schema():
    w = MasscanWrapper()
    result = w.parse(FIX.read_text())
    assert result == {
        "hosts": [
            {"ip": "192.168.1.45", "ports": [{"port": 445, "service": "", "version": ""}]},
            {"ip": "192.168.1.50", "ports": [{"port": 80, "service": "", "version": ""}]},
        ]
    }

def test_masscan_tool_name():
    assert MasscanWrapper().tool_name == "masscan"

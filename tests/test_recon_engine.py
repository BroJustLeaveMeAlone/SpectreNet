# tests/test_recon_engine.py
from spectrenet.engines.recon import ReconEngine
from spectrenet.wrappers.base import ToolWrapper

class StubNmap(ToolWrapper):
    tool_name = "nmap"
    @property
    def schema(self): return {"hosts": []}
    def run(self, **kw):
        return {"hosts": [{"ip": "10.0.0.1", "ports": [{"port": 22, "service": "ssh", "version": "8.0"}]}]}
    def is_available(self): return True

class FakeRegistry:
    def __init__(self): self._w = {"nmap": StubNmap()}
    def get(self, n): return self._w[n]
    def available(self): return ["nmap"]

def test_recon_engine_runs_named_tool_and_returns_hosts():
    eng = ReconEngine(FakeRegistry())
    result = eng.scan(tool="nmap", target="10.0.0.1")
    assert result["hosts"][0]["ip"] == "10.0.0.1"

def test_recon_engine_rejects_unavailable_tool():
    eng = ReconEngine(FakeRegistry())
    try:
        eng.scan(tool="zmap", target="10.0.0.1")
        assert False, "should have raised"
    except ValueError as e:
        assert "zmap" in str(e)

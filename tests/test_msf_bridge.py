# tests/test_msf_bridge.py
from spectrenet.msf.bridge import MsfBridge, MsfSession

class _FakeExploit(dict):
    def execute(self, payload=""):
        return {"job_id": 42}

class _FakeModules:
    def use(self, mtype, path):
        return _FakeExploit()

class _FakeSessions:
    @property
    def list(self):
        return {
            "1": {"type": "meterpreter", "tunnel_peer": "10.0.0.1:1234"}
        }

class _FakeClient:
    def __init__(self):
        self.modules = _FakeModules()
        self.sessions = _FakeSessions()

def test_bridge_connects_with_injected_client():
    bridge = MsfBridge(client=_FakeClient())
    assert bridge.connect() is True
    assert bridge.is_connected() is True

def test_bridge_run_module_returns_job_id():
    bridge = MsfBridge(client=_FakeClient())
    bridge.connect()
    job_id = bridge.run_module("exploit/multi/handler",
                               {"LHOST": "10.0.0.1", "LPORT": "4444"})
    assert job_id == "42"

def test_bridge_get_sessions_returns_list():
    bridge = MsfBridge(client=_FakeClient())
    bridge.connect()
    sessions = bridge.get_sessions()
    assert len(sessions) == 1
    assert sessions[0].type == "meterpreter"
    assert sessions[0].tunnel_peer == "10.0.0.1:1234"

def test_bridge_run_module_raises_when_not_connected():
    bridge = MsfBridge(client=_FakeClient())  # not yet connected
    try:
        bridge.run_module("exploit/multi/handler", {})
        assert False, "should raise"
    except RuntimeError as e:
        assert "connected" in str(e).lower()

def test_bridge_is_connected_false_by_default():
    bridge = MsfBridge(client=_FakeClient())
    assert bridge.is_connected() is False

def test_bridge_connect_fails_gracefully_without_pymetasploit3():
    # No injected client, no real msfrpcd — connect() must return False gracefully
    bridge = MsfBridge(host="127.0.0.1", port=19999)
    result = bridge.connect()
    assert result is False
    assert bridge.is_connected() is False

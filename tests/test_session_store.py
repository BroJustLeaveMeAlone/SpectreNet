# tests/test_session_store.py
from spectrenet.storage.session import SessionStore

def test_create_session_and_log_action(tmp_path):
    store = SessionStore(tmp_path / "s.db")
    sid = store.create_session(name="engagement-1", operator="alice", mode="classic")
    assert sid == 1
    store.log_action(sid, operator="alice", tool="nmap",
                     params={"target": "10.0.0.1"}, output_hash="abc123")
    actions = store.actions_for(sid)
    assert len(actions) == 1
    assert actions[0]["tool"] == "nmap"
    assert actions[0]["operator"] == "alice"

def test_actions_isolated_per_session(tmp_path):
    store = SessionStore(tmp_path / "s.db")
    s1 = store.create_session("a", "alice")
    s2 = store.create_session("b", "bob")
    store.log_action(s1, "alice", "nmap", {}, "h1")
    assert store.actions_for(s2) == []

import pytest
from spectrenet.engines.post_ex import PostExEngine, Session
from spectrenet.loot import LootVault


@pytest.fixture
def loot(tmp_path):
    return LootVault(str(tmp_path / "loot.json"))


@pytest.fixture
def engine(loot):
    return PostExEngine(loot=loot)


def test_register_session(engine):
    s = engine.register_session("10.0.0.1", "linux", "root", 1234)
    assert isinstance(s, Session)
    assert s.id == 1
    assert s.host == "10.0.0.1"
    assert s.platform == "linux"
    assert s.user == "root"
    assert s.pid  == 1234


def test_register_multiple_sessions(engine):
    s1 = engine.register_session("10.0.0.1")
    s2 = engine.register_session("10.0.0.2")
    s3 = engine.register_session("10.0.0.3")
    assert s1.id == 1
    assert s2.id == 2
    assert s3.id == 3
    assert len(engine.list_sessions()) == 3


def test_get_session(engine):
    s = engine.register_session("10.0.0.1", "windows")
    found = engine.get_session(s.id)
    assert found is s


def test_get_session_missing(engine):
    assert engine.get_session(999) is None


def test_kill_session(engine):
    s = engine.register_session("10.0.0.1")
    assert engine.kill_session(s.id) is True
    assert engine.get_session(s.id) is None
    assert engine.kill_session(s.id) is False


def test_list_sessions_empty(engine):
    assert engine.list_sessions() == []


def test_session_summary_empty(engine):
    assert "no active sessions" in engine.session_summary()


def test_session_summary(engine):
    engine.register_session("10.0.0.1", "linux", "root")
    summary = engine.session_summary()
    assert "10.0.0.1" in summary
    assert "linux" in summary
    assert "root" in summary


def test_extract_creds(engine, loot):
    output = 'password = "supersecret"\napi_key = "sk-abc123"\n'
    found  = engine.extract_creds(output)
    assert len(found) > 0
    entries = loot.by_type("cred")
    assert len(entries) > 0


def test_extract_hashes_ntlm(engine, loot):
    output = "Administrator:500:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0:::\n"
    found  = engine.extract_hashes(output)
    assert len(found) > 0
    entries = loot.by_type("hash")
    assert len(entries) > 0


def test_extract_hashes_shadow(engine, loot):
    output = "root:$6$salt$hashedpassword:18000:0:99999:7:::\n"
    found  = engine.extract_hashes(output)
    assert len(found) > 0


def test_extract_no_match(engine):
    output = "Hello world, no credentials here.\n"
    creds  = engine.extract_creds(output)
    hashes = engine.extract_hashes(output)
    assert creds  == []
    assert hashes == []


def test_auto_enum_linux(engine):
    cmds = engine.auto_enum_commands("linux")
    assert any("id" in c for c in cmds)
    assert any("uname" in c for c in cmds)
    assert len(cmds) >= 5


def test_auto_enum_windows(engine):
    cmds = engine.auto_enum_commands("windows")
    assert any("whoami" in c for c in cmds)
    assert any("systeminfo" in c for c in cmds)
    assert len(cmds) >= 5


def test_suggest_pivot(engine):
    s = engine.register_session("10.0.0.1", "linux", "root")
    suggestions = engine.suggest_pivot(s, ["192.168.1.1", "172.16.0.5"])
    assert len(suggestions) > 0
    combined = "\n".join(suggestions)
    assert "192.168.1.1" in combined


def test_run_local(engine):
    result = engine.run_local("echo hello")
    assert "hello" in result


def test_run_local_timeout(engine):
    result = engine.run_local("sleep 60", timeout=1)
    assert "[timeout]" in result

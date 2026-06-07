import json
import pytest
from pathlib import Path
from spectrenet.loot import LootVault


@pytest.fixture
def vault(tmp_path):
    return LootVault(str(tmp_path / "loot.json"))


def test_empty_vault(vault):
    assert vault.all() == []
    assert vault.summary() == "empty"


def test_add_cred(vault):
    vault.add("cred", "admin:password123")
    entries = vault.all()
    assert len(entries) == 1
    assert entries[0]["type"] == "cred"
    assert entries[0]["text"] == "admin:password123"
    assert "t" in entries[0]


def test_add_multiple_types(vault):
    vault.add("cred",   "admin:pass")
    vault.add("hash",   "aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0")
    vault.add("file",   "/etc/passwd")
    vault.add("secret", "AWS_KEY=AKIA...")
    assert len(vault.all()) == 4


def test_by_type(vault):
    vault.add("cred", "user:pass")
    vault.add("cred", "admin:admin")
    vault.add("hash", "deadbeef")
    creds = vault.by_type("cred")
    assert len(creds) == 2
    assert all(e["type"] == "cred" for e in creds)
    hashes = vault.by_type("hash")
    assert len(hashes) == 1


def test_summary_with_entries(vault):
    vault.add("cred", "a:b")
    vault.add("hash", "abc")
    vault.add("hash", "def")
    summary = vault.summary()
    assert "cred: 1" in summary
    assert "hash: 2" in summary


def test_persistence(tmp_path):
    path = str(tmp_path / "loot.json")
    v1 = LootVault(path)
    v1.add("cred", "user:pass")
    v1.add("secret", "token=abc123")

    v2 = LootVault(path)
    entries = v2.all()
    assert len(entries) == 2
    assert entries[0]["text"] == "user:pass"


def test_clear(vault):
    vault.add("cred", "user:pass")
    vault.add("hash", "deadbeef")
    vault.clear()
    assert vault.all() == []


def test_clear_persists(tmp_path):
    path = str(tmp_path / "loot.json")
    v1 = LootVault(path)
    v1.add("cred", "user:pass")
    v1.clear()
    v2 = LootVault(path)
    assert v2.all() == []


def test_empty_file_resilience(tmp_path):
    path = tmp_path / "loot.json"
    path.write_text("not-valid-json")
    v = LootVault(str(path))
    assert v.all() == []


def test_vault_types_constant():
    assert set(LootVault.TYPES) == {"cred", "hash", "file", "secret"}

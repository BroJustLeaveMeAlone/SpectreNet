"""
Tests for PgSessionStore — all mock-based (no real PostgreSQL server required).
"""
import json
import pytest
from unittest.mock import MagicMock, patch, call


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_store(mock_conn):
    """Instantiate PgSessionStore with a fully-mocked psycopg2 connection."""
    with patch("spectrenet.storage.pg_session._PG_AVAILABLE", True), \
         patch("spectrenet.storage.pg_session.psycopg2") as mock_pg:
        mock_pg.connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = lambda s: s
        mock_conn.cursor.return_value.__exit__  = MagicMock(return_value=False)
        from spectrenet.storage.pg_session import PgSessionStore
        store = PgSessionStore.__new__(PgSessionStore)
        store.conn = mock_conn
        return store


def _cursor_mock(fetchone=None, fetchall=None, description=None):
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__  = MagicMock(return_value=False)
    if fetchone is not None:
        cur.fetchone.return_value = fetchone
    if fetchall is not None:
        cur.fetchall.return_value = fetchall
    if description is not None:
        cur.description = description
    return cur


# ── Import guard ──────────────────────────────────────────────────────────────

def test_import_without_psycopg2():
    with patch("spectrenet.storage.pg_session._PG_AVAILABLE", False):
        from spectrenet.storage.pg_session import PgSessionStore
        with pytest.raises(RuntimeError, match="psycopg2"):
            PgSessionStore("postgresql://localhost/test")


# ── create_session ────────────────────────────────────────────────────────────

def test_create_session():
    conn = MagicMock()
    cur  = _cursor_mock(fetchone=(42,))
    conn.cursor.return_value = cur

    from spectrenet.storage.pg_session import PgSessionStore
    store = PgSessionStore.__new__(PgSessionStore)
    store.conn = conn
    sid = store.create_session("test-session", "alice", "classic")

    assert sid == 42
    conn.commit.assert_called()


# ── log_action ────────────────────────────────────────────────────────────────

def test_log_action():
    conn = MagicMock()
    cur  = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__  = MagicMock(return_value=False)
    conn.cursor.return_value = cur

    with patch("spectrenet.storage.pg_session._PG_AVAILABLE", True):
        from spectrenet.storage.pg_session import PgSessionStore
        store = PgSessionStore.__new__(PgSessionStore)
        store.conn = conn
        store.log_action(1, "alice", "nmap", {"target": "10.0.0.1"}, "hash123")

    cur.execute.assert_called_once()
    call_args = cur.execute.call_args[0]
    assert "INSERT INTO actions" in call_args[0]
    params = call_args[1]
    assert params[0] == 1
    assert params[2] == "alice"
    assert params[3] == "nmap"
    assert json.loads(params[4]) == {"target": "10.0.0.1"}
    conn.commit.assert_called()


# ── actions_for ───────────────────────────────────────────────────────────────

def test_actions_for():
    conn = MagicMock()
    cur  = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__  = MagicMock(return_value=False)
    cur.description = [("id",), ("session_id",), ("ts",), ("operator",), ("tool",), ("params",), ("output_hash",)]
    cur.fetchall.return_value = [
        (1, 1, "2026-01-01T00:00:00", "alice", "nmap", '{"target":"10.0.0.1"}', "abc"),
    ]
    conn.cursor.return_value = cur

    with patch("spectrenet.storage.pg_session._PG_AVAILABLE", True):
        from spectrenet.storage.pg_session import PgSessionStore
        store = PgSessionStore.__new__(PgSessionStore)
        store.conn = conn
        actions = store.actions_for(1)

    assert len(actions) == 1
    assert actions[0]["tool"] == "nmap"
    assert actions[0]["operator"] == "alice"


# ── log_approval ──────────────────────────────────────────────────────────────

def test_log_approval_string():
    conn = MagicMock()
    cur  = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__  = MagicMock(return_value=False)
    conn.cursor.return_value = cur

    with patch("spectrenet.storage.pg_session._PG_AVAILABLE", True):
        from spectrenet.storage.pg_session import PgSessionStore
        store = PgSessionStore.__new__(PgSessionStore)
        store.conn = conn
        store.log_approval(1, "alice", "exploit", "10.0.0.1", "HIGH", "approve")

    cur.execute.assert_called_once()
    assert "INSERT INTO approvals" in cur.execute.call_args[0][0]


def test_log_approval_enum():
    from spectrenet.tui.approval_gate import ApprovalResult
    conn = MagicMock()
    cur  = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__  = MagicMock(return_value=False)
    conn.cursor.return_value = cur

    with patch("spectrenet.storage.pg_session._PG_AVAILABLE", True):
        from spectrenet.storage.pg_session import PgSessionStore
        store = PgSessionStore.__new__(PgSessionStore)
        store.conn = conn
        store.log_approval(1, "alice", "exploit", "10.0.0.1", "HIGH", ApprovalResult.APPROVED)

    params = cur.execute.call_args[0][1]
    assert params[-1] == ApprovalResult.APPROVED.value

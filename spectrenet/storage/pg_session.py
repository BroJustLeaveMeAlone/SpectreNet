"""
PostgreSQL-backed session store — drop-in replacement for the SQLite SessionStore.

Requires: pip install psycopg2-binary

Usage:
    store = PgSessionStore("postgresql://user:pass@localhost:5432/spectrenet")
    sid = store.create_session("pentest-01", "operator", "classic")
    store.log_action(sid, "operator", "nmap", {"target": "10.0.0.1"}, "abc123")
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

try:
    import psycopg2                          # type: ignore
    import psycopg2.extras                   # type: ignore
    _PG_AVAILABLE = True
except ImportError:
    _PG_AVAILABLE = False

from spectrenet.tui.approval_gate import ApprovalResult

_DDL = """\
CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    name        TEXT    NOT NULL,
    operator    TEXT    NOT NULL,
    started_at  TEXT    NOT NULL,
    mode        TEXT    NOT NULL DEFAULT 'classic'
);

CREATE TABLE IF NOT EXISTS actions (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    ts          TEXT    NOT NULL,
    operator    TEXT    NOT NULL,
    tool        TEXT    NOT NULL,
    params      TEXT,
    output_hash TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    ts          TEXT    NOT NULL,
    operator    TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    target      TEXT    NOT NULL,
    risk        TEXT    NOT NULL,
    result      TEXT    NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PgSessionStore:
    """PostgreSQL session store with the same interface as the SQLite SessionStore."""

    def __init__(self, dsn: str) -> None:
        if not _PG_AVAILABLE:
            raise RuntimeError(
                "psycopg2 not installed — run: pip install psycopg2-binary"
            )
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = False
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(_DDL)
        self.conn.commit()

    def _row_to_dict(self, row, cursor) -> dict:
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, name: str, operator: str, mode: str = "classic") -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (name, operator, started_at, mode) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (name, operator, _now(), mode),
            )
            row = cur.fetchone()
        self.conn.commit()
        return row[0]

    # ── Actions ───────────────────────────────────────────────────────────────

    def log_action(
        self,
        session_id: int,
        operator:   str,
        tool:       str,
        params:     dict,
        output_hash: str,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO actions "
                "(session_id, ts, operator, tool, params, output_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (session_id, _now(), operator, tool, json.dumps(params), output_hash),
            )
        self.conn.commit()

    def actions_for(self, session_id: int) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM actions WHERE session_id=%s ORDER BY id",
                (session_id,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    # ── Approvals ─────────────────────────────────────────────────────────────

    def log_approval(
        self,
        session_id: int,
        operator:   str,
        action:     str,
        target:     str,
        risk:       str,
        result:     str | ApprovalResult,
    ) -> None:
        if isinstance(result, ApprovalResult):
            result = result.value
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO approvals "
                "(session_id, ts, operator, action, target, risk, result) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (session_id, _now(), operator, action, target, risk, result),
            )
        self.conn.commit()

    def approvals_for(self, session_id: int) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM approvals WHERE session_id=%s ORDER BY id",
                (session_id,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()

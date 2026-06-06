# spectrenet/storage/session.py
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = Path(__file__).parent / "schema.sql"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class SessionStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA.read_text())
        self.conn.commit()

    def create_session(self, name: str, operator: str, mode: str = "classic") -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions (name, operator, started_at, mode) VALUES (?,?,?,?)",
            (name, operator, _now(), mode),
        )
        self.conn.commit()
        return cur.lastrowid

    def log_action(self, session_id: int, operator: str, tool: str,
                   params: dict, output_hash: str) -> None:
        self.conn.execute(
            "INSERT INTO actions (session_id, ts, operator, tool, params, output_hash) "
            "VALUES (?,?,?,?,?,?)",
            (session_id, _now(), operator, tool, json.dumps(params), output_hash),
        )
        self.conn.commit()

    def actions_for(self, session_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM actions WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

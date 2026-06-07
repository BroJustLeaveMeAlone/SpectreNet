# spectrenet/knowledge/cve_db.py
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).parent / "schema.sql"

class CVEKnowledgeBase:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA.read_text())
        self.conn.commit()

    def add_cve(self, cve_id: str, cvss: float, service: str,
                version_match: str, description: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO cves VALUES (?,?,?,?,?)",
            (cve_id, cvss, service, version_match, description),
        )
        self.conn.commit()

    def find_by_service(self, service: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM cves WHERE service=? ORDER BY cvss DESC", (service,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self.conn.close()

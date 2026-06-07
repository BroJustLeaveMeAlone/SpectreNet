CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    operator TEXT NOT NULL,
    started_at TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'classic'
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    operator TEXT NOT NULL,
    tool TEXT NOT NULL,
    params TEXT,
    output_hash TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    operator TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    risk TEXT NOT NULL,
    result TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

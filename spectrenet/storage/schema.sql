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

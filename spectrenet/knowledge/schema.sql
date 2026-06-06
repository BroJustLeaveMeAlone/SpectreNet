CREATE TABLE IF NOT EXISTS cves (
    cve_id TEXT PRIMARY KEY,
    cvss REAL,
    service TEXT,
    version_match TEXT,
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_cves_service ON cves(service);

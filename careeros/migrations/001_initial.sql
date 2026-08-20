CREATE TABLE IF NOT EXISTS migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    source_connector TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    title TEXT NOT NULL,
    period TEXT,
    tags TEXT NOT NULL,
    context TEXT,
    confidence TEXT,
    situation TEXT,
    task TEXT,
    action TEXT,
    result TEXT,
    content_fingerprint TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL REFERENCES records(id),
    locator TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grant_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    scopes TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    revoked_at TEXT,
    UNIQUE(grant_type, resource_id)
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    destination_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL
);

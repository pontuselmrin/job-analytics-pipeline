CREATE TABLE organizations (
    org_abbrev TEXT PRIMARY KEY,
    org_name   TEXT NOT NULL,
    enriched_at TIMESTAMPTZ
);

CREATE TABLE jobs (
    url           TEXT PRIMARY KEY,
    org_abbrev    TEXT NOT NULL REFERENCES organizations(org_abbrev),
    title         TEXT NOT NULL,
    content_type  TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    pdf_path      TEXT NOT NULL DEFAULT '',
    enriched_at   TIMESTAMPTZ,
    enrich_error  TEXT NOT NULL DEFAULT '',
    enrich_status TEXT NOT NULL DEFAULT '',
    status_reason TEXT NOT NULL DEFAULT '',
    fetch_method  TEXT NOT NULL DEFAULT '',
    fetch_seconds REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS boilerplate_sentences (
    id         SERIAL PRIMARY KEY,
    org_abbrev TEXT NOT NULL REFERENCES organizations(org_abbrev),
    sentence   TEXT NOT NULL,
    frequency  REAL NOT NULL,
    UNIQUE (org_abbrev, sentence)
);

CREATE TABLE IF NOT EXISTS fetch_failures (
    url           TEXT PRIMARY KEY,
    org_abbrev    TEXT NOT NULL REFERENCES organizations(org_abbrev),
    title         TEXT NOT NULL DEFAULT '',
    fail_count    INTEGER NOT NULL DEFAULT 1,
    last_error    TEXT NOT NULL DEFAULT '',
    last_status   TEXT NOT NULL DEFAULT '',
    last_reason   TEXT NOT NULL DEFAULT '',
    first_failed  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_failed   TIMESTAMPTZ NOT NULL DEFAULT now()
);

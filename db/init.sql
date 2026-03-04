CREATE TABLE organizations (
    org_abbrev TEXT PRIMARY KEY,
    org_name   TEXT NOT NULL,
    enriched_at TIMESTAMPTZ
);

CREATE TABLE jobs (
    id            SERIAL PRIMARY KEY,
    org_abbrev    TEXT NOT NULL REFERENCES organizations(org_abbrev),
    title         TEXT NOT NULL,
    url           TEXT NOT NULL,
    content_type  TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    pdf_path      TEXT NOT NULL DEFAULT '',
    enriched_at   TIMESTAMPTZ,
    enrich_error  TEXT NOT NULL DEFAULT '',
    enrich_status TEXT NOT NULL DEFAULT '',
    status_reason TEXT NOT NULL DEFAULT '',
    fetch_method  TEXT NOT NULL DEFAULT '',
    fetch_seconds REAL NOT NULL DEFAULT 0.0,
    UNIQUE (org_abbrev, url)
);

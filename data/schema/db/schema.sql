CREATE TABLE poll_log (
  id INTEGER PRIMARY KEY,
  ran_at TEXT NOT NULL,
  source TEXT NOT NULL,
  company_slug TEXT NOT NULL,
  ok INTEGER NOT NULL,
  postings_seen INTEGER NOT NULL DEFAULT 0,
  new_postings INTEGER NOT NULL DEFAULT 0,
  error TEXT
);
CREATE TABLE postings (
  id INTEGER PRIMARY KEY,
  fingerprint TEXT NOT NULL UNIQUE,
  content_key TEXT NOT NULL,
  company_slug TEXT NOT NULL,
  source TEXT NOT NULL,
  source_id TEXT,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  location TEXT,
  remote_class TEXT,
  comp_min INTEGER,
  comp_max INTEGER,
  comp_currency TEXT,
  comp_found INTEGER NOT NULL DEFAULT 0,
  description TEXT,
  posted_at TEXT,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  closed_at TEXT,
  score REAL,
  score_json TEXT,
  ruleset_version TEXT
);
CREATE TABLE status_log (
  id INTEGER PRIMARY KEY,
  posting_id INTEGER NOT NULL REFERENCES postings(id),
  state TEXT NOT NULL CHECK (state IN ('new','interested','applied','rejected','ignored','interview','offer')),
  noted_at TEXT NOT NULL,
  letter_path TEXT,
  note TEXT
);
CREATE INDEX postings_company ON postings(company_slug);
CREATE INDEX postings_content_key ON postings(content_key);
CREATE INDEX status_log_posting ON status_log(posting_id);

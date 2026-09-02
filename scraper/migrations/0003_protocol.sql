ALTER TABLE postings ADD COLUMN pile TEXT;
ALTER TABLE postings ADD COLUMN drop_reason TEXT;
ALTER TABLE postings ADD COLUMN contact_hint TEXT;
ALTER TABLE postings ADD COLUMN employment_type TEXT;
CREATE TABLE status_log_v2 (
  id INTEGER PRIMARY KEY,
  posting_id INTEGER NOT NULL REFERENCES postings(id),
  state TEXT NOT NULL CHECK (state IN ('new','reviewed','applied','screen','loop','offer','rejected','skipped')),
  noted_at TEXT NOT NULL,
  letter_path TEXT,
  note TEXT
);
INSERT INTO status_log_v2 (id, posting_id, state, noted_at, letter_path, note)
  SELECT id, posting_id,
    CASE state WHEN 'interested' THEN 'reviewed' WHEN 'ignored' THEN 'skipped' WHEN 'interview' THEN 'screen' ELSE state END,
    noted_at, letter_path, note
  FROM status_log;
DROP INDEX IF EXISTS status_log_posting;
DROP TABLE status_log;
ALTER TABLE status_log_v2 RENAME TO status_log;
CREATE INDEX status_log_posting ON status_log(posting_id);

"""The only writer of postings.db. Forward-only SQL migrations applied by
PRAGMA user_version. Status is a log, never a mutable column, because a
nine-month search wants its history."""

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS = Path(__file__).parent / "migrations"
STATES = ("new", "reviewed", "applied", "screen", "loop", "offer", "rejected", "skipped")
# Anything past reviewed is Matt's and never resurfaces in a digest.
TERMINAL = ("applied", "screen", "loop", "offer", "rejected", "skipped")

_REFRESH = ("title", "url", "location", "remote_class", "comp_min", "comp_max", "comp_currency", "comp_found", "description", "posted_at", "contact_hint", "employment_type")


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def content_key(company_slug, title):
    norm = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    return hashlib.sha256(f"{company_slug}|{norm}".encode()).hexdigest()[:32]


def fingerprint(p):
    if p.get("source_id"):
        return f"{p['source']}:{p['source_id']}"
    return content_key(p["company_slug"], p["title"])


class Store:
    def __init__(self, path):
        self.path = str(path)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    def close(self):
        self.db.close()

    # migrations

    def migrate(self):
        current = self.db.execute("PRAGMA user_version").fetchone()[0]
        for f in sorted(MIGRATIONS.glob("*.sql")):
            n = int(f.name.split("_", 1)[0])
            if n <= current:
                continue
            self.db.executescript(f.read_text(encoding="utf-8"))
            self.db.execute(f"PRAGMA user_version = {n}")
            self.db.commit()
        return self.db.execute("PRAGMA user_version").fetchone()[0]

    def schema_dump(self):
        rows = self.db.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name"
        ).fetchall()
        return "\n".join(r["sql"].strip() + ";" for r in rows) + "\n"

    # postings

    def upsert(self, p, seen_at=None):
        """Insert or refresh one normalized posting. Returns (id, is_new).
        A posting whose fingerprint is unknown but whose content key matches an
        open posting at the same company from a different source is the same
        role seen through a new ATS, so the row is re-keyed rather than
        duplicated. Same source, new id, same title is a second opening."""
        seen_at = seen_at or utcnow()
        fp = fingerprint(p)
        ck = content_key(p["company_slug"], p["title"])
        comp_found = 1 if (p.get("comp_min") is not None or p.get("comp_max") is not None) else 0
        values = {
            "title": p["title"],
            "url": p["url"],
            "location": p.get("location"),
            "remote_class": p.get("remote"),
            "comp_min": p.get("comp_min"),
            "comp_max": p.get("comp_max"),
            "comp_currency": p.get("comp_currency"),
            "comp_found": comp_found,
            "description": p.get("description"),
            "posted_at": p.get("posted_at"),
            "contact_hint": p.get("contact_hint"),
            "employment_type": p.get("employment_type"),
        }
        row = self.db.execute("SELECT id FROM postings WHERE fingerprint = ?", (fp,)).fetchone()
        if row is None:
            row = self.db.execute(
                "SELECT id FROM postings WHERE company_slug = ? AND content_key = ? AND closed_at IS NULL AND source != ?",
                (p["company_slug"], ck, p["source"]),
            ).fetchone()
            if row is not None:
                self.db.execute(
                    "UPDATE postings SET fingerprint = ?, source = ?, source_id = ? WHERE id = ?",
                    (fp, p["source"], p.get("source_id"), row["id"]),
                )
        if row is None:
            cur = self.db.execute(
                "INSERT INTO postings (fingerprint, content_key, company_slug, source, source_id, "
                + ", ".join(_REFRESH)
                + ", first_seen, last_seen) VALUES (?, ?, ?, ?, ?, "
                + ", ".join("?" for _ in _REFRESH)
                + ", ?, ?)",
                (fp, ck, p["company_slug"], p["source"], p.get("source_id"), *[values[k] for k in _REFRESH], seen_at, seen_at),
            )
            pid = cur.lastrowid
            self.db.execute(
                "INSERT INTO status_log (posting_id, state, noted_at) VALUES (?, 'new', ?)", (pid, seen_at)
            )
            self.db.commit()
            return pid, True
        self.db.execute(
            "UPDATE postings SET " + ", ".join(f"{k} = ?" for k in _REFRESH) + ", last_seen = ?, closed_at = NULL WHERE id = ?",
            (*[values[k] for k in _REFRESH], seen_at, row["id"]),
        )
        self.db.commit()
        return row["id"], False

    def close_unlisted(self, listed, at=None):
        """A posting whose company is no longer on the list is closed. Discovery
        adds companies and a bad night gets cleaned up by removing them, so the
        postings they brought must not linger in the store."""
        at = at or utcnow()
        rows = self.db.execute("SELECT id, company_slug FROM postings WHERE closed_at IS NULL").fetchall()
        gone = [r["id"] for r in rows if r["company_slug"] not in set(listed)]
        if gone:
            self.db.executemany("UPDATE postings SET closed_at = ? WHERE id = ?", [(at, i) for i in gone])
            self.db.commit()
        return len(gone)

    def close_missing(self, company_slug, source, seen_fingerprints, at=None):
        """A posting that stopped appearing in a successful poll is closed, not deleted."""
        at = at or utcnow()
        rows = self.db.execute(
            "SELECT id, fingerprint FROM postings WHERE company_slug = ? AND source = ? AND closed_at IS NULL",
            (company_slug, source),
        ).fetchall()
        seen = set(seen_fingerprints)
        gone = [r["id"] for r in rows if r["fingerprint"] not in seen]
        if gone:
            self.db.executemany("UPDATE postings SET closed_at = ? WHERE id = ?", [(at, i) for i in gone])
            self.db.commit()
        return len(gone)

    def log_poll(self, ran_at, source, company_slug, ok, seen=0, new=0, error=None):
        self.db.execute(
            "INSERT INTO poll_log (ran_at, source, company_slug, ok, postings_seen, new_postings, error) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ran_at, source, company_slug, 1 if ok else 0, seen, new, error),
        )
        self.db.commit()

    # status

    def mark(self, posting_id, state, note=None, letter_path=None, at=None):
        if state not in STATES:
            raise ValueError(f"state must be one of {STATES}, got {state!r}")
        if self.db.execute("SELECT 1 FROM postings WHERE id = ?", (posting_id,)).fetchone() is None:
            raise KeyError(f"no posting with id {posting_id}")
        self.db.execute(
            "INSERT INTO status_log (posting_id, state, noted_at, letter_path, note) VALUES (?, ?, ?, ?, ?)",
            (posting_id, state, at or utcnow(), letter_path, note),
        )
        self.db.commit()

    def state_of(self, posting_id):
        row = self.db.execute(
            "SELECT state FROM status_log WHERE posting_id = ? ORDER BY id DESC LIMIT 1", (posting_id,)
        ).fetchone()
        return row["state"] if row else None

    def get(self, posting_id):
        row = self.db.execute("SELECT * FROM postings WHERE id = ?", (posting_id,)).fetchone()
        return dict(row) if row else None

    # scoring and digest

    def set_score(self, posting_id, result):
        self.db.execute(
            "UPDATE postings SET score = ?, score_json = ?, ruleset_version = ?, pile = ?, drop_reason = ? WHERE id = ?",
            (result["score"], json.dumps(result), result["version"], result.get("pile"), result.get("drop_reason"), posting_id),
        )
        self.db.commit()

    def new_by_source(self, since):
        rows = self.db.execute("SELECT source, COUNT(*) AS n FROM postings WHERE first_seen >= ? GROUP BY source", (since,)).fetchall()
        return {r["source"]: r["n"] for r in rows}

    def drop_counts(self, since):
        rows = self.db.execute(
            "SELECT drop_reason, COUNT(*) AS n FROM postings WHERE pile = 'logged' AND drop_reason IS NOT NULL AND first_seen >= ? GROUP BY drop_reason",
            (since,),
        ).fetchall()
        return {r["drop_reason"]: r["n"] for r in rows}

    def open_postings(self):
        rows = self.db.execute("SELECT * FROM postings WHERE closed_at IS NULL ORDER BY score DESC, first_seen").fetchall()
        return [dict(r) for r in rows]

    def study_rows(self):
        """Open postings in a pile that Matt has not skipped or been rejected
        from. Applied and interviewing postings stay in, because they are the
        best evidence of what the target asks for; a skipped one has nothing
        left to teach."""
        return [r for r in self.open_postings() if r.get("pile") in ("apply", "review") and self.state_of(r["id"]) not in ("skipped", "rejected")]

    def mark_digested(self, ids, at, hasher):
        for pid in ids:
            self.db.execute("UPDATE postings SET digested_at = ?, digest_hash = ? WHERE id = ?", (at, hasher(self.get(pid)), pid))
        self.db.commit()

    def poll_errors_since(self, since):
        rows = self.db.execute(
            "SELECT ran_at, source, company_slug, error FROM poll_log WHERE ok = 0 AND ran_at >= ? ORDER BY ran_at DESC", (since,)
        ).fetchall()
        return [dict(r) for r in rows]

    def never_answered(self, since):
        """{(source, company_slug)} that only ever errored in the window. A
        board that fails some polls is drifting, but one that fails every poll
        is a company sitting on the list without being polled at all, which
        looks the same as a company with nothing open."""
        rows = self.db.execute(
            "SELECT source, company_slug, SUM(ok) AS ok, COUNT(*) AS n "
            "FROM poll_log WHERE ran_at >= ? GROUP BY source, company_slug", (since,)
        ).fetchall()
        return {(r["source"], r["company_slug"]) for r in rows if (r["ok"] or 0) == 0}

    def recovered_since(self, since):
        """{(source, company_slug)} whose most recent poll in the window
        succeeded. An error that has since been fixed is history, not health,
        and a footer that keeps naming it for a week is a footer that gets
        read past, which costs the real outage its only warning."""
        rows = self.db.execute(
            "SELECT source, company_slug, ok FROM poll_log WHERE ran_at >= ? ORDER BY id DESC", (since,)
        ).fetchall()
        latest = {}
        for r in rows:
            latest.setdefault((r["source"], r["company_slug"]), r["ok"])
        return {k for k, ok in latest.items() if ok}

    def zero_twice_running(self):
        """(company_slug, source) pairs whose last two successful polls saw nothing."""
        rows = self.db.execute("SELECT company_slug, source, postings_seen FROM poll_log WHERE ok = 1 ORDER BY id DESC").fetchall()
        seen = {}
        for r in rows:
            seen.setdefault((r["company_slug"], r["source"]), []).append(r["postings_seen"])
        return [k for k, v in seen.items() if len(v) >= 2 and v[0] == 0 and v[1] == 0]

    def company_yield(self):
        """[{company_slug, postings, on_target}] over the whole store, worst
        first. on_target counts postings that ever reached a pile other than
        logged, so a company polling hundreds of listings and clearing none of
        them is visible as what it is: polling budget spent for nothing."""
        rows = self.db.execute(
            "SELECT company_slug, COUNT(*) AS postings, "
            "SUM(CASE WHEN pile IS NOT NULL AND pile != 'logged' THEN 1 ELSE 0 END) AS on_target "
            "FROM postings GROUP BY company_slug"
        ).fetchall()
        out = [{"company_slug": r["company_slug"], "postings": r["postings"], "on_target": r["on_target"] or 0} for r in rows]
        return sorted(out, key=lambda r: (r["on_target"], -r["postings"]))

    def company_drop_reasons(self):
        """{company_slug: [(reason, n), ...]} most common first, over logged
        rows. This is what lets the dead-weight section say why a company's
        postings died, so a gate miss and a real absence stop printing the
        same line."""
        rows = self.db.execute(
            "SELECT company_slug, drop_reason, COUNT(*) AS n FROM postings "
            "WHERE pile = 'logged' AND drop_reason IS NOT NULL GROUP BY company_slug, drop_reason"
        ).fetchall()
        out = {}
        for r in rows:
            out.setdefault(r["company_slug"], []).append((r["drop_reason"], r["n"]))
        for slug in out:
            out[slug].sort(key=lambda x: -x[1])
        return out

    def stats(self, since=None):
        """Counts. With `since` (ISO date or datetime), the period fields count
        only what happened on or after it; the totals stay whole-store."""
        q = lambda sql, *a: self.db.execute(sql, a).fetchone()[0]
        by_state = self.db.execute(
            "SELECT s.state, COUNT(*) AS n FROM status_log s "
            "JOIN (SELECT posting_id, MAX(id) AS id FROM status_log GROUP BY posting_id) last ON last.id = s.id "
            "GROUP BY s.state"
        ).fetchall()
        out = {
            "postings": q("SELECT COUNT(*) FROM postings"),
            "open": q("SELECT COUNT(*) FROM postings WHERE closed_at IS NULL"),
            "comp_found": q("SELECT COUNT(*) FROM postings WHERE comp_found = 1"),
            "by_state": {r["state"]: r["n"] for r in by_state},
            "polls": q("SELECT COUNT(*) FROM poll_log"),
            "poll_errors": q("SELECT COUNT(*) FROM poll_log WHERE ok = 0"),
        }
        if since:
            transitions = self.db.execute(
                "SELECT state, COUNT(*) AS n FROM status_log WHERE noted_at >= ? AND state != 'new' GROUP BY state", (since,)
            ).fetchall()
            out["period"] = {
                "since": since,
                "seen": q("SELECT COUNT(*) FROM postings WHERE first_seen >= ?", since),
                "surfaced": q("SELECT COUNT(*) FROM postings WHERE digested_at >= ?", since),
                "transitions": {r["state"]: r["n"] for r in transitions},
                "polls": q("SELECT COUNT(*) FROM poll_log WHERE ran_at >= ?", since),
                "poll_errors": q("SELECT COUNT(*) FROM poll_log WHERE ran_at >= ? AND ok = 0", since),
            }
        return out

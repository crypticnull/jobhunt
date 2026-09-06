import unittest
from pathlib import Path

from scraper.posting import posting
from scraper.store import Store, content_key, fingerprint

ROOT = Path(__file__).resolve().parents[2]


def p(**kw):
    base = dict(source="greenhouse", source_id="1", company_slug="acme", title="Creative Technologist", url="https://x/1", remote="remote")
    base.update(kw)
    return posting(**base)


class Migrations(unittest.TestCase):
    def test_fresh_store_is_at_latest_version(self):
        s = Store(":memory:")
        self.assertEqual(s.migrate(), 3)

    def test_schema_matches_committed_reference(self):
        """data/schema/db/schema.sql is the readable contract; the migrations are
        the truth. Regenerate the reference when a migration lands."""
        ref = (ROOT / "data" / "schema" / "db" / "schema.sql").read_text(encoding="utf-8")
        self.assertEqual(Store(":memory:").schema_dump(), ref)


class Upsert(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")

    def test_new_then_seen(self):
        pid, new = self.s.upsert(p(), "2026-09-01T00:00:00+00:00")
        self.assertTrue(new)
        self.assertEqual(self.s.state_of(pid), "new")
        pid2, new2 = self.s.upsert(p(title="Creative Technologist II"), "2026-09-02T00:00:00+00:00")
        self.assertEqual((pid2, new2), (pid, False))
        row = self.s.get(pid)
        self.assertEqual(row["title"], "Creative Technologist II")
        self.assertEqual(row["first_seen"], "2026-09-01T00:00:00+00:00")
        self.assertEqual(row["last_seen"], "2026-09-02T00:00:00+00:00")

    def test_comp_found_flag(self):
        pid, _ = self.s.upsert(p(comp_min=150000))
        self.assertEqual(self.s.get(pid)["comp_found"], 1)
        pid2, _ = self.s.upsert(p(source_id="2"))
        self.assertEqual(self.s.get(pid2)["comp_found"], 0)

    def test_same_role_through_new_ats_is_rekeyed_not_duplicated(self):
        pid, _ = self.s.upsert(p(source="greenhouse", source_id="9"))
        pid2, new = self.s.upsert(p(source="lever", source_id="abc"))
        self.assertEqual((pid2, new), (pid, False))
        self.assertEqual(self.s.get(pid)["fingerprint"], "lever:abc")

    def test_same_title_same_source_new_id_is_a_second_opening(self):
        a, _ = self.s.upsert(p(source_id="1"))
        b, new = self.s.upsert(p(source_id="2"))
        self.assertTrue(new)
        self.assertNotEqual(a, b)

    def test_fingerprint_without_source_id_uses_content_key(self):
        q = p(source_id=None)
        self.assertEqual(fingerprint(q), content_key("acme", "Creative Technologist"))
        self.assertEqual(content_key("acme", "  creative   TECHNOLOGIST!"), content_key("acme", "Creative Technologist"))

    def test_close_missing_then_reopen(self):
        a, _ = self.s.upsert(p(source_id="1"))
        b, _ = self.s.upsert(p(source_id="2", title="Motion Designer"))
        closed = self.s.close_missing("acme", "greenhouse", [fingerprint(p(source_id="1"))], "2026-09-03T00:00:00+00:00")
        self.assertEqual(closed, 1)
        self.assertIsNone(self.s.get(a)["closed_at"])
        self.assertEqual(self.s.get(b)["closed_at"], "2026-09-03T00:00:00+00:00")
        self.s.upsert(p(source_id="2", title="Motion Designer"))
        self.assertIsNone(self.s.get(b)["closed_at"], "a posting that comes back reopens")


class Unlisted(unittest.TestCase):
    def test_postings_of_a_removed_company_are_closed(self):
        """A bad discovery night is cleaned up by dropping the companies, so
        the postings they brought must not linger open in the store."""
        s = Store(":memory:")
        keep, _ = s.upsert(p(company_slug="acme", source_id="1"))
        drop, _ = s.upsert(p(company_slug="junk-co", source_id="2"))
        self.assertEqual(s.close_unlisted({"acme"}, "2026-09-02T00:00:00+00:00"), 1)
        self.assertIsNone(s.get(keep)["closed_at"])
        self.assertEqual(s.get(drop)["closed_at"], "2026-09-02T00:00:00+00:00")
        self.assertEqual(s.close_unlisted({"acme"}), 0, "already closed, nothing to do")


class Status(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.pid, _ = self.s.upsert(p())

    def test_mark_is_a_log(self):
        self.s.mark(self.pid, "reviewed")
        self.s.mark(self.pid, "applied", note="sent", letter_path="data/local/letters/acme.md")
        self.assertEqual(self.s.state_of(self.pid), "applied")
        rows = self.s.db.execute("SELECT state FROM status_log WHERE posting_id = ? ORDER BY id", (self.pid,)).fetchall()
        self.assertEqual([r["state"] for r in rows], ["new", "reviewed", "applied"])

    def test_bad_state_and_bad_id(self):
        with self.assertRaises(ValueError):
            self.s.mark(self.pid, "maybe")
        with self.assertRaises(KeyError):
            self.s.mark(999, "applied")

    def test_stats(self):
        self.s.mark(self.pid, "applied")
        self.s.upsert(p(source_id="2", comp_min=1))
        self.s.log_poll("2026-09-01T00:00:00+00:00", "greenhouse", "acme", True, 2, 2)
        self.s.log_poll("2026-09-01T00:00:00+00:00", "lever", "other", False, error="boom")
        st = self.s.stats()
        self.assertEqual((st["postings"], st["open"], st["comp_found"]), (2, 2, 1))
        self.assertEqual(st["by_state"], {"applied": 1, "new": 1})
        self.assertEqual((st["polls"], st["poll_errors"]), (2, 1))

    def test_stats_counts_bodies_per_source(self):
        """A posting with no body is one he cannot judge, so the gap is counted
        rather than averaged away, and per source so it names the adapter."""
        # Distinct titles, because same company plus same title from another
        # source is one role seen twice and upsert re-keys rather than adds.
        self.s.upsert(p(source_id="2", title="Technical Artist", description="a real body"))
        self.s.upsert(p(source="lever", source_id="3", title="Pipeline TD", url="https://x/3", description=""))
        self.s.upsert(p(source="lever", source_id="4", title="Motion Lead", url="https://x/4", description=None))
        d = self.s.stats()["described"]
        self.assertEqual(d["greenhouse"], {"open": 2, "with_body": 1, "longest": len("a real body")})
        self.assertEqual(d["lever"], {"open": 2, "with_body": 0, "longest": 0})

    def test_stats_ignores_closed_postings_when_counting_bodies(self):
        """Coverage is about what he is being shown, and a closed posting is not."""
        pid, _ = self.s.upsert(p(source_id="9", title="Tools Engineer", url="https://x/9", description=""))
        self.assertEqual(self.s.stats()["described"]["greenhouse"]["open"], 2)
        self.s.db.execute("UPDATE postings SET closed_at = ? WHERE id = ?", ("2026-09-06", pid))
        self.s.db.commit()
        self.assertEqual(self.s.stats()["described"]["greenhouse"]["open"], 1)

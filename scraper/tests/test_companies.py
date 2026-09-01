import tempfile
import unittest
from pathlib import Path

from scraper import companies


def rec(slug, kind="greenhouse", board="acme", reviewed="2026-09-01", priority=2):
    r = companies.record(slug, slug.title(), kind, board, "ai-video", priority, today="2026-09-01")
    r["last_reviewed"] = reviewed
    return r


class Records(unittest.TestCase):
    def test_record_shape_matches_example(self):
        r = rec("acme")
        self.assertEqual(set(r), {"slug", "name", "careers_url", "ats", "category", "priority", "lead_proof", "remote_notes", "contacts", "notes", "added", "last_reviewed"})

    def test_rejects_bad_category_and_kind(self):
        with self.assertRaises(ValueError):
            companies.record("a", "A", "lever", "a", "startup")
        with self.assertRaises(ValueError):
            companies.record("a", "A", "linkedin", "a", "ai-video")

    def test_add_rejects_duplicate_slug(self):
        data = companies.empty()
        companies.add(data, rec("acme"))
        with self.assertRaises(ValueError):
            companies.add(data, rec("acme"))

    def test_slugify(self):
        self.assertEqual(companies.slugify("Black Forest Labs, Inc."), "black-forest-labs-inc")


class Files(unittest.TestCase):
    def test_roundtrip_sorted_by_priority(self):
        data = companies.empty()
        companies.add(data, rec("zeta", priority=1))
        companies.add(data, rec("alpha", priority=2))
        companies.add(data, rec("beta", priority=1))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nested" / "companies.json"
            companies.save(path, data)
            back = companies.load(path)
        self.assertEqual([c["slug"] for c in back["companies"]], ["beta", "zeta", "alpha"])

    def test_missing_file_is_empty(self):
        self.assertEqual(companies.load("/nonexistent/companies.json"), companies.empty())

    def test_example_file_loads(self):
        root = Path(__file__).resolve().parents[2]
        data = companies.load(root / "data" / "companies.example.json")
        self.assertGreaterEqual(len(data["companies"]), 3)


class CheckAndStale(unittest.TestCase):
    def test_check_uses_probe_and_skips_manual(self):
        data = companies.empty()
        companies.add(data, rec("live"))
        companies.add(data, rec("dead", kind="lever", board="dead"))
        companies.add(data, rec("hand", kind="manual", board=None))

        def probe(kind, board):
            return (True, 7, None) if board == "acme" else (False, 0, "404")

        out = {r["slug"]: r for r in companies.check(data, probe)}
        self.assertEqual((out["live"]["ok"], out["live"]["count"]), (True, 7))
        self.assertEqual((out["dead"]["ok"], out["dead"]["error"]), (False, "404"))
        self.assertIsNone(out["hand"]["ok"])

    def test_stale(self):
        data = companies.empty()
        companies.add(data, rec("fresh", reviewed="2026-08-20"))
        companies.add(data, rec("old", reviewed="2026-06-01"))
        companies.add(data, rec("older", reviewed="2026-01-01"))
        self.assertEqual(companies.stale(data, 60, today="2026-09-01"), [("older", 243), ("old", 92)])

import json
import unittest
from pathlib import Path

from scraper import companies
from scraper.http import HttpError
from scraper.poll import poll
from scraper.store import Store

FIX = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class Poll(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.companies = [
            companies.record("studio", "Studio", "greenhouse", "examplestudio", "studio-ai", today="2026-09-01"),
            companies.record("brand", "Brand", "lever", "examplebrand", "brand-inhouse", today="2026-09-01"),
            companies.record("hand", "Hand", "manual", None, "product-inhouse", today="2026-09-01"),
        ]

    def test_isolation_and_logging(self):
        def get_json(url):
            if "greenhouse" in url:
                return fixture("greenhouse.json")
            raise HttpError(url, 503, "down")

        out = {r["slug"]: r for r in poll(self.s, self.companies, get_json, now="2026-09-01T00:00:00+00:00")}
        self.assertEqual((out["studio"]["ok"], out["studio"]["seen"], out["studio"]["new"]), (True, 2, 2))
        self.assertFalse(out["brand"]["ok"])
        self.assertIn("503", out["brand"]["error"])
        self.assertIsNone(out["hand"]["ok"])
        logs = self.s.db.execute("SELECT company_slug, ok, error FROM poll_log ORDER BY id").fetchall()
        self.assertEqual([(r["company_slug"], r["ok"]) for r in logs], [("studio", 1), ("brand", 0)])
        self.assertEqual(self.s.stats()["postings"], 2)

    def test_second_poll_dedupes_and_closes(self):
        full = fixture("greenhouse.json")
        poll(self.s, self.companies[:1], lambda u: full, now="2026-09-01T00:00:00+00:00")
        fewer = {"jobs": full["jobs"][:1]}
        out = poll(self.s, self.companies[:1], lambda u: fewer, now="2026-09-02T00:00:00+00:00")[0]
        self.assertEqual((out["seen"], out["new"], out["closed"]), (1, 0, 1))
        st = self.s.stats()
        self.assertEqual((st["postings"], st["open"]), (2, 1))

    def test_parse_bug_is_isolated(self):
        out = poll(self.s, self.companies[:1], lambda u: {"jobs": [{"title": None, "id": 1}]}, now="2026-09-01T00:00:00+00:00")[0]
        self.assertFalse(out["ok"])
        self.assertIn("IntegrityError", out["error"])

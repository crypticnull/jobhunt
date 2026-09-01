import json
import unittest
from pathlib import Path

from scraper.adapters import ashby, greenhouse, lever
from scraper.adapters._text import classify_remote, html_to_text

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class Greenhouse(unittest.TestCase):
    def setUp(self):
        self.p = list(greenhouse.parse(load("greenhouse.json")))

    def test_two_postings(self):
        self.assertEqual(len(self.p), 2)

    def test_remote_with_pay_range(self):
        a = self.p[0]
        self.assertEqual(a["source"], "greenhouse")
        self.assertEqual(a["source_id"], "4001")
        self.assertEqual(a["title"], "Senior Creative Technologist")
        self.assertEqual(a["remote"], "remote")
        self.assertEqual((a["comp_min"], a["comp_max"], a["comp_currency"]), (140000, 175000, "USD"))
        self.assertIn("creative technologist", a["description"])
        self.assertNotIn("<", a["description"], "escaped HTML must become plain text")
        self.assertEqual(a["posted_at"], "2026-08-15T09:00:00-04:00")

    def test_hybrid_without_pay(self):
        b = self.p[1]
        self.assertEqual(b["remote"], "hybrid")
        self.assertIsNone(b["comp_min"])
        self.assertEqual(b["posted_at"], "2026-08-25T10:00:00-04:00", "falls back to updated_at")


class Lever(unittest.TestCase):
    def setUp(self):
        self.p = list(lever.parse(load("lever.json")))

    def test_structured_remote_and_salary(self):
        a = self.p[0]
        self.assertEqual(a["source_id"], "8f1c-1")
        self.assertEqual(a["remote"], "remote")
        self.assertEqual((a["comp_min"], a["comp_max"], a["comp_currency"]), (150000, 190000, "USD"))
        self.assertIn("remote first", a["description"])
        self.assertTrue(a["posted_at"].startswith("2025-08-12"))

    def test_onsite_without_salary(self):
        b = self.p[1]
        self.assertEqual(b["remote"], "onsite")
        self.assertIsNone(b["comp_min"])
        self.assertEqual(b["location"], "Los Angeles, CA")


class Ashby(unittest.TestCase):
    def setUp(self):
        self.p = list(ashby.parse(load("ashby.json")))

    def test_tiers_win(self):
        a = self.p[0]
        self.assertEqual(a["remote"], "remote")
        self.assertEqual((a["comp_min"], a["comp_max"], a["comp_currency"]), (160000, 210000, "USD"))

    def test_summary_fallback(self):
        b = self.p[1]
        self.assertEqual(b["remote"], "hybrid")
        self.assertEqual((b["comp_min"], b["comp_max"]), (140000, 180000))


class TextHelpers(unittest.TestCase):
    def test_classify_remote(self):
        self.assertEqual(classify_remote("Remote - US"), "remote")
        self.assertEqual(classify_remote("New York (Hybrid)"), "hybrid")
        self.assertEqual(classify_remote("Remote or NYC, hybrid"), "hybrid")
        self.assertEqual(classify_remote("Austin, TX"), "onsite")
        self.assertEqual(classify_remote(""), "unclear")
        self.assertEqual(classify_remote("Austin, TX", "remote"), "remote")
        self.assertEqual(classify_remote("Remote", "OnSite"), "onsite")

    def test_html_to_text(self):
        self.assertEqual(html_to_text("&lt;p&gt;A &amp;amp; B&lt;/p&gt;&lt;p&gt;C&lt;/p&gt;"), "A & B\n\nC")
        self.assertEqual(html_to_text(None), "")

import json
import unittest
from pathlib import Path

from scraper.adapters import ADAPTERS, count_postings, recruitee, rss, smartrecruiters, workable
from scraper.http import HttpError

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class Registry(unittest.TestCase):
    def test_all_seven_kinds_are_pollable(self):
        self.assertEqual(set(ADAPTERS), {"greenhouse", "lever", "ashby", "workable", "smartrecruiters", "recruitee", "rss"})

    def test_counts(self):
        self.assertEqual(count_postings("workable", load("workable.json")), 2)
        self.assertEqual(count_postings("smartrecruiters", load("smartrecruiters.json")), 2)
        self.assertEqual(count_postings("recruitee", load("recruitee.json")), 2)


class Workable(unittest.TestCase):
    def setUp(self):
        self.p = list(workable.parse(load("workable.json")))

    def test_telecommuting_is_remote(self):
        a = self.p[0]
        self.assertEqual((a["source_id"], a["remote"], a["location"]), ("AB12CD", "remote", "United States"))
        self.assertIn("ComfyUI", a["description"])
        self.assertEqual(a["posted_at"], "2026-08-22")

    def test_workplace_hybrid(self):
        b = self.p[1]
        self.assertEqual((b["remote"], b["location"]), ("hybrid", "Austin, Texas, United States"))


class SmartRecruiters(unittest.TestCase):
    def test_fetch_merges_details_and_survives_a_failed_one(self):
        detail = load("smartrecruiters.detail.json")

        def get_json(url):
            if url.endswith("/postings?limit=100"):
                return load("smartrecruiters.json")
            if url.endswith("743999900000001"):
                return detail
            raise HttpError(url, 404, "gone")

        p = list(smartrecruiters.parse(smartrecruiters.fetch("ExampleSR", get_json)))
        self.assertEqual(len(p), 2)
        a, b = p
        self.assertEqual((a["remote"], a["url"]), ("remote", "https://jobs.smartrecruiters.com/ExampleSR/743999900000001"))
        self.assertIn("Unreal and Houdini", a["description"])
        self.assertIn("$150,000 - $185,000", a["description"], "comp lives in the text for salary.py")
        self.assertEqual(b["remote"], "onsite")
        self.assertEqual(b["description"], "")
        self.assertTrue(b["url"].startswith("https://jobs.smartrecruiters.com/ExampleSR/"))


class Recruitee(unittest.TestCase):
    def setUp(self):
        self.p = list(recruitee.parse(load("recruitee.json")))

    def test_flags_and_salary(self):
        a = self.p[0]
        self.assertEqual((a["remote"], a["comp_min"], a["comp_max"], a["comp_currency"]), ("remote", 90000, 120000, "EUR"))
        self.assertIn("TouchDesigner", a["description"])
        self.assertEqual(a["posted_at"], "2026-08-21 09:00:00")

    def test_hybrid_without_salary(self):
        b = self.p[1]
        self.assertEqual(b["remote"], "hybrid")
        self.assertIsNone(b["comp_min"])


class Rss(unittest.TestCase):
    def test_rss_items(self):
        p = list(rss.parse((FIX / "careers.rss").read_text(encoding="utf-8")))
        self.assertEqual(len(p), 2)
        self.assertEqual((p[0]["source"], p[0]["remote"], p[0]["url"]), ("rss", "remote", "https://example.com/careers/senior-creative-technologist"))
        self.assertIn("Pipeline and tooling", p[0]["description"])
        self.assertEqual(p[1]["remote"], "unclear")
        self.assertEqual(p[1]["source_id"], "https://example.com/careers/motion-designer", "falls back to the link")

    def test_atom_entries(self):
        atom = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Jobs</title>
        <entry><title>Design Technologist</title><link href="https://x/1"/><id>tag:x,1</id>
        <summary>&lt;p&gt;Tooling for the design system.&lt;/p&gt;</summary><updated>2026-08-30T00:00:00Z</updated></entry></feed>"""
        p = list(rss.parse(atom))
        self.assertEqual((p[0]["title"], p[0]["url"], p[0]["source_id"], p[0]["posted_at"]), ("Design Technologist", "https://x/1", "tag:x,1", "2026-08-30T00:00:00Z"))
        self.assertEqual(p[0]["description"], "Tooling for the design system.")

    def test_empty(self):
        self.assertEqual(list(rss.parse("")), [])

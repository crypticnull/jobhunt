import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper import digest
from scraper.posting import posting
from scraper.score import RULES_PATH, load_rules, score
from scraper.store import Store

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
SEEN = "2026-09-01T00:00:00+00:00"


def rules():
    r = load_rules(RULES_PATH, local="/nonexistent")
    r["comp_band"] = {"min": 130000, "max": 170000, "currency": "USD"}
    return r


class Digest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.r = rules()
        self.ids = {}
        specs = {
            "strong": dict(title="Senior Creative Technologist", description="pipeline comfyui python", comp_min=140000, comp_max=165000),
            "border": dict(title="Senior Motion Designer", description="", comp_min=135000, comp_max=150000, remote="hybrid"),
            "nocomp": dict(title="Senior Motion Designer", description=""),
            "below": dict(title="Junior Motion Designer", description="agency, hourly", remote="onsite"),
        }
        for i, (key, spec) in enumerate(specs.items(), 1):
            spec.setdefault("remote", "remote")
            p = posting(source="greenhouse", source_id=str(i), company_slug="acme", url=f"https://x/{i}", **spec)
            pid, _ = self.s.upsert(p, SEEN)
            self.s.set_score(pid, score(self.s.get(pid), self.r, NOW))
            self.ids[key] = pid

    def lanes(self):
        lanes, below = digest.select(self.s, self.r)
        return {k: [r["id"] for r in v] for k, v in lanes.items()}, below

    def test_lanes(self):
        lanes, below = self.lanes()
        self.assertEqual(lanes["strong"], [self.ids["strong"]])
        self.assertEqual(lanes["borderline"], [self.ids["border"]])
        self.assertEqual(lanes["no_comp"], [self.ids["nocomp"]], "borderline without comp goes to its own lane, never dropped")
        self.assertEqual(below, 1)

    def test_terminal_status_is_excluded(self):
        self.s.mark(self.ids["strong"], "applied")
        self.s.mark(self.ids["border"], "interested")
        lanes, _ = self.lanes()
        self.assertEqual(lanes["strong"], [])
        self.assertEqual(lanes["borderline"], [self.ids["border"]], "interested still shows")

    def test_write_marks_and_unchanged_stay_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            path, n = digest.write(self.s, self.r, Path(d), {"acme": "Acme"}, NOW)
            self.assertTrue(path.name.endswith("W36.md"))
            self.assertEqual(n, 3)
            text = path.read_text(encoding="utf-8")
        self.assertIn("## Strong", text)
        self.assertIn("Senior Creative Technologist, Acme", text)
        self.assertIn("comp not posted", text)
        self.assertIn("mark with `python -m scraper mark", text)
        lanes, _ = self.lanes()
        self.assertEqual(sum(len(v) for v in lanes.values()), 0, "already surfaced and unchanged")
        # comp appears on the no-comp posting: it changed, so it comes back
        pid = self.ids["nocomp"]
        p = posting(source="greenhouse", source_id="3", company_slug="acme", url="https://x/3", remote="remote", title="Senior Motion Designer", comp_min=150000, comp_max=160000)
        self.s.upsert(p, "2026-09-05T00:00:00+00:00")
        self.s.set_score(pid, score(self.s.get(pid), self.r, NOW))
        lanes, _ = self.lanes()
        self.assertIn(pid, lanes["strong"] + lanes["borderline"])

    def test_source_health_footer(self):
        self.s.log_poll("2026-09-05T02:30:00+00:00", "lever", "brand", False, error="503 down")
        self.s.log_poll("2026-09-04T02:30:00+00:00", "ashby", "quiet", True, 0, 0)
        self.s.log_poll("2026-09-05T02:30:00+00:00", "ashby", "quiet", True, 0, 0)
        self.s.log_poll("2026-09-05T02:30:00+00:00", "greenhouse", "acme", True, 4, 0)
        md, _ = digest.build(self.s, self.r, now=NOW)
        self.assertIn("lever/brand: 503 down", md)
        self.assertIn("ashby/quiet: zero postings on the last two polls", md)
        self.assertNotIn("greenhouse/acme", md.split("## Source health")[1])

    def test_all_sources_answered(self):
        md, _ = digest.build(self.s, self.r, now=NOW)
        self.assertIn("All sources answered.", md)

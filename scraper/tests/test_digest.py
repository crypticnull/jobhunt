import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper import digest
from scraper.posting import posting
from scraper.score import RULES_PATH, _deep_merge, load_rules, score
from scraper.store import Store

NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)  # inside the collect-only window, which closes on the 6th
SEEN = "2026-09-01T00:00:00+00:00"
BAND = {
    "gates": {"comp": {"pass_min_annual": 100000, "flag_min_annual": 80000, "fail_below_annual": 80000, "hourly_floor": 60}},
    "score": {"comp": {"bands": [{"midpoint_min": 120000, "points": 20}, {"midpoint_min": 100000, "points": 15}, {"midpoint_min": 80000, "points": 5}]}},
}
COMPANIES = {
    "acme": {"slug": "acme", "name": "Acme", "tier": 1},
    "brand": {"slug": "brand", "name": "Brand Co", "tier": 4},
}


def rules():
    r = load_rules(RULES_PATH, local="/nonexistent")
    return _deep_merge(r, json.loads(json.dumps(BAND)))


class Digest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.r = rules()
        self.ids = {}
        specs = {
            "apply": dict(company_slug="acme", title="Senior Creative Technologist", description="pipeline comfyui python", comp_min=140000, comp_max=165000),
            "review": dict(company_slug="brand", title="Senior Motion Designer", description="", comp_min=85000, comp_max=95000),
            "unknown": dict(company_slug="nobody", title="Senior Motion Designer", description=""),
            "hybrid": dict(company_slug="acme", title="Senior Motion Designer", description="", remote="hybrid"),
        }
        for i, (key, spec) in enumerate(specs.items(), 1):
            spec.setdefault("remote", "remote")
            spec.setdefault("location", "Remote - US")
            self.ids[key] = self.add(i, **spec)

    def add(self, i, **spec):
        p = posting(source="greenhouse", source_id=str(i), url=f"https://x/{i}", **spec)
        pid, _ = self.s.upsert(p, SEEN)
        self.rescore(pid)
        return pid

    def rescore(self, pid):
        row = self.s.get(pid)
        self.s.set_score(pid, score(row, self.r, NOW, COMPANIES.get(row["company_slug"])))

    def piles(self):
        return {k: [r["id"] for r in v] for k, v in digest.select(self.s, self.r, COMPANIES, NOW).items()}

    def test_piles(self):
        piles = self.piles()
        self.assertEqual(piles, {"apply": [self.ids["apply"]], "review": [self.ids["review"]], "overflow": [], "hidden": []})
        self.assertEqual(self.s.drop_counts(SEEN), {"comp: unlisted_salary_unknown_company": 1, "remote: remote claim is hybrid": 1})
        self.assertEqual(self.s.new_by_source(SEEN), {"greenhouse": 4})

    def test_terminal_status_is_excluded(self):
        self.s.mark(self.ids["apply"], "applied")
        self.s.mark(self.ids["review"], "reviewed")
        piles = self.piles()
        self.assertEqual(piles["apply"], [])
        self.assertEqual(piles["review"], [self.ids["review"]], "reviewed still shows until Matt moves it on")

    def test_weekly_cap_sorts_by_tier_then_score(self):
        self.r["piles"]["apply_weekly_cap"] = 1
        second = self.add(9, company_slug="brand", title="Creative Technologist", description="comfyui python houdini pipeline", comp_min=150000, comp_max=170000, remote="remote", location="Remote - US")
        piles = self.piles()
        self.assertEqual(piles["apply"], [self.ids["apply"]], "tier 1 first even at a lower score")
        self.assertEqual(piles["overflow"], [second])
        md, ids = digest.build(self.s, self.r, COMPANIES, NOW)
        self.assertIn("over the weekly cap of 1", md)
        self.assertEqual(ids, [self.ids["apply"], second, self.ids["review"]])

    def test_write_marks_and_unchanged_stay_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            path, n = digest.write(self.s, self.r, Path(d), COMPANIES, NOW)
            self.assertTrue(path.name.endswith("W36.md"))
            self.assertEqual(n, 2)
            text = path.read_text(encoding="utf-8")
        for needle in (
            "Collect-only until 2026-09-06",
            "## New listings by source",
            "- greenhouse: 4",
            "## Apply",
            "Senior Creative Technologist, Acme (tier 1)",
            "Lead with: local-pipeline",
            "## Review",
            "Senior Motion Designer, Brand Co (tier 4)",
            "Flags: comp:",
            "## Logged, by reason",
            "comp: unlisted_salary_unknown_company",
            "remote: remote claim is hybrid",
            "`python -m scraper mark 1 reviewed`",
        ):
            self.assertIn(needle, text)
        self.assertEqual(sum(len(v) for v in self.piles().values()), 0, "already surfaced and unchanged")
        # comp moves on the review posting: it changed, so it comes back, now in apply
        pid = self.ids["review"]
        p = posting(source="greenhouse", source_id="2", company_slug="brand", url="https://x/2", remote="remote", location="Remote - US", title="Senior Motion Designer", description="python tooling", comp_min=150000, comp_max=160000)
        self.s.upsert(p, "2026-09-05T00:00:00+00:00")
        self.rescore(pid)
        self.assertIn(pid, self.piles()["apply"])

    def test_an_exceptional_posting_is_called_out_during_the_window(self):
        """Matt may not have this job in two months. A posting scoring 85 or
        better is named in the digest even while the window is open, because
        it will be gone before the window closes."""
        self.r["piles"]["exceptional_min"] = 70
        md, _ = digest.build(self.s, self.r, COMPANIES, NOW)
        self.assertIn("will not wait for the window to close", md)
        self.assertIn("Senior Creative Technologist, Acme", md.split("will not wait")[1])
        self.r["piles"]["exceptional_min"] = 999
        md, _ = digest.build(self.s, self.r, COMPANIES, NOW)
        self.assertNotIn("will not wait", md)

    def test_the_review_pile_is_capped_and_the_rest_are_not_marked_seen(self):
        """Ninety companies put six thousand postings in the store. A digest
        listing four hundred is a digest nobody reads, and marking them all as
        surfaced would bury them for good."""
        self.r["piles"]["review_weekly_cap"] = 1
        for i in range(20, 25):
            self.add(i, company_slug="brand", title=f"Senior Motion Designer {i}", description="", comp_min=85000, comp_max=95000, remote="remote", location="Remote - US")
        piles = digest.select(self.s, self.r, COMPANIES, NOW)
        self.assertEqual(len(piles["review"]), 1)
        self.assertEqual(len(piles["hidden"]), 5)
        md, ids = digest.build(self.s, self.r, COMPANIES, NOW)
        self.assertIn("5 more scored below", md)
        self.assertTrue(all(r["id"] not in ids for r in piles["hidden"]), "held back means it comes round again")

    def test_after_the_collect_window_the_banner_goes(self):
        later = datetime(2026, 10, 12, tzinfo=timezone.utc)  # past collect_only_until
        md, _ = digest.build(self.s, self.r, COMPANIES, later)
        self.assertNotIn("Collect-only", md)
        self.assertIn("# Digest, week 2026-W42", md)

    def test_a_stopped_scraper_says_so_at_the_top(self):
        """A digest that is quiet because nothing was found and one that is
        quiet because the nightly job stopped look identical otherwise."""
        with tempfile.TemporaryDirectory() as d:
            beat = Path(d) / "last-run.json"
            beat.write_text(json.dumps({"ran_at": "2026-08-20T04:00:00+00:00"}), encoding="utf-8")
            md, _ = digest.build(self.s, self.r, COMPANIES, NOW, heartbeat=beat)
            self.assertIn("The last poll was 15 days ago", md)
            beat.write_text(json.dumps({"ran_at": "2026-09-05T04:00:00+00:00"}), encoding="utf-8")
            md, _ = digest.build(self.s, self.r, COMPANIES, NOW, heartbeat=beat)
            self.assertNotIn("last poll was", md)
            md, _ = digest.build(self.s, self.r, COMPANIES, NOW, heartbeat=Path(d) / "missing.json")
            self.assertIn("no record of ever running", md)

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


class PayModel(unittest.TestCase):
    """Location-adjusted pay is what decides whether the move north costs money,
    so the digest asks the question rather than leaving it to offer stage."""

    def setUp(self):
        self.s = Store(":memory:")
        self.r = rules()
        p = posting(source="greenhouse", source_id="1", company_slug="acme", url="https://x/1",
                    remote="remote", location="Remote - US", title="Senior Creative Technologist",
                    description="pipeline comfyui python", comp_min=140000, comp_max=165000)
        pid, _ = self.s.upsert(p, SEEN)
        self.pid = pid

    def md(self, pay_model):
        cs = {"acme": {"slug": "acme", "name": "Acme", "tier": 1, "pay_model": pay_model}}
        row = self.s.get(self.pid)
        self.s.set_score(self.pid, score(row, self.r, NOW, cs["acme"]))
        md, _ = digest.build(self.s, self.r, cs, NOW)
        return md

    def test_location_adjusted_is_called_out(self):
        self.assertIn("location-adjusted, so the move north cuts it", self.md("location-adjusted"))

    def test_unknown_asks_the_question(self):
        self.assertIn("Ask whether pay is the same wherever you live", self.md("unknown"))

    def test_same_everywhere_says_nothing(self):
        md = self.md("same-everywhere")
        self.assertNotIn("Pay model unknown", md)
        self.assertNotIn("location-adjusted", md)


class Headquarters(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.r = rules()
        p = posting(source="greenhouse", source_id="1", company_slug="acme", url="https://x/1",
                    remote="remote", location="Remote - US", title="Senior Creative Technologist",
                    description="pipeline comfyui python", comp_min=140000, comp_max=165000)
        self.pid, _ = self.s.upsert(p, SEEN)

    def md(self, **extra):
        c = {"slug": "acme", "name": "Acme", "tier": 1, **extra}
        self.s.set_score(self.pid, score(self.s.get(self.pid), self.r, NOW, c))
        md, _ = digest.build(self.s, self.r, {"acme": c}, NOW)
        return md

    def test_a_known_location_is_printed(self):
        self.assertIn("Hillsboro, OR", self.md(hq="Hillsboro, OR"))

    def test_an_unknown_location_adds_nothing(self):
        md = self.md()
        self.assertIn("Senior Creative Technologist, Acme", md)
        self.assertNotIn(" ·  · ", md, "a missing location must not leave an empty separator")

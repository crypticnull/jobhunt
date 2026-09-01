import unittest
from datetime import datetime, timezone

from scraper.score import RULES_PATH, lane, load_rules, score

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def rules(band=True):
    r = load_rules(RULES_PATH, local="/nonexistent/scoring.local.json")
    if band:
        r["comp_band"] = {"min": 130000, "max": 170000, "currency": "USD"}
    return r


def row(**kw):
    base = dict(
        title="Motion Designer",
        description="",
        remote_class="remote",
        comp_min=None,
        comp_max=None,
        comp_found=0,
        posted_at="2026-08-30T00:00:00+00:00",
        first_seen="2026-08-30T00:00:00+00:00",
    )
    base.update(kw)
    return base


def fired(result, rule):
    return next((r for r in result["rules"] if r["rule"] == rule), None)


class Scoring(unittest.TestCase):
    def test_strong_fit(self):
        r = score(
            row(
                title="Senior Creative Technologist",
                description="Build our generative pipeline in ComfyUI and Houdini, with Python tooling.",
                comp_min=140000,
                comp_max=165000,
                comp_found=1,
            ),
            rules(),
            NOW,
        )
        self.assertEqual(lane(r, rules()), "strong")
        self.assertEqual(fired(r, "remote")["value"], 30)
        self.assertEqual(fired(r, "seniority")["value"], 10)
        self.assertEqual(fired(r, "intersection")["value"], 30, "capped")
        self.assertEqual(fired(r, "comp")["value"], 20)
        self.assertEqual(fired(r, "freshness")["value"], 10)
        self.assertEqual(r["version"], rules()["version"])

    def test_junior_onsite_sinks(self):
        r = score(row(title="Junior Motion Designer", remote_class="onsite"), rules(), NOW)
        self.assertEqual(fired(r, "seniority")["value"], -40)
        self.assertEqual(lane(r, rules()), "below")

    def test_borderline_must_surface(self):
        """A remote motion role with no seniority signal, no intersection terms
        and no comp is exactly the posting that needs a human look, so it
        scores into borderline, never below."""
        r = score(row(title="Motion Designer"), rules(), NOW)
        self.assertEqual(lane(r, rules()), "borderline")
        self.assertIn("comp not posted", r["flags"])

    def test_remote_hedge(self):
        r = score(row(description="Remote, but expect 3 days in office in Austin."), rules(), NOW)
        self.assertEqual(fired(r, "remote_hedge")["value"], -15)
        self.assertIn("remote hedged", r["flags"])

    def test_comp_bands(self):
        below = score(row(comp_min=90000, comp_max=110000, comp_found=1), rules(), NOW)
        above = score(row(comp_min=200000, comp_max=250000, comp_found=1), rules(), NOW)
        partial = score(row(comp_min=150000, comp_max=200000, comp_found=1), rules(), NOW)
        self.assertEqual(fired(below, "comp")["value"], -25)
        self.assertEqual(fired(above, "comp")["value"], 25)
        self.assertEqual(fired(partial, "comp")["value"], 5)

    def test_no_band_configured_is_flagged_not_scored(self):
        r = score(row(comp_min=150000, comp_max=160000, comp_found=1), rules(band=False), NOW)
        self.assertIsNone(fired(r, "comp"))
        self.assertIn("no comp band configured", r["flags"])

    def test_freshness_decays(self):
        r = score(row(posted_at="2026-08-11T00:00:00+00:00"), rules(), NOW)
        self.assertEqual(fired(r, "freshness")["value"], 5)
        stale = score(row(posted_at="2026-06-01T00:00:00+00:00"), rules(), NOW)
        self.assertIsNone(fired(stale, "freshness"))

    def test_penalty_is_capped_and_word_bounded(self):
        r = score(row(description="agency, fast-paced, high volume, freelance, hourly, contract work"), rules(), NOW)
        self.assertEqual(fired(r, "penalty")["value"], -30)
        clean = score(row(description="contractor-friendly leadership"), rules(), NOW)
        self.assertIsNone(fired(clean, "penalty"), "'contractor' must not match 'contract'")

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper.score import RULES_PATH, _deep_merge, evaluate, lane, load_rules, parse_states, score

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)

# A demo band, never Matt's. The real numbers live in data/local/scoring.local.json.
BAND = {
    "gates": {"comp": {"pass_min_annual": 100000, "flag_min_annual": 80000, "fail_below_annual": 80000, "hourly_floor": 60}},
    "score": {"comp": {"bands": [{"midpoint_min": 120000, "points": 20}, {"midpoint_min": 100000, "points": 15}, {"midpoint_min": 80000, "points": 5}]}},
}


def rules(band=True):
    r = load_rules(RULES_PATH, local="/nonexistent/scoring.local.json")
    if band:
        _deep_merge(r, json.loads(json.dumps(BAND)))
    return r


def row(**kw):
    base = dict(
        title="Motion Designer",
        description="",
        location="Remote - US",
        remote_class="remote",
        comp_min=None,
        comp_max=None,
        comp_found=0,
        posted_at="2026-08-30T00:00:00+00:00",
        first_seen="2026-08-30T00:00:00+00:00",
        last_seen="2026-09-01T00:00:00+00:00",
    )
    base.update(kw)
    return base


TIER2 = {"tier": 2, "size": None}


def fired(result, rule):
    return next((r for r in result["rules"] if r["rule"] == rule), None)


class Gates(unittest.TestCase):
    def test_hybrid_claim_is_dropped_with_a_reason(self):
        r = score(row(remote_class="hybrid"), rules(), NOW, TIER2)
        self.assertEqual((r["pile"], r["score"]), ("logged", 0))
        self.assertEqual(r["drop_reason"], "remote: remote claim is hybrid")

    def test_fake_remote_phrase_fails_the_gate(self):
        r = score(row(description="Remote, but expect 3 days in the office in Austin."), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "logged")
        self.assertIn("fake-remote phrase", r["drop_reason"])

    def test_state_list_without_pa_fails(self):
        r = score(row(location="Remote (CA, NY, WA)"), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "logged")
        self.assertIn("state list excludes PA", r["drop_reason"])

    def test_state_list_without_the_pnw_is_only_a_flag(self):
        r = score(row(location="Remote (PA, NY, NJ)"), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "review")
        self.assertTrue(any("state list has no WA or OR" in f for f in r["flags"]))
        self.assertEqual(fired(r, "remote")["value"], 12)

    def test_timezone_language_flags_unless_pacific_is_fine(self):
        east = score(row(location="Remote", description="Must keep eastern time hours."), rules(), NOW, TIER2)
        self.assertEqual(fired(east, "remote")["value"], 12)
        self.assertTrue(any("timezone" in f for f in east["flags"]))
        west = score(row(location="Remote", description="Any US time zones, pacific hours preferred."), rules(), NOW, TIER2)
        self.assertEqual(fired(west, "remote")["value"], 25)

    def test_remote_in_body_only_is_a_flag_and_absent_is_a_drop(self):
        body = score(row(remote_class="unclear", location="", description="This role is remote."), rules(), NOW, TIER2)
        self.assertEqual(body["pile"], "review")
        self.assertTrue(any("remote in the body" in f for f in body["flags"]))
        gone = score(row(remote_class="unclear", location="", description="Great team."), rules(), NOW, TIER2)
        self.assertEqual(gone["drop_reason"], "remote: remote not stated")

    def test_unlisted_comp_depends_on_the_company(self):
        unknown = score(row(), rules(), NOW, {})
        self.assertEqual(unknown["drop_reason"], "comp: unlisted_salary_unknown_company")
        tier3 = score(row(), rules(), NOW, {"tier": 3})
        self.assertEqual(fired(tier3, "comp")["value"], 10)
        big = score(row(), rules(), NOW, {"tier": 4, "size": 500})
        self.assertEqual(fired(big, "comp")["value"], 8)

    def test_comp_gate_and_bands(self):
        low = score(row(comp_min=60000, comp_max=75000, comp_found=1), rules(), NOW, TIER2)
        self.assertEqual(low["pile"], "logged")
        self.assertIn("below 80,000", low["drop_reason"])
        soft = score(row(comp_min=85000, comp_max=95000, comp_found=1), rules(), NOW, TIER2)
        self.assertEqual((soft["pile"], fired(soft, "comp")["value"]), ("review", 5))
        self.assertTrue(any("under the floor" in f for f in soft["flags"]))
        edge = score(row(comp_min=80000, comp_max=100000, comp_found=1), rules(), NOW, TIER2)
        self.assertEqual(fired(edge, "comp")["value"], 5, "gate on the max, score on the midpoint")
        mid = score(row(comp_min=100000, comp_max=110000, comp_found=1), rules(), NOW, TIER2)
        self.assertEqual(fired(mid, "comp")["value"], 15)
        top = score(row(comp_min=110000, comp_max=130000, comp_found=1), rules(), NOW, TIER2)
        self.assertEqual(fired(top, "comp")["value"], 20)

    def test_no_band_configured_flags_instead_of_guessing(self):
        r = score(row(comp_min=150000, comp_max=160000, comp_found=1), rules(band=False), NOW, TIER2)
        self.assertEqual(r["pile"], "review")
        self.assertTrue(any("comp band not configured" in f for f in r["flags"]))

    def test_unpaid_work_fails_the_comp_gate(self):
        r = score(row(description="Finalists complete an unpaid test."), rules(), NOW, TIER2)
        self.assertEqual(r["drop_reason"], "comp: unpaid work: unpaid test")


class Disqualifiers(unittest.TestCase):
    def test_title_patterns(self):
        self.assertEqual(score(row(title="Video Editor"), rules(), NOW, TIER2)["drop_reason"], "title: ^video editor$")
        self.assertEqual(score(row(title="Junior Motion Designer"), rules(), NOW, TIER2)["drop_reason"], "title: ^junior")
        self.assertIsNone(score(row(title="Senior Video Editor and Motion Designer"), rules(), NOW, TIER2)["drop_reason"])

    def test_phrases_and_staleness(self):
        r = score(row(description="Relocation required within a year."), rules(), NOW, TIER2)
        self.assertEqual(r["drop_reason"], "disqualifier: relocation required")
        stale = score(row(posted_at="2026-07-01T00:00:00+00:00", last_seen="2026-08-01T00:00:00+00:00"), rules(), NOW, TIER2)
        self.assertEqual(stale["drop_reason"], "stale")
        still_up = score(row(posted_at="2026-07-01T00:00:00+00:00"), rules(), NOW, TIER2)
        self.assertIsNone(still_up["drop_reason"], "old but still listed is not stale")

    def test_engine_and_frontend_are_flags_not_drops(self):
        r = score(row(description="Unreal Engine and custom shader work."), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "review")
        self.assertTrue(any("engine or frontend primary" in f for f in r["flags"]))


class Points(unittest.TestCase):
    def test_strong_fit_scores_full_marks(self):
        r = score(
            row(
                title="Senior Creative Technologist",
                description="Build our generative pipeline in ComfyUI and Houdini, with Python tooling.",
                comp_min=140000,
                comp_max=165000,
                comp_found=1,
                contact_hint="Jane Doe, Head of Studio",
            ),
            rules(),
            NOW,
            {"tier": 1},
        )
        self.assertEqual((r["pile"], r["score"]), ("apply", 100))
        self.assertEqual(sorted(r["legs_hit"]), ["3d", "generative", "pipeline", "software"])
        self.assertEqual(r["title_tier"], "A")
        self.assertEqual(r["proof_lead"], "local-pipeline")
        self.assertEqual(fired(r, "human")["value"], 5)
        self.assertEqual(r["version"], rules()["version"])

    def test_plain_motion_designer_lands_in_review_never_logged(self):
        """A remote motion role with no comp, no intersection legs beyond motion
        and no named human is exactly the posting a human should glance at."""
        r = score(row(), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "review")
        self.assertEqual(r["score"], 58)
        self.assertEqual(r["title_tier"], "C")

    def test_title_tier_b_needs_a_technical_leg(self):
        c = score(row(title="Motion Designer", description="After Effects and Cinema 4D."), rules(), NOW, TIER2)
        self.assertEqual((c["title_tier"], fired(c, "title")["value"]), ("C", 5))
        b = score(row(title="Motion Designer", description="Python scripting for After Effects."), rules(), NOW, TIER2)
        self.assertEqual((b["title_tier"], fired(b, "title")["value"]), ("B", 10))
        a = score(row(title="Design Technologist"), rules(), NOW, TIER2)
        self.assertEqual((a["title_tier"], fired(a, "title")["value"]), ("A", 15))

    def test_intersection_caps_at_four_legs(self):
        r = evaluate(row(description="Houdini, After Effects, ComfyUI, Python, and a render farm pipeline."), rules(), TIER2, NOW)
        self.assertEqual(len(r["legs_hit"]), 5)
        self.assertEqual(r["score"]["intersection"], 20)

    def test_freshness_and_company_tier(self):
        fresh = score(row(), rules(), NOW, {"tier": 1})
        self.assertEqual((fired(fresh, "freshness")["value"], fired(fresh, "company")["value"]), (5, 10))
        older = score(row(posted_at="2026-08-20T00:00:00+00:00"), rules(), NOW, {"tier": 4, "size": 300})
        self.assertEqual((fired(older, "freshness")["value"], fired(older, "company")["value"]), (3, 4))
        old = score(row(posted_at="2026-08-01T00:00:00+00:00"), rules(), NOW, {"tier": 3, "size": 50})
        self.assertIsNone(fired(old, "freshness"))

    def test_deductions_cap_and_word_bound(self):
        r = score(row(description="fast-paced, wear many hats, hustle, a rockstar, unlimited pto, high volume"), rules(), NOW, TIER2)
        self.assertEqual(fired(r, "deductions")["value"], -15)
        clean = score(row(description="associates program for juniors"), rules(), NOW, TIER2)
        self.assertIsNone(fired(clean, "deductions"), "'associate' must not match 'associates'")

    def test_under_threshold_is_logged_with_a_reason(self):
        r = score(row(title="Animator", posted_at="2026-08-01T00:00:00+00:00"), rules(), NOW, {"size": 300})
        self.assertEqual((r["pile"], r["drop_reason"]), ("logged", "under review threshold"))
        self.assertEqual(r["score"], 40)

    def test_flags_always_push_to_review(self):
        r = score(
            row(title="Creative Technologist", description="ComfyUI pipeline in Python and Houdini, Unreal for previs.", comp_min=140000, comp_max=165000, comp_found=1),
            rules(),
            NOW,
            {"tier": 1},
        )
        self.assertGreaterEqual(r["score"], 70)
        self.assertEqual(r["pile"], "review")
        self.assertEqual(lane(r, rules()), "review")

    def test_proof_lead_follows_the_tier(self):
        self.assertEqual(score(row(), rules(), NOW, {"tier": 4})["proof_lead"], "event-franchises")
        self.assertEqual(score(row(), rules(), NOW, {"tier": 3})["proof_lead"], "keynote-extractor")
        self.assertEqual(score(row(), rules(), NOW, {"size": 300})["proof_lead"], "ae-llama")


class States(unittest.TestCase):
    def test_parse_states(self):
        r = rules()
        self.assertEqual(parse_states("Remote (CA, NY, WA)", r), ["CA", "NY", "WA"])
        self.assertEqual(parse_states("Remote in California and Washington", r), ["CA", "WA"])
        self.assertEqual(parse_states("Remote - US", r), ["US"])
        self.assertIsNone(parse_states("Remote", r))
        self.assertIsNone(parse_states("Remote, NY", r), "one state is a location, not a list")


class LocalOverlay(unittest.TestCase):
    def test_local_file_merges_over_the_public_ruleset(self):
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "scoring.local.json"
            local.write_text(json.dumps({"gates": {"comp": {"pass_min_annual": 1}}, "tuning": {"apply_weekly_cap": 3}}), encoding="utf-8")
            r = load_rules(RULES_PATH, local=local)
        self.assertEqual(r["gates"]["comp"]["pass_min_annual"], 1)
        self.assertIsNone(r["gates"]["comp"]["flag_min_annual"], "untouched keys survive")
        self.assertEqual(r["tuning"]["apply_weekly_cap"], 3)
        self.assertEqual(r["tuning"]["collect_only_until"], "2026-10-05")

    def test_public_ruleset_carries_no_numbers(self):
        r = rules(band=False)
        for key in ("pass_min_annual", "flag_min_annual", "fail_below_annual", "hourly_floor"):
            self.assertIsNone(r["gates"]["comp"][key])
        self.assertEqual(r["score"]["comp"]["bands"], [])

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
TIER1 = {"tier": 1, "size": None}


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

    def test_pacific_outscores_nationwide(self):
        us = score(row(), rules(), NOW, TIER2)
        self.assertEqual(fired(us, "remote")["value"], 22)
        pt = score(row(description="Core hours on Pacific time."), rules(), NOW, TIER2)
        self.assertEqual(fired(pt, "remote")["value"], 25)
        self.assertEqual(fired(pt, "remote")["why"], "pacific hours")
        pnw = score(row(location="Remote (PA, WA, OR)"), rules(), NOW, TIER2)
        self.assertEqual(fired(pnw, "remote")["value"], 25, "a state list naming WA or OR counts as pacific")
        self.assertEqual(pnw["pile"], "review", "still a plain motion designer")
        flagged = score(row(location="Remote (PA, NY, NJ)", description="Pacific hours."), rules(), NOW, TIER2)
        self.assertEqual(fired(flagged, "remote")["value"], 12, "a flag still halves it")

    def test_contract_floor_is_firm(self):
        # 40 to 50 an hour annualizes to 83,200 to 104,000, which clears the demo salary floor of 100,000
        low = score(row(comp_min=40 * 2080, comp_max=50 * 2080, comp_found=1, employment_type="contract"), rules(), NOW, TIER2)
        self.assertEqual(low["pile"], "logged")
        self.assertIn("under the hourly floor", low["drop_reason"])
        self.assertNotIn("60", low["drop_reason"].split("is under")[1], "the hourly floor itself never prints")
        annual = score(row(comp_min=90000, comp_max=104000, comp_found=1, employment_type="freelance"), rules(), NOW, TIER2)
        self.assertEqual(annual["drop_reason"], low["drop_reason"].replace("104,000", "104,000"), "an annual figure on freelance work is held to the same floor")
        fine = score(row(comp_min=90 * 2080, comp_max=100 * 2080, comp_found=1, employment_type="contract"), rules(), NOW, TIER2)
        self.assertEqual(fine["pile"], "review")
        salaried = score(row(comp_min=40 * 2080, comp_max=50 * 2080, comp_found=1), rules(), NOW, TIER2)
        self.assertNotIn("hourly floor", salaried["drop_reason"] or "", "the hourly floor is for contract work only")

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
        self.assertIn("below the floor", low["drop_reason"])
        self.assertNotIn("80,000", low["drop_reason"], "the floor itself never prints, digests are public")
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
        self.assertEqual(score(row(title="Video Editor"), rules(), NOW, TIER2)["drop_reason"], "title: video editor")
        self.assertEqual(score(row(title="Junior Motion Designer"), rules(), NOW, TIER2)["drop_reason"], "title: junior")
        self.assertIsNone(score(row(title="Senior Video Editor and Motion Designer"), rules(), NOW, TIER2)["drop_reason"])

    def test_phrases_and_staleness(self):
        r = score(row(description="Relocation required within a year."), rules(), NOW, TIER2)
        self.assertEqual(r["drop_reason"], "disqualifier: relocation required")
        stale = score(row(posted_at="2026-07-01T00:00:00+00:00", last_seen="2026-08-01T00:00:00+00:00"), rules(), NOW, TIER2)
        self.assertEqual(stale["drop_reason"], "stale")
        still_up = score(row(posted_at="2026-07-01T00:00:00+00:00"), rules(), NOW, TIER2)
        self.assertNotEqual(still_up["drop_reason"], "stale", "old but still listed is not stale")

    def test_a_game_engine_is_always_a_flag(self):
        r = score(row(description="Unreal Engine and custom shader work."), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "review")
        self.assertTrue(any("game engine primary" in f for f in r["flags"]), r["flags"])

    def test_frontend_terms_do_not_flag_a_title_that_already_tiered(self):
        """Every design engineering posting names React and TypeScript. Flagging
        them sent the tier being promoted straight to review, which defeated the
        promotion."""
        body = "Build our design system in React and TypeScript, with Python tooling for the pipeline."
        de = score(row(title="Design Engineer", description=body), rules(), NOW, TIER2)
        self.assertEqual(de["title_tier"], "B")
        self.assertFalse(any("web frontend" in f for f in de["flags"]), de["flags"])

    def test_frontend_terms_still_flag_an_untiered_title(self):
        r = score(row(title="Growth Marketer", description="Mostly React and front-end work."), rules(), NOW, TIER2)
        self.assertIsNone(r["title_tier"])
        self.assertTrue(any("web frontend primary" in f for f in r["flags"]), r["flags"])

    def test_engineering_design_engineers_are_dropped(self):
        """The title match was catching civil and electrical engineering, which
        polluted the highest-value tier."""
        for title in (
            "Controls Design Engineer (Electrical)",
            "Electrical Design Engineer",
            "Precast Design Engineer",
            "Mechanical Design Engineer",
        ):
            r = score(row(title=title, description="python automation pipeline"), rules(), NOW, TIER2)
            self.assertEqual(r["pile"], "logged", title)
            self.assertIn("design engineer", r["drop_reason"], title)

    def test_a_real_design_engineer_survives(self):
        r = score(row(title="Design Engineer", description="Prototyping in Figma, Python tooling, generative video."), rules(), NOW, TIER2)
        self.assertIsNone(r.get("drop_reason"))
        self.assertEqual(r["title_tier"], "B")

    def test_a_posting_located_abroad_fails_the_remote_gate(self):
        for loc in ("Remote - LATAM", "Estonia", "Remote (United Kingdom)", "Remote - India"):
            r = score(row(location=loc), rules(), NOW, TIER2)
            self.assertEqual(r["pile"], "logged", loc)
            self.assertIn("outside the US", r["drop_reason"], loc)

    def test_a_us_marker_beside_another_country_still_passes(self):
        """Remote - US, Canada is a US role that also hires in Canada."""
        r = score(row(location="Remote - US, Canada"), rules(), NOW, TIER2)
        self.assertIsNone(r.get("drop_reason"), r.get("drop_reason"))

    def test_a_us_state_list_is_not_read_as_abroad(self):
        r = score(row(location="Remote - PA, WA, OR"), rules(), NOW, TIER2)
        self.assertIsNone(r.get("drop_reason"), r.get("drop_reason"))


class ProductTitles(unittest.TestCase):
    """Product Designer is 130 of the corpus and where the remote volume and the
    pay are, but Matt is not a product designer and the protocol drops pure UX.
    The leg gate is what reconciles those: the title tiers only where the body
    also wants generative, software or pipeline work."""

    def test_product_designer_at_an_ai_company_tiers(self):
        r = score(
            row(title="Senior Product Designer", description="Prototyping in Figma for our text-to-video diffusion product, with Python tooling."),
            rules(), NOW, TIER2,
        )
        self.assertEqual(r["title_tier"], "B")

    def test_product_terms_now_tier_because_the_leg_means_the_work(self):
        """Reversed 2026-09-05. The product leg used to be generic enough that
        a bank's product role would tier on it, so it was kept out of the gate.
        It is now figma prototyping, design system, motion system, ui animation,
        which is the target work rather than the discipline, and keeping it out
        meant a Design Engineer doing design systems could not tier and so could
        never reach apply. Pure UX is still dropped by title."""
        r = score(
            row(title="Senior Product Designer", description="Prototyping in Figma, design systems, component library work."),
            rules(), NOW, TIER2,
        )
        self.assertEqual(r["title_tier"], "B")
        self.assertIn("product", r["legs_hit"])

    def test_a_motion_title_with_no_technical_leg_is_still_tier_c(self):
        """The distinction tier C exists to draw. Adding motion and 3d to the
        gate collapsed it, so only product joined."""
        r = score(row(title="Motion Designer", description="After Effects and Cinema 4D."), rules(), NOW, TIER2)
        self.assertEqual(r["title_tier"], "C")

    def test_the_product_leg_still_scores_where_it_appears(self):
        r = score(
            row(title="Senior Product Designer", description="Prototyping in Figma, design systems, component library work."),
            rules(), NOW, TIER2,
        )
        self.assertIn("product", r["legs_hit"])

    def test_pure_ux_is_still_dropped(self):
        r = score(row(title="User Experience Designer", description="prototyping figma"), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "logged")


class Points(unittest.TestCase):
    def test_strong_fit_scores_full_marks(self):
        r = score(
            row(
                title="Senior Creative Technologist",
                description="Build our generative pipeline in ComfyUI and Houdini, with Python tooling. Pacific hours.",
                comp_min=140000,
                comp_max=165000,
                comp_found=1,
                contact_hint="Jane Doe, Head of Studio",
            ),
            rules(),
            NOW,
            {"tier": 1},
        )
        # 95 rather than 100: company tier is worth half what it was, and this
        # posting is a perfect fit for what Matt already has without asking for
        # anything the curriculum is taking him toward. Full marks now need
        # both, which is the point of the rebalance.
        self.assertEqual((r["pile"], r["score"]), ("apply", 95))
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
        self.assertEqual(r["score"], 46, "the motion leg is the longform vocabulary and stops paying")
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
        self.assertEqual((fired(fresh, "freshness")["value"], fired(fresh, "company")["value"]), (5, 5))
        older = score(row(posted_at="2026-08-20T00:00:00+00:00"), rules(), NOW, {"tier": 4, "size": 300})
        self.assertEqual((fired(older, "freshness")["value"], fired(older, "company")["value"]), (3, 2))
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
        self.assertEqual(r["score"], 36)

    def test_flags_push_to_review_unless_the_title_is_tier_a(self):
        """A flag means Matt decides, so it holds the posting in review. A tier A
        title is the thing being searched for, so it goes through with the flag
        printed on the row. Revised 2026-09-05."""
        r = score(
            row(title="3D Motion Designer", description="ComfyUI pipeline in Python and Houdini, Unreal for previs.", comp_min=140000, comp_max=165000, comp_found=1),
            rules(),
            NOW,
            {"tier": 1},
        )
        self.assertGreaterEqual(r["score"], 65)
        self.assertEqual(r["pile"], "review")
        self.assertEqual(lane(r, rules()), "review")
        a = score(
            row(title="Creative Technologist", description="ComfyUI pipeline in Python and Houdini, Unreal for previs.", comp_min=140000, comp_max=165000, comp_found=1),
            rules(),
            NOW,
            {"tier": 1},
        )
        self.assertTrue(a["flags"])
        self.assertEqual(a["pile"], "apply")

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
        self.assertEqual(r["tuning"]["collect_only_until"], "2026-09-06")

    def test_public_ruleset_carries_no_numbers(self):
        r = rules(band=False)
        for key in ("pass_min_annual", "flag_min_annual", "fail_below_annual", "hourly_floor"):
            self.assertIsNone(r["gates"]["comp"][key])
        self.assertEqual(r["score"]["comp"]["bands"], [])


class RelevanceFloor(unittest.TestCase):
    """Remote 22 plus comp 20 plus a tier 1 company plus freshness is 57, over
    the review threshold, on a posting about nothing Matt does. With a review
    cap of 40 a week that is how the pile fills with work he would never take."""

    def test_no_title_fit_and_no_leg_is_logged_however_well_it_pays(self):
        r = score(
            row(title="Backend Engineer", description="Java and Spring, distributed systems.",
                comp_min=180000, comp_max=220000),
            rules(), NOW, TIER1,
        )
        self.assertEqual(r["pile"], "logged")
        self.assertEqual(r["drop_reason"], "no title fit and no intersection")

    def test_a_leg_alone_no_longer_rescues_a_title_that_names_no_craft(self):
        """The cost of the 2026-09-06 rule, stated rather than hidden. This
        body is the intersection and the rule cannot tell it apart from the
        About Us block that says the same words in every posting at the same
        company. Matt chose the craft-title requirement knowing it drops this
        shape, because thirty-five of eighty-three review rows were the other
        kind."""
        r = score(
            row(title="Software Engineer", description="Build our ComfyUI generative video pipeline.",
                comp_min=180000, comp_max=220000),
            rules(), NOW, TIER1,
        )
        self.assertEqual(r["pile"], "logged")
        self.assertEqual(r["drop_reason"], "intersection but the title names no craft")

    def test_the_same_body_under_a_craft_title_still_clears(self):
        r = score(
            row(title="Creative Engineer", description="Build our ComfyUI generative video pipeline.",
                comp_min=180000, comp_max=220000),
            rules(), NOW, TIER1,
        )
        self.assertNotEqual(r["pile"], "logged")

    def test_the_boilerplate_rows_the_rule_was_written_for(self):
        """All four sat in the 2026-09-06 review pile, carried by legs the
        company blurb fired."""
        body = "OpenAI builds generative models and the product and pipeline behind them."
        for title in ("Economist", "Workday Engineer", "Commercial Counsel", "Revenue Accounting Manager"):
            r = score(row(title=title, description=body, comp_min=266000, comp_max=385000), rules(), NOW, TIER1)
            self.assertEqual(r["pile"], "logged", title)

    def test_a_tiered_title_alone_is_enough(self):
        r = score(row(title="Creative Technologist", description="", comp_min=180000, comp_max=220000), rules(), NOW, TIER1)
        self.assertNotEqual(r["pile"], "logged")

    def test_the_floor_never_rescues_a_gate_failure(self):
        r = score(row(title="Creative Technologist", location="Remote - LATAM"), rules(), NOW, TIER1)
        self.assertEqual(r["pile"], "logged")
        self.assertIn("outside the US", r["drop_reason"])


class GuidingPrinciples(unittest.TestCase):
    """Matt named two: remote, and no longform animation. The second was only
    half encoded, catching a fixed-fee bid for a full animated piece and
    missing a staff job on a feature or a series."""

    def test_longform_work_is_dropped(self):
        for desc in (
            "Animate sequences for our next animated feature.",
            "Character work across an episodic series for streaming.",
            "Long-form branded content, ten minutes a piece.",
        ):
            r = score(row(title="Motion Designer", description=desc + " comfyui python pipeline"), rules(), NOW, TIER2)
            self.assertEqual(r["pile"], "logged", desc)

    def test_film_pipeline_titles_are_dropped(self):
        for title in ("Character Animator", "Storyboard Artist", "Layout Artist", "Compositor"):
            r = score(row(title=title, description="python pipeline comfyui"), rules(), NOW, TIER2)
            self.assertEqual(r["pile"], "logged", title)

    def test_product_animation_is_the_bullseye_not_a_penalty(self):
        r = score(
            row(title="Motion Systems Designer",
                description="Own our motion system and the product animation across the design system, prototyping in Figma.",
                comp_min=150000, comp_max=180000),
            rules(), NOW, TIER2,
        )
        self.assertEqual(r["title_tier"], "A")
        self.assertIn("product-motion", r["legs_hit"])
        self.assertEqual(r["pile"], "apply")

    def test_ui_animation_scores_the_product_motion_leg(self):
        r = score(row(title="Senior Product Designer", description="UI animation and interface animation for the app, plus Python tooling."), rules(), NOW, TIER2)
        self.assertIn("product-motion", r["legs_hit"])
        self.assertNotIn("product", r["legs_hit"], "no figma, no design system, so no product design leg")

    def test_figma_alone_no_longer_buys_what_a_motion_system_buys(self):
        """The whole reason for the split. One list was doing two jobs, so a
        posting saying figma scored the intersection exactly as hard as one
        saying you will own our motion system, and in W36 that put 39 of 51
        surfaced postings on the product leg with not one of them naming motion
        or animation in the title."""
        design = score(row(title="Senior Product Designer", description="Figma, design systems and design handoff."), rules(), NOW, TIER2)
        motion = score(row(title="Senior Product Designer", description="You will own our motion system and ship it in Rive."), rules(), NOW, TIER2)
        self.assertEqual(design["legs_hit"], ["product"])
        self.assertEqual(motion["legs_hit"], ["product-motion"])
        self.assertEqual(fired(design, "intersection")["value"], 2)
        self.assertEqual(fired(motion, "intersection")["value"], 10)


class Rebalance(unittest.TestCase):
    """Company tier went from 10 points to 5 and the curriculum took the other
    5. Matt's own argument for it: the top 100 is a lagging indicator, so where
    a company sits on a list he would not have written matters less than
    whether the job is the one he is training for. Thresholds came down 5 with
    it, so this changes which postings win rather than how many clear."""

    def test_a_hundred_now_needs_the_curriculum_too(self):
        best = score(
            row(title="Senior Creative Technologist",
                description="Own the motion system and product animation, shipped with Lottie and GSAP, "
                            "on a generative ComfyUI pipeline in Houdini with Python tooling and asset management. Pacific hours.",
                comp_min=160000, comp_max=200000, contact_hint="Jane Doe"),
            rules(), NOW, TIER1,
        )
        self.assertEqual(best["score"], 100)
        self.assertEqual(best["pile"], "apply")

    def test_prestige_alone_moves_a_posting_less_than_it_did(self):
        # Both carry a posted band, so company tier is the only thing differing.
        # Unlisted salary at an unknown company fails the comp gate outright,
        # which would otherwise swamp the comparison.
        paid = dict(title="Motion Designer", comp_min=140000, comp_max=160000, comp_found=1)
        tier1 = score(row(**paid), rules(), NOW, TIER1)
        unknown = score(row(**paid), rules(), NOW, {})
        self.assertEqual(tier1["score"] - unknown["score"], 4, "tier 1 over unknown is 4 points, was 8")


class CraftFloor(unittest.TestCase):
    """The first real run put 894 postings in a pile, led by LLM, CI/CD and
    GraphQL. Every software job hits the software leg, so "any leg" was not a
    relevance test at all. Software and pipeline support a creative role; they
    do not make one."""

    def test_a_software_job_no_longer_clears_on_the_software_leg(self):
        r = score(
            row(title="Backend Engineer", description="Python, REST API, automation and tooling.",
                comp_min=180000, comp_max=240000),
            rules(), NOW, TIER2,
        )
        self.assertEqual(r["legs_hit"], ["software"])
        self.assertEqual(r["pile"], "logged")
        self.assertEqual(r["drop_reason"], "no title fit and no intersection")

    def test_pipeline_alone_is_also_not_enough(self):
        r = score(
            row(title="Data Engineer", description="Asset management, metadata and versioning at scale.",
                comp_min=180000, comp_max=240000),
            rules(), NOW, TIER2,
        )
        self.assertEqual(r["pile"], "logged")

    def test_a_craft_leg_clears_it_under_a_craft_title(self):
        for desc in ("After Effects and Cinema 4D.", "ComfyUI and diffusion work.", "Figma and design systems."):
            r = score(row(title="Creative Lead", description=desc), rules(), NOW, TIER2)
            self.assertNotEqual(r["pile"], "logged", desc)

    def test_the_same_legs_under_a_title_that_names_no_craft_do_not(self):
        for desc in ("After Effects and Cinema 4D.", "ComfyUI and diffusion work.", "Figma and design systems."):
            r = score(row(title="Nondescript Role", description=desc), rules(), NOW, TIER2)
            self.assertEqual(r["pile"], "logged", desc)

    def test_a_tiered_title_still_clears_without_any_leg(self):
        r = score(row(title="Creative Technologist", description="Nothing else to say."), rules(), NOW, TIER2)
        self.assertNotEqual(r["pile"], "logged")


class LegBreadth(unittest.TestCase):
    """The first digest put an Economist, a PCB Layout Engineer and a Software
    Engineer for Trainium in the apply pile. The discovery config already said
    why, in a note written weeks earlier: the scoring legs are far too broad,
    rendering matches every backend job, generative ai is boilerplate. That
    lesson had only ever been applied to discovery."""

    def junk(self, title, description):
        return score(row(title=title, description=description, comp_min=250000, comp_max=380000), rules(), NOW, TIER1)

    def test_economic_modeling_is_not_the_3d_leg(self):
        r = self.junk("Economist", "Economic modeling and forecasting. Data pipelines in Python.")
        self.assertNotIn("3d", r["legs_hit"])
        self.assertEqual(r["pile"], "logged")

    def test_server_side_rendering_is_not_the_3d_leg(self):
        r = self.junk("Full Stack Engineer", "Server-side rendering, React, Node.")
        self.assertNotIn("3d", r["legs_hit"])

    def test_threat_modeling_is_not_the_3d_leg(self):
        r = self.junk("Threat Intelligence Platform Engineer", "Threat modeling and detection, Python pipelines.")
        self.assertNotIn("3d", r["legs_hit"])
        self.assertEqual(r["pile"], "logged")

    def test_generative_ai_boilerplate_is_not_the_generative_leg(self):
        """Every posting at every AI company says it. The specific terms stay."""
        r = self.junk("Software Engineer, Trainium", "Compiler work for generative AI training.")
        self.assertNotIn("generative", r["legs_hit"])
        real = self.junk("Research Engineer", "Diffusion models, ComfyUI and text-to-video.")
        self.assertIn("generative", real["legs_hit"])

    def test_the_company_name_runway_is_not_a_skill(self):
        """Every Runway posting was scoring a generative leg for its own
        letterhead."""
        r = self.junk("Backend Engineer", "Join Runway to build our API.")
        self.assertNotIn("generative", r["legs_hit"])

    def test_chip_and_hardware_design_engineers_are_dropped(self):
        for title in ("RTL Design Engineer - Interconnect", "Actuator Design Engineer",
                      "PCB Layout Engineer, Robotics", "Silicon Design Engineer"):
            r = self.junk(title, "Python tooling and verification.")
            self.assertEqual(r["pile"], "logged", title)

    def test_apply_needs_a_title_that_fits(self):
        """The apply pile feeds the letter generator. A posting he cannot write
        a credible letter for does not belong in it, whatever the body scores."""
        r = self.junk("Staff IT Technical Program Manager",
                      "Figma, design systems and motion system work across teams, Python automation.")
        self.assertIsNone(r["title_tier"])
        self.assertNotEqual(r["pile"], "apply")

    def test_japan_and_the_rest_of_the_world_fail_the_gate(self):
        for loc in ("Remote - Japan", "Remote (France)", "Remote - Singapore", "Tel Aviv, Israel"):
            r = score(row(title="Creative Technologist", location=loc), rules(), NOW, TIER1)
            self.assertEqual(r["pile"], "logged", loc)
            self.assertIn("outside the US", r["drop_reason"], loc)


class ThirdDigestFixes(unittest.TestCase):
    """Three things the 2026-09-05 digest still had wrong, one of them the
    stated bullseye."""

    def junk(self, title, description):
        return score(row(title=title, description=description, comp_min=145000, comp_max=205000), rules(), NOW, TIER1)

    def test_a_tier_a_title_is_not_held_out_of_apply_by_a_flag(self):
        """Creative Technologist at Luma scored 70 and sat in review because the
        body mentions Unity. The flag still prints, so Matt still decides."""
        r = self.junk("Creative Technologist",
                      "Build with our video models, ComfyUI, text-to-video, some Unity engine work.")
        self.assertEqual(r["title_tier"], "A")
        self.assertTrue(r["flags"])
        self.assertEqual(r["pile"], "apply")

    def test_an_untiered_title_is_still_held_by_a_flag(self):
        r = score(row(title="Senior Frontend Engineer, Ads Creative",
                      description="React, TypeScript, frontend work on motion in ads, Figma, design systems, prototyping.",
                      comp_min=190800, comp_max=267100), rules(), NOW, TIER1)
        self.assertTrue(r["flags"])
        self.assertNotEqual(r["pile"], "apply")

    def test_economics_words_are_not_the_generative_leg(self):
        """diffusion of innovation, a market in flux, minimax regret. All three
        were scoring a generative leg on the Economist posting at OpenAI."""
        r = self.junk("Economist",
                      "Study the diffusion of innovation in a market in flux, minimax regret under uncertainty.")
        self.assertNotIn("generative", r["legs_hit"])

    def test_the_product_senses_of_those_words_still_score(self):
        for body in ("Latent diffusion and diffusion transformers.",
                     "We fine-tune FLUX.1 and ship Flux LoRAs.",
                     "Hailuo and MiniMax video models."):
            r = self.junk("Research Engineer", body)
            self.assertIn("generative", r["legs_hit"], body)

    def test_the_discipline_can_come_after_design_engineer(self):
        """Data Center Design Engineer, Electrical was reaching review at 60.
        Every pattern required the discipline before the title."""
        for title in ("Data Center Design Engineer, Electrical - Industrial Compute",
                      "Design Engineer, Mechanical", "Design Engineer - Power and Cooling"):
            r = self.junk(title, "Python tooling and verification.")
            self.assertEqual(r["pile"], "logged", title)

    def test_a_plain_design_engineer_still_tiers(self):
        r = self.junk("Senior Design Engineer",
                      "Figma, prototyping, design systems, TypeScript, motion in the product.")
        self.assertEqual(r["title_tier"], "B")


class RemoteGateReadsTheBody(unittest.TestCase):
    """The 2026-09-05 review found 6,069 of 9,591 logged rows were one text
    heuristic: any location without a remote word was stamped onsite before
    the body was read. These pin the corrected gate."""

    def test_a_country_location_with_a_remote_body_reaches_review(self):
        r = score(row(remote_class="unclear", location="United States", description="This is a fully remote role anywhere in the US."), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "review", r.get("drop_reason"))
        self.assertTrue(any("remote in the body" in f for f in r["flags"]))

    def test_a_city_location_is_still_onsite(self):
        r = score(row(remote_class="onsite", location="Austin, TX", description="Fully remote."), rules(), NOW, TIER2)
        self.assertEqual(r["drop_reason"], "remote: remote claim is onsite")

    def test_us_residency_wording_is_not_a_fake_remote_phrase(self):
        bodies = (
            "This is a fully remote role. You must be based in the United States.",
            "Remote. Candidates must be located in the US.",
            "Remote. You must reside in the United States to be eligible.",
            "Remote. Applicants must live within the U.S.",
            "We use a hybrid search architecture and hybrid cloud deployments.",
            "Remote. The final round is an on-site interview in Austin.",
        )
        for body in bodies:
            r = score(row(description=body), rules(), NOW, TIER2)
            self.assertIsNone(r.get("drop_reason"), body + " -> " + str(r.get("drop_reason")))

    def test_residency_outside_the_us_still_fails(self):
        for body in ("Remote. You must be based in the UK.", "Remote. Must reside in Germany.", "Remote, but hybrid schedule with three days in the office."):
            r = score(row(description=body), rules(), NOW, TIER2)
            self.assertEqual(r["pile"], "logged", body)
            self.assertIn("fake-remote phrase", r["drop_reason"], body)

    def test_join_us_no_longer_makes_a_posting_nationwide(self):
        r = score(row(location="Remote (CA, NY, WA)", description="Join us. Figma."), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "logged")
        self.assertIn("state list excludes PA", r["drop_reason"])

    def test_pay_boilerplate_is_not_a_state_list(self):
        body = "Fully remote across the US. The pay range for this role in California, Colorado, New York and Washington is $150,000 to $180,000."
        r = score(row(location="Remote - US", description=body), rules(), NOW, TIER2)
        self.assertIsNone(r.get("drop_reason"), r.get("drop_reason"))

    def test_a_residency_list_in_the_body_still_counts(self):
        body = "Remote. Candidates must be located in California, Colorado or New York."
        r = score(row(location="Remote", description=body), rules(), NOW, TIER2)
        self.assertEqual(r["pile"], "logged")
        self.assertIn("state list excludes PA", r["drop_reason"])

    def test_eastern_hours_flag_on_a_nationwide_posting(self):
        r = score(row(location="Remote - US", description="Must keep eastern time hours. About us: we are great."), rules(), NOW, TIER2)
        self.assertEqual(fired(r, "remote")["value"], 12)
        self.assertTrue(any("timezone" in f for f in r["flags"]))

    def test_a_payroll_default_flag_does_not_hold_a_tiered_title(self):
        r = score(row(title="Senior Design Engineer", location="Remote - New York",
                      description="Figma, design systems, TypeScript, and you will own our motion tokens and the UI animation.",
                      comp_min=200000, comp_max=260000, comp_found=1), rules(), NOW, TIER1)
        self.assertTrue(any("payroll-default" in f for f in r["flags"]))
        self.assertEqual(fired(r, "remote")["value"], 12)
        self.assertEqual(r["pile"], "apply", "the flag prints and halves the marks but does not hide the match")

    def test_remote_cities_abroad_fail(self):
        for loc in ("Remote - London", "Remote, Toronto", "Remote - Europe", "Berlin (Remote)", "Remote - New Zealand"):
            r = score(row(location=loc), rules(), NOW, TIER2)
            self.assertEqual(r["pile"], "logged", loc)
            self.assertIn("outside the US", r["drop_reason"], loc)


class PayFollowsTheWorker(unittest.TestCase):
    def test_greenhouse_gates_on_the_lowest_tier(self):
        from scraper.adapters.greenhouse import _pay_range
        tiers = [{"min_cents": 20000000, "max_cents": 25000000, "title": "SF"}, {"min_cents": 15000000, "max_cents": 19000000, "title": "All other US"}]
        self.assertEqual(_pay_range(tiers), (150000, 190000, None))

    def test_a_dropped_zero_does_not_become_a_minimum(self):
        from scraper.adapters.greenhouse import _pay_range
        self.assertEqual(_pay_range([{"min_cents": 2030000, "max_cents": 21400000, "currency_type": "USD"}]), (None, 214000, "USD"))

    def test_ashby_walks_every_tier(self):
        from scraper.adapters.ashby import _comp
        c = {"compensationTiers": [
            {"components": [{"compensationType": "Salary", "minValue": 200000, "maxValue": 250000, "currencyCode": "USD"}]},
            {"components": [{"compensationType": "Salary", "minValue": 140000, "maxValue": 175000, "currencyCode": "USD"}]},
        ]}
        self.assertEqual(_comp(c), (140000, 175000, "USD"))

    def test_a_stipend_before_the_salary_does_not_hide_it(self):
        from scraper.salary import extract
        found = extract("We offer a $1,000 to $2,000 home office stipend. The base salary range is $150,000 to $180,000.")
        self.assertEqual(found[:2], (150000, 180000))
        self.assertIsNone(extract("A $500 stipend and a $2,000 learning budget."))


class TitlesAfterTheReview(unittest.TestCase):
    """The 2026-09-05 review: product-motion titles had no tier, seniority
    prefixes dropped senior roles, the engine flag fired on curriculum words,
    and studio roles reached apply through tier C and a bare tier A title."""

    def product(self, title, body="Figma, prototyping, design systems, TypeScript, product motion.", **kw):
        return score(row(title=title, description=body, comp_min=200000, comp_max=260000, comp_found=1, **kw), rules(), NOW, TIER1)

    def test_product_motion_titles_tier(self):
        for title in ("Interaction Designer", "UX Engineer", "Prototyper", "Design Systems Designer", "Motion Design Lead"):
            r = self.product(title)
            self.assertEqual(r["title_tier"], "B", title)
            self.assertEqual(r["pile"], "apply", title)

    def test_seniority_prefixes_only_drop_juniors(self):
        self.assertIsNone(self.product("Associate Creative Director").get("drop_reason"))
        self.assertIsNone(self.product("International Brand Designer").get("drop_reason"))
        self.assertIsNone(self.product("Internal Tools Designer").get("drop_reason"))
        self.assertEqual(self.product("Junior Product Designer")["pile"], "logged")
        self.assertEqual(self.product("Associate Product Designer")["pile"], "logged")
        self.assertEqual(self.product("Intern, Design")["pile"], "logged")

    def test_the_engine_flag_spares_tiered_titles_and_team_unity(self):
        r = self.product("Design Engineer", "WebGL shaders and GLSL for product motion, Figma, design systems.")
        self.assertFalse(any("game engine" in f for f in r["flags"]), r["flags"])
        self.assertEqual(r["pile"], "apply")
        r = self.product("Senior Product Designer", "We value team unity. Figma, prototyping.")
        self.assertFalse(any("game engine" in f for f in r["flags"]))
        r = score(row(title="Creative Producer", description="Unity engine work, Unreal Engine 5, motion design in After Effects."), rules(), NOW, TIER1)
        self.assertTrue(any("game engine" in f for f in r["flags"]))

    def test_naming_the_ml_team_is_not_a_disqualifier(self):
        for body in ("Design Engineer working alongside a research scientist. Figma, design systems.",
                     "You will pair with a machine learning engineer. Figma, prototyping."):
            r = self.product("Design Engineer", body)
            self.assertIsNone(r.get("drop_reason"), body)
        self.assertEqual(self.product("Senior Research Scientist")["pile"], "logged")
        self.assertEqual(self.product("Machine Learning Engineer, Video")["pile"], "logged")

    def test_bare_creative_ai_is_no_longer_tier_a(self):
        self.assertIsNone(self.product("Creative AI Product Manager", "Generative video, ComfyUI.")["title_tier"])
        self.assertEqual(self.product("Creative AI Engineer", "Generative video, ComfyUI.")["title_tier"], "A")

    def test_studio_roles_stay_out_of_apply(self):
        studio = "Commercials, brand films and music videos. Cinema 4D, After Effects."
        for title in ("Senior Animator", "Stop Motion Animator", "Senior 3D Artist"):
            r = score(row(title=title, description=studio, comp_min=150000, comp_max=180000, comp_found=1), rules(), NOW, TIER2)
            self.assertNotEqual(r["pile"], "apply", title)
        for title in ("Creature FX Technical Director", "Lighting Artist", "FX TD", "CG Supervisor"):
            r = score(row(title=title, description=studio, comp_min=150000, comp_max=180000, comp_found=1), rules(), NOW, TIER2)
            self.assertEqual(r["pile"], "logged", title)
        td = score(row(title="Technical Director, Animation", description=studio, comp_min=150000, comp_max=180000, comp_found=1), rules(), NOW, TIER2)
        self.assertIsNone(td["title_tier"], "a film TD with no software or pipeline leg does not tier A")
        pipe = score(row(title="Pipeline TD", description="Python tooling, ComfyUI, asset management.", comp_min=150000, comp_max=180000, comp_found=1), rules(), NOW, TIER2)
        self.assertEqual(pipe["title_tier"], "A")

    def test_lottie_and_rive_unlock_tier_b(self):
        r = self.product("Product Designer", "Lottie and Rive animation for the app.")
        self.assertEqual(r["title_tier"], "B")
        self.assertIn("product-motion", r["legs_hit"])


class ReadableReasons(unittest.TestCase):
    """The drop counts are the part Matt works from every Monday, and the
    2026-09-06 digest printed eighty-character lookaheads in that column."""

    def test_the_shapes_that_were_unreadable(self):
        from scraper.score import readable
        cases = {
            r"\bhybrid\b(?=[^.\n]{0,80}\b(office|on-?site|in[- ]person|days|week|commute)\b)": "hybrid",
            r"\bbased in the (?!(the )?(us\b|u\.s\.|united states))": "based in the",
            r"(electrical|mechanical|civil)[a-z ]* design engineer": "electrical design engineer",
            r"^(senior |staff |principal |lead )?(research scientist|ml researcher)": "research scientist",
            r"\bintern(ship)?s?\b": "intern",
            r"\bonsite\b(?! interview)": "onsite",
            r"must (live|be living) (in|within) (?!(the )?(us\b))": "must live in",
            r"\bcanada\b": "canada",
            r"on-?site": "onsite",
        }
        for pattern, want in cases.items():
            self.assertEqual(readable(pattern), want, pattern)

    def test_it_prints_the_original_rather_than_something_untrue(self):
        """Best effort. A pattern it cannot reduce cleanly comes back whole."""
        from scraper.score import readable
        odd = r"travel (up to )?(1[1-9]|[2-9]\d)%"
        self.assertEqual(readable(odd), odd)


class HybridInTheLocation(unittest.TestCase):
    """A location field is short and structured, not prose, so the lookahead
    that keeps `hybrid` from firing on body text leaves a hole there."""

    def go(self, location):
        r = row(title="Senior Product Designer", description="figma design systems prototyping",
                location=location, comp_min=200000, comp_max=285000, comp_found=1)
        return score(r, rules(), NOW, TIER1)

    def test_a_bay_area_hybrid_listing_no_longer_reaches_the_pile(self):
        """It was scoring remote plus pacific and sitting second in the apply
        pile on 2026-09-06."""
        for loc in ("San Francisco Bay Area Hybrid", "Hybrid - New York", "New York (Hybrid)"):
            r = self.go(loc)
            self.assertEqual(r["pile"], "logged", loc)
            self.assertIn("the location says hybrid", r["drop_reason"], loc)

    def test_a_location_offering_both_still_passes(self):
        """Only hybrid needs the escape. A bare onsite in the location was
        already failing on the body phrase list, wherever it appeared."""
        for loc in ("Remote or Hybrid", "Remote - US"):
            self.assertNotEqual(self.go(loc)["pile"], "logged", loc)


class RegionAndInterns(unittest.TestCase):
    """Three misses found in the review pile Matt read on 2026-09-06."""

    def setUp(self):
        self.r = rules()

    def go(self, title, location="Remote - US", description="design systems figma prototyping"):
        r = row(title=title, description=description, location=location, comp_min=170000, comp_max=220000)
        return score(r, self.r, NOW, {"tier": 3, "size": None})

    def test_a_region_in_the_title_scopes_the_role(self):
        """A region in the body can be a team this role works with, but a
        region in the title is the role. Deal Strategy Analyst - EMEA sat in
        review for a week on a blank location."""
        self.assertEqual(self.go("Deal Strategy Analyst - EMEA")["pile"], "logged")
        self.assertEqual(self.go("Forward Deployed Creative [KSA]")["pile"], "logged")
        self.assertIn("title is scoped to", self.go("Product Designer, LATAM")["drop_reason"])

    def test_a_title_naming_the_us_as_well_still_passes(self):
        self.assertNotEqual(self.go("Product Designer, US & Canada")["pile"], "logged")

    def test_intern_anywhere_in_the_title(self):
        self.assertEqual(self.go("Data Engineer Intern")["pile"], "logged")
        self.assertEqual(self.go("Design Internship")["pile"], "logged")

    def test_international_and_internal_are_left_alone(self):
        self.assertNotEqual(self.go("International Brand Designer")["pile"], "logged")
        # Internal Tooling has no craft word, so it is logged either way. What
        # matters is that the intern rule is not what logs it.
        self.assertNotIn("intern", self.go("Senior Engineer, Internal Tooling")["drop_reason"])

    def test_an_american_city_that_shares_a_foreign_name(self):
        """Vancouver WA is in one of the two states he is moving to. Dublin OH
        and Paris TX are the same shape. One state code is enough to say a
        city is American, even though two are needed to call something a
        residency list."""
        for loc in ("Vancouver, WA", "Dublin, OH", "Paris, TX", "Berlin, NH"):
            self.assertNotEqual(self.go("Senior Product Designer", loc)["pile"], "logged", loc)

    def test_the_foreign_originals_are_still_foreign(self):
        for loc in ("Vancouver, BC", "Dublin, Ireland", "Paris, France", "Berlin, DE", "Toronto, ON"):
            self.assertEqual(self.go("Senior Product Designer", loc)["pile"], "logged", loc)


class PayrollDefaultShape(unittest.TestCase):
    """A payroll-default shape is a location reading "Remote (Berlin)", a
    company defaulting to wherever its payroll already reaches. It was matched
    against the body too, where "we are a fully remote, distributed team" hit
    every time, and that took ten remote marks off four all-remote companies
    in the 2026-09-06 digest."""

    BODY = "We are a fully remote, distributed team. You will build design systems and prototypes in figma."

    def go(self, location, body=None):
        r = row(title="Senior Design Engineer", description=body or self.BODY, location=location,
                comp_min=156500, comp_max=202300, comp_found=1)
        return score(r, rules(), NOW, {"tier": 3, "size": None})

    def test_a_bare_remote_location_is_not_a_payroll_default(self):
        r = self.go("Remote")
        self.assertEqual([f for f in r["flags"] if "payroll" in f], [])
        self.assertEqual(fired(r, "remote")["value"], 22, "the full remote mark, not the halved one")

    def test_the_shape_still_flags_where_it_is_real(self):
        r = self.go("Remote, Global")
        self.assertIn("payroll-default shape in the location", r["flags"][0])
        self.assertNotIn("[a-z]", r["flags"][0], "a reason never prints a character class")

    def test_a_nationwide_location_excuses_the_shape(self):
        for loc in ("Remote - USA", "Remote - United States"):
            self.assertEqual([f for f in self.go(loc)["flags"] if "payroll" in f], [], loc)

    def test_timezone_language_is_unaffected(self):
        r = self.go("Remote - USA", "Fully remote in the US. Must keep eastern time hours.")
        self.assertTrue(any("timezone language: eastern time" in f for f in r["flags"]))

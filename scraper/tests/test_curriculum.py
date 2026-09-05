import unittest
from datetime import datetime, timezone

from scraper import curriculum
from scraper.score import RULES_PATH, load_rules, score

RULES = load_rules(RULES_PATH, local="/nonexistent")
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def row(**kw):
    base = dict(
        title="Senior Product Designer", description="", location="Remote - US", remote_class="remote",
        comp_min=150000, comp_max=180000, comp_found=1,
        posted_at="2026-09-03T00:00:00+00:00", first_seen="2026-09-03T00:00:00+00:00",
        last_seen="2026-09-05T00:00:00+00:00",
    )
    base.update(kw)
    return base


class Forwards(unittest.TestCase):
    """The half Matt asked for: the curriculum steers the search rather than
    being derived from it."""

    def test_two_target_areas_score_the_maximum(self):
        areas = curriculum.alignment("We own the motion system and ship it with Lottie, plus GSAP on the web.", RULES)
        self.assertEqual(areas, ["product-motion", "web-motion"])
        self.assertEqual(curriculum.points(areas, RULES), 5)

    def test_one_area_scores_less(self):
        areas = curriculum.alignment("Design systems and Figma prototyping.", RULES)
        self.assertEqual(areas, ["product-motion"])
        self.assertEqual(curriculum.points(areas, RULES), 3)

    def test_no_area_scores_nothing(self):
        self.assertEqual(curriculum.alignment("Kubernetes and Terraform.", RULES), [])
        self.assertEqual(curriculum.points([], RULES), 0)

    def test_a_skill_he_cannot_claim_yet_still_scores(self):
        """The point of pointing it forwards. Figma and Lottie are not in
        skills.json, and a job asking for them is the job the study is for."""
        claimed = curriculum.load_skills()
        self.assertNotIn("figma", claimed)
        self.assertNotIn("lottie", claimed)
        r = score(row(description="Figma, design tokens, Lottie handoff and CSS animation."), RULES, NOW, {"tier": 3})
        got = {x["rule"]: x["value"] for x in r["rules"]}
        self.assertEqual(got.get("curriculum"), 5)

    def test_web_motion_vocabulary_alone_does_not_make_a_job_relevant(self):
        """Alignment is scored separately from the legs so it never inflates
        them. A plain frontend job hits the curriculum and still gets logged,
        because the relevance floor asks a different question."""
        body = "GSAP and spring physics with easing curves, plus React and Tailwind."
        self.assertEqual(curriculum.alignment(body, RULES), ["web-motion"])
        r = score(row(title="Frontend Engineer", description=body), RULES, NOW, {"tier": 3})
        self.assertEqual(r["pile"], "logged")
        self.assertEqual(r["drop_reason"], "no title fit and no intersection")

    def test_product_vocabulary_does_clear_the_floor_and_that_is_intended(self):
        """The product leg and the product-motion vocabulary overlap on
        purpose. Figma and design systems are both what the market asks for
        and what Matt is learning, so a posting naming them is relevant."""
        r = score(row(title="Product Designer", description="Figma, design systems and design tokens."), RULES, NOW, {"tier": 3})
        self.assertIn("product", r["legs_hit"])
        self.assertNotEqual(r["pile"], "logged")

    def test_the_scale_still_totals_one_hundred(self):
        s = RULES["score"]
        total = (s["remote"]["max"] + s["comp"]["max"] + s["intersection"]["max"] + s["title"]["max"]
                 + s["company_tier"]["max"] + s["curriculum"]["max"] + s["freshness"]["max"] + s["human"]["max"])
        self.assertEqual(total, 100)


class Backwards(unittest.TestCase):
    """The other half: the same vocabulary counted against what he can claim
    gives the study list."""

    def rows(self, *descriptions):
        return [{"description": d, "title": "", "comp_max": 160000} for d in descriptions]

    def test_a_term_he_lacks_and_the_market_asks_for_is_a_gap(self):
        rows = self.rows(*["Figma and design systems work."] * 4)
        gaps = curriculum.gaps(rows, RULES, skills=set())
        terms = {g["term"] for g in gaps}
        self.assertIn("figma", terms)
        figma = next(g for g in gaps if g["term"] == "figma")
        self.assertEqual(figma["postings"], 4)
        self.assertEqual(figma["share"], 100)

    def test_a_term_he_claims_is_not_a_gap(self):
        rows = self.rows(*["ComfyUI and Figma."] * 4)
        gaps = curriculum.gaps(rows, RULES, skills={"comfyui"})
        terms = {g["term"] for g in gaps}
        self.assertIn("figma", terms)
        self.assertNotIn("comfyui", terms, "a claimed skill is not a study item")

    def test_a_rare_term_is_below_the_floor(self):
        rows = self.rows("Rive only here.", "Figma.", "Figma.", "Figma.")
        terms = {g["term"] for g in curriculum.gaps(rows, RULES, skills=set())}
        self.assertNotIn("rive", terms)

    def test_gaps_are_ranked_by_how_often_the_market_asks(self):
        rows = self.rows(*["Figma."] * 9, *["Storybook and Figma."] * 3)
        gaps = curriculum.gaps(rows, RULES, skills=set())
        self.assertEqual(gaps[0]["term"], "figma")

    def test_no_postings_means_no_study_list_rather_than_a_crash(self):
        self.assertEqual(curriculum.gaps([], RULES, skills=set()), [])
        self.assertEqual(curriculum.report([], RULES, skills=set()), [])

    def test_the_report_names_the_share_and_the_pay(self):
        rows = self.rows(*["Figma and design systems."] * 5)
        text = "\n".join(curriculum.report(rows, RULES, skills=set()))
        self.assertIn("## Curriculum", text)
        self.assertIn("figma (product-motion): 5 of 5, 100%", text)
        self.assertIn("median 160k", text)

    def test_the_real_skills_file_loads_and_claims_his_actual_tools(self):
        claimed = curriculum.load_skills()
        for term in ("comfyui", "after effects", "cinema 4d", "python"):
            self.assertIn(term, claimed)


if __name__ == "__main__":
    unittest.main()


class Readability(unittest.TestCase):
    """The first written study list printed raw regexes at a person."""

    def test_word_boundaries_and_lookaheads_are_stripped(self):
        self.assertEqual(curriculum.readable(r"\bllm\b"), "llm")
        self.assertEqual(curriculum.readable(r"framer(?! motion)"), "framer")
        self.assertEqual(curriculum.readable(r"three\.js"), "three.js")
        self.assertEqual(curriculum.readable("figma"), "figma")

    def test_the_report_prints_the_readable_form(self):
        rows = [{"description": "We use an LLM in the loop.", "title": "", "comp_max": 200000}] * 4
        text = "\n".join(curriculum.report(rows, RULES, skills=set()))
        self.assertIn("- llm (engineering)", text)
        self.assertNotIn(r"\b", text)

    def test_boilerplate_is_no_longer_in_the_vocabulary(self):
        """documentation and stakeholder led the first study list. A curriculum
        that says learn documentation is noise."""
        terms = {t for group in RULES["curriculum"]["vocabulary"].values() for t in group}
        for boilerplate in ("documentation", "stakeholder", "workshop", r"\bgit\b", "node", "ci/cd", "graphql"):
            self.assertNotIn(boilerplate, terms)


class Plurals(unittest.TestCase):
    def test_plural_forms_score(self):
        for text in ("We maintain design systems.", "Own micro-interactions across the app.", "Motion systems for the product."):
            self.assertIn("product-motion", curriculum.alignment(text, RULES), text)

    def test_a_claim_retires_the_regex_form_of_a_term(self):
        rows = [row(description="LLM and diffusion models daily.") for _ in range(3)]
        found = {g["term"] for g in curriculum.gaps(rows, RULES, skills={"llm", "stable diffusion"})}
        self.assertNotIn("\\bllm\\b", found)
        self.assertNotIn("diffusion", found)

    def test_boilerplate_words_are_not_the_vocabulary(self):
        self.assertEqual(curriculum.alignment("You will have a blank canvas to build the team.", RULES), [])
        self.assertEqual(curriculum.alignment("Catmull-Rom spline interpolation for our physics engine.", RULES), [])
        self.assertIn("product-motion", curriculum.alignment("Motion principles and a motion language for the product.", RULES))

    def test_an_alternation_reads_as_its_first_option(self):
        self.assertEqual(curriculum.readable("canvas (2d|api|animation|element)"), "canvas 2d")

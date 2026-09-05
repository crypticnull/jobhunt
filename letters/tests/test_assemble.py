import json
import unittest

from letters import assemble
from letters.voicelint import load_rules


def posting(**kw):
    base = dict(id=7, title="Senior Creative Technologist", source="greenhouse", url="https://x/7", remote_class="remote", comp_found=1, comp_min=140000, comp_max=165000, comp_currency="USD", first_seen="2026-09-01T00:00:00+00:00", score=84.0, score_json=json.dumps({"rules": [{"rule": "remote", "value": 30, "why": "remote"}], "flags": []}), description="Build the pipeline.", company_slug="acme")
    base.update(kw)
    return base


def company(**kw):
    base = dict(slug="acme", name="Acme", category="ai-video", priority=1, lead_proof=None, remote_notes="", notes="")
    base.update(kw)
    return base


class Blocks(unittest.TestCase):
    def test_library_shape(self):
        b = assemble.load_blocks()
        self.assertEqual(len(b["opening"]), 3)
        self.assertEqual({m["for"] for m, _ in b["claim"]}, {"ai-video", "studio-ai", "product-inhouse", "brand-inhouse"})
        self.assertEqual(len(b["remote"]), 1)
        self.assertEqual(len(b["close"]), 2)

    def test_claim_follows_category_and_placeholders_fill(self):
        chosen = assemble.select(posting(), company(category="brand-inhouse"))
        self.assertEqual(chosen["claim"][0]["for"], "brand-inhouse")
        self.assertIn("Acme", chosen["claim"][1])
        self.assertNotIn("{company}", chosen["claim"][1])
        self.assertTrue(any("{specific}" in b for _, b in chosen["openings"]), "unknown placeholders stay for Matt")


class Lead(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(assemble.choose_lead(company(), lead="dancekit"), "dancekit")
        self.assertEqual(assemble.choose_lead(company(lead_proof="game-project")), "game-project")
        self.assertEqual(assemble.choose_lead(company(category="ai-video")), "local-pipeline")
        self.assertEqual(assemble.choose_lead(company(category="brand-inhouse")), "event-franchises")

    def test_scored_posting_names_its_own_lead(self):
        scored = posting(score_json=json.dumps({"rules": [], "flags": [], "proof_lead": "keynote-extractor"}))
        self.assertEqual(assemble.choose_lead(company(category="ai-video"), posting=scored), "keynote-extractor")
        self.assertEqual(assemble.choose_lead(company(), lead="dancekit", posting=scored), "dancekit", "--lead still wins")
        self.assertEqual(assemble.choose_lead(company(lead_proof="game-project"), posting=scored), "keynote-extractor", "the scored tier beats the company default")

    def test_unknown_proof_is_an_error(self):
        with self.assertRaises(KeyError):
            assemble.select(posting(), company(), lead="nope")


class Remote(unittest.TestCase):
    def test_only_when_the_posting_hedges(self):
        self.assertFalse(assemble.hedges(posting()))
        self.assertTrue(assemble.hedges(posting(remote_class="hybrid")))
        self.assertTrue(assemble.hedges(posting(remote_class="unclear")))
        hedged = json.dumps({"rules": [], "flags": ["remote hedged"]})
        self.assertTrue(assemble.hedges(posting(score_json=hedged)))
        v2 = json.dumps({"rules": [], "flags": ["remote: payroll-default or timezone language: eastern time"]})
        self.assertTrue(assemble.hedges(posting(score_json=v2)))


class Brief(unittest.TestCase):
    def test_renders_everything(self):
        p, c = posting(remote_class="hybrid"), company(category="studio-ai")
        md = assemble.render_brief(p, c, assemble.select(p, c), load_rules())
        for needle in ("# Brief: Senior Creative Technologist at Acme", "Posting id 7", "USD 140,000-165,000", "remote +30", "### The intersection claim (studio-ai)", "### The proof story: AE Llama", "include it, the posting hedges", "python -m letters save 7"):
            self.assertIn(needle, md)

    def test_clear_remote_skips_paragraph(self):
        p, c = posting(), company()
        md = assemble.render_brief(p, c, assemble.select(p, c), load_rules())
        self.assertIn("skip it, the posting is clearly remote", md)


class TheRoleChoosesTheClaim(unittest.TestCase):
    """Until 2026-09-05 the claim came from the company category alone, so a
    Staff Product Designer at a brand-inhouse company got the event key-art
    letter and a Brand Designer at a product company got the metadata one."""

    def test_a_product_designer_at_a_brand_company_gets_the_product_motion_claim(self):
        chosen = assemble.select(posting(title="Staff Product Designer"), company(category="brand-inhouse"))
        self.assertEqual(chosen["claim"][0]["id"], "claim-product-motion")
        self.assertEqual(chosen["family"], "product-designer")
        self.assertEqual(chosen["proof"][0], "game-project", "the game is the design engineer proof, not the Keynote unzipper")

    def test_a_design_engineer_at_a_product_company_too(self):
        chosen = assemble.select(posting(title="Senior Design Engineer"), company(category="product-inhouse"))
        self.assertEqual(chosen["claim"][0]["id"], "claim-product-motion")
        self.assertEqual(chosen["proof"][0], "game-project")

    def test_a_brand_designer_gets_the_product_motion_claim_wherever_the_company_sits(self):
        chosen = assemble.select(posting(title="Brand Designer"), company(category="product-inhouse"))
        self.assertEqual(chosen["claim"][0]["id"], "claim-product-motion")

    def test_an_unfamiliar_title_still_falls_back_to_the_category(self):
        chosen = assemble.select(posting(title="Head of Product Creative"), company(category="brand-inhouse"))
        self.assertEqual(chosen["claim"][0]["for"], "brand-inhouse")
        self.assertIsNone(chosen["family"])

    def test_no_block_or_story_carries_the_struck_bullets(self):
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        texts = [p.read_text(encoding="utf-8") for p in list((root / "letters" / "blocks").rglob("*.md")) + list((root / "data" / "proof").glob("*.md"))]
        for t in texts:
            self.assertIsNone(re.search(r"58 tasks|sixteen weeks|inside a single day|inside one day|RTX 5090 machine", t), t[:80])

    def test_no_claim_or_opening_files_him_as_a_motion_designer_first(self):
        import re
        b = assemble.load_blocks()
        for meta, body in b["claim"] + b["opening"]:
            first = body.strip().split(".")[0].lower()
            self.assertIsNone(re.search(r"\bi'?m an? [a-z ]*motion designer", first), meta["id"])

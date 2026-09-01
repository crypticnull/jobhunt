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

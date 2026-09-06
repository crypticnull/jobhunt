"""The letter and the resume are held to the same rules as every other surface."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from letters import page
from pipeline import design

ROOT = Path(__file__).resolve().parents[2]
RECORD = json.loads((ROOT / "data" / "resume.json").read_text(encoding="utf-8"))
SKILLS = json.loads((ROOT / "data" / "skills.json").read_text(encoding="utf-8"))["skills"]
WHO = {"name": "Matt Rodenbeck", "hero": "A sentence.", "title": "Creative technologist",
       "github": "https://github.com/crypticnull", "location": "Philadelphia", "email": "", "site": ""}


class Documents(unittest.TestCase):
    def setUp(self):
        self.resume = page.resume(RECORD, SKILLS, WHO)
        self.letter = page.letter("First para.\n\nSecond para.", WHO)

    def test_neither_page_writes_a_literal(self):
        """The site's rule, in tools/check_tokens.mjs. Every colour, size and
        measure comes from data/design/tokens.json, so a token edit moves the
        documents and the portfolio together."""
        css = page.PAGE_CSS
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), [], "a hand-written hex")
        self.assertEqual(re.findall(r"cubic-bezier", css), [], "a hand-written curve")

    def test_every_token_named_exists_in_the_record(self):
        t = design.tokens()
        declared = set(t["colour"]["light"]) | set(t["colour"]["dark"]) | set(t["colour"]["plate"])
        declared |= set(t["grid"]) | set(t["type"]) | {m["name"] for m in t["motion"]["tokens"]}
        used = set(re.findall(r"var\(--([a-z0-9-]+)\)", page.PAGE_CSS))
        self.assertEqual(sorted(used - declared), [])

    def test_a_document_is_never_dark(self):
        """Paper is paper. A letter that renders dark because the reader's
        laptop is dark prints as a black rectangle or not at all."""
        for html in (self.resume, self.letter):
            self.assertNotIn("prefers-color-scheme: dark", html)
            self.assertIn("color-scheme: light;", html)

    def test_nothing_is_fetched_from_anywhere(self):
        for html in (self.resume, self.letter):
            for pattern in ("<link", "<script", "@import", "url("):
                self.assertNotIn(pattern, html, pattern)

    def test_the_letter_is_his_words_and_only_his_words(self):
        self.assertIn("<p>First para.</p>", self.letter)
        self.assertIn("<p>Second para.</p>", self.letter)
        self.assertEqual(self.letter.count("<p>"), 2, "nothing is added to the body")

    def test_a_draft_cannot_inject_markup(self):
        html = page.letter("Regards <script>alert(1)</script>", WHO)
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("&lt;script&gt;", html)

    def test_the_resume_pulls_proof_from_its_own_record(self):
        """The titles and summaries are not copied into data/resume.json, so
        the resume and the site cannot disagree about what a thing is."""
        self.assertIn("AE Llama", self.resume)
        self.assertNotIn("AE Llama", json.dumps(RECORD))

    def test_an_empty_section_prints_as_nothing(self):
        """The same rule the site's Mask keeps: never fake words into a slot
        there is no record for."""
        self.assertEqual(RECORD["experience"], [], "fixture assumes this is still empty")
        self.assertNotIn("<h2>Experience</h2>", self.resume)
        filled = dict(RECORD, experience=[{"role": "Senior Motion Designer", "org": "POWER", "from": "2019", "to": "present", "lines": ["A line."]}])
        self.assertIn("<h2>Experience</h2>", page.resume(filled, SKILLS, WHO))
        self.assertIn("2019 to present", page.resume(filled, SKILLS, WHO))

    def test_the_summary_falls_back_to_the_positioning_sentence(self):
        self.assertIn("A sentence.", self.resume)
        self.assertIn("Written.", page.resume(dict(RECORD, summary="Written."), SKILLS, WHO))

    def test_an_empty_contact_is_absent_rather_than_blank(self):
        self.assertNotIn('href=""', self.resume)

    def test_the_identity_record_is_what_the_site_reads(self):
        """One name, one sentence. site/src/site.config.mjs imports the same
        file, so the letterhead and the hero cannot drift."""
        cfg = (ROOT / "site" / "src" / "site.config.mjs").read_text(encoding="utf-8")
        self.assertIn("data/identity.json", cfg)
        self.assertIn("identity.name", cfg)
        who = design.identity()
        self.assertTrue(who["name"] and who["hero"])


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from letters.__main__ import save_draft
from letters.voicelint import load_rules

RULES = load_rules()
POSTING = {"id": 7, "title": "Senior Creative Technologist", "url": "https://x/7"}
COMPANY = {"slug": "acme", "name": "Acme"}

GOOD = """I've been following what Acme is doing with local video models, and this posting reads like the work I actually do.

I run a 38-node ComfyUI graph on my own hardware, and I've spent years judging frames for a living, so I know when the model is wrong and I can change the graph until it isn't.

If the intersection is what you're hiring for, I'd like to talk.
"""

BAD = """I am writing to apply for the Senior Creative Technologist role — it looks like a great fit (really).

I leverage pipelines; however, I also design.

Sincerely,
Matt
"""


class SaveGate(unittest.TestCase):
    def test_clean_draft_is_filed_with_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            path, findings = save_draft(POSTING, COMPANY, GOOD, d, RULES, today="2026-09-02")
            self.assertEqual(findings, [])
            self.assertEqual(path.name, "acme-7-2026-09-02.md")
            text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nposting_id: 7\ncompany: acme\n"))
        self.assertIn("I'd like to talk.", text)

    def test_dirty_draft_is_refused_and_nothing_written(self):
        with tempfile.TemporaryDirectory() as d:
            path, findings = save_draft(POSTING, COMPANY, BAD, d, RULES)
            self.assertIsNone(path)
            self.assertEqual(list(Path(d).iterdir()), [])
        rules = {f.rule for f in findings}
        for r in ("apply-opener", "em-dash", "parentheses", "corporate-vocab", "semicolon", "connector", "formal-signoff"):
            self.assertIn(r, rules)

    def test_warnings_alone_still_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            path, findings = save_draft(POSTING, COMPANY, "I am sure it is right.\n", d, RULES)
        self.assertIsNone(path)
        self.assertEqual({f.level for f in findings}, {"warning"})

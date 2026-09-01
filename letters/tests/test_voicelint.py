import unittest
from pathlib import Path

from letters.voicelint import ROOT, check_files, check_text, collect, exit_code, load_rules, strip_frontmatter

SAMPLES = Path(__file__).parent / "samples"
RULES = load_rules()
LETTER = RULES["profiles"]["letter"]
ALL_RULES = LETTER["errors"] + LETTER["warnings"]


def rules_in(findings):
    return {f.rule for f in findings}


class Samples(unittest.TestCase):
    def test_every_rule_has_a_pair(self):
        for rule in ALL_RULES:
            with self.subTest(rule=rule):
                self.assertTrue((SAMPLES / f"{rule}.fail.md").exists(), f"missing {rule}.fail.md")
                self.assertTrue((SAMPLES / f"{rule}.pass.md").exists(), f"missing {rule}.pass.md")

    def test_fail_samples_trip_exactly_their_rule(self):
        for rule in ALL_RULES:
            with self.subTest(rule=rule):
                text = (SAMPLES / f"{rule}.fail.md").read_text(encoding="utf-8")
                self.assertEqual(rules_in(check_text(text, "letter", RULES)), {rule})

    def test_pass_samples_are_clean(self):
        for rule in ALL_RULES:
            with self.subTest(rule=rule):
                text = (SAMPLES / f"{rule}.pass.md").read_text(encoding="utf-8")
                self.assertEqual(rules_in(check_text(text, "letter", RULES)), set())

    def test_levels(self):
        errors = check_text((SAMPLES / "em-dash.fail.md").read_text(encoding="utf-8"), "letter", RULES)
        warnings = check_text((SAMPLES / "contractions.fail.md").read_text(encoding="utf-8"), "letter", RULES)
        self.assertEqual({f.level for f in errors}, {"error"})
        self.assertEqual({f.level for f in warnings}, {"warning"})
        self.assertEqual(exit_code(errors), 1)
        self.assertEqual(exit_code(warnings), 2)
        self.assertEqual(exit_code([]), 0)


class Mechanics(unittest.TestCase):
    def test_output_format_and_position(self):
        f = check_text("Fine line.\nA bad; line.\n", "letter", RULES, "x.md")[0]
        self.assertEqual(str(f), "x.md:2:6 semicolon semicolon in prose")

    def test_waiver_on_previous_line_and_inline(self):
        text = "<!-- voicelint: allow parentheses -->\nThe panel (v0.11.0) runs.\nStill (bad).\nFine (ok). <!-- voicelint: allow parentheses -->\n"
        findings = check_text(text, "letter", RULES)
        self.assertEqual([f.line for f in findings], [3, 3])

    def test_frontmatter_is_skipped_and_lines_offset(self):
        text = "---\ntags:\n- one\n- two\n---\n\nClean.\nBad; here.\n"
        findings = check_text(text, "letter", RULES)
        self.assertEqual([(f.rule, f.line) for f in findings], [("semicolon", 8)])
        self.assertEqual(strip_frontmatter("no frontmatter"), ("no frontmatter", 0))

    def test_paragraph_rules_span_wrapped_lines(self):
        text = "It isn't a template,\nbut a graph I built by hand.\n"
        findings = check_text(text, "letter", RULES)
        self.assertEqual([(f.rule, f.line, f.col) for f in findings], [("not-x-but-y", 1, 6)], "points at the n't")

    def test_fenced_code_is_ignored(self):
        text = "Prose.\n\n```\nx = (1; 2) — code\n```\n"
        self.assertEqual(check_text(text, "letter", RULES), [])

    def test_repo_profile_keeps_parentheses(self):
        text = "Docs may use (parentheses); and semicolons. But never — an em dash, or robust claims.\n"
        self.assertEqual(rules_in(check_text(text, "repo", RULES)), {"em-dash", "corporate-vocab"})

    def test_word_boundaries(self):
        self.assertEqual(check_text("Robustness and delivering.\n", "repo", RULES), [])
        self.assertEqual(rules_in(check_text("Delve in.\n", "repo", RULES)), {"corporate-vocab"})


class Repo(unittest.TestCase):
    def test_collect_skips_node_modules_and_private(self):
        files = collect(["site", "data"], RULES["profiles"]["repo"])
        rels = [f.relative_to(ROOT).as_posix() for f in files]
        self.assertTrue(rels, "should find site and data docs")
        self.assertFalse(any("node_modules" in r or r.startswith("data/local") for r in rels), rels)

    def test_repo_prose_passes_repo_profile(self):
        self.assertEqual(check_files(["."], "repo", RULES), [])

    def test_proof_stories_pass_letter_profile(self):
        self.assertEqual(check_files(["data/proof"], "letter", RULES), [])

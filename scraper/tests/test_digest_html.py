"""The page is held to the same rules as the site it is designed with."""

import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper import digest, digest_html
from scraper.posting import posting
from scraper.score import RULES_PATH, _deep_merge, load_rules, score
from scraper.store import Store

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
BAND = {
    "gates": {"comp": {"pass_min_annual": 100000, "flag_min_annual": 80000, "fail_below_annual": 80000, "hourly_floor": 60}},
    "score": {"comp": {"bands": [{"midpoint_min": 120000, "points": 20}, {"midpoint_min": 100000, "points": 15}, {"midpoint_min": 80000, "points": 5}]}},
}
COMPANIES = {
    "luma": {"slug": "luma", "name": "Luma AI", "tier": 1, "pay_model": "unknown"},
    "mercury": {"slug": "mercury", "name": "Mercury", "tier": 3, "pay_model": "location-adjusted", "hq": "San Francisco, CA"},
}


def rules():
    return _deep_merge(load_rules(RULES_PATH, local="/nonexistent"), json.loads(json.dumps(BAND)))


class Page(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.r = rules()
        rows = [
            ("luma", "Creative Technologist", "Generative video, ComfyUI, Python tooling and interface animation.", 145000, 205000),
            ("mercury", "Senior Product Designer", "Figma and our design system. Flows and handoff.", 180000, 220000),
        ]
        for i, (slug, title, desc, lo, hi) in enumerate(rows, 1):
            self.s.upsert(posting(source="ashby", source_id=str(i), company_slug=slug, url=f"https://x/{i}",
                                  title=title, description=desc, remote="remote", location="Remote - US",
                                  comp_min=lo, comp_max=hi, comp_currency="USD", comp_found=1,
                                  posted_at="2026-09-02T00:00:00+00:00"), "2026-09-02T00:00:00+00:00")
        for row in self.s.open_postings():
            self.s.set_score(row["id"], score(row, self.r, NOW, COMPANIES.get(row["company_slug"], {})))
        self.html = digest_html.render(self.s, self.r, COMPANIES, NOW)

    def test_a_component_never_writes_a_literal(self):
        """The site's rule, in tools/check_tokens.mjs. Every colour, duration
        and curve comes from data/design/tokens.json, so a token edit moves the
        digest and the portfolio together instead of only one of them."""
        css = digest_html.PAGE_CSS
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), [], "a hand-written hex")
        self.assertEqual(re.findall(r"\b\d+m?s\b", css), [], "a hand-written duration")
        self.assertEqual(re.findall(r"cubic-bezier", css), [], "a hand-written curve")

    def test_every_token_the_page_names_exists_in_the_record(self):
        """A var() naming a token that is not in the record does nothing and
        says nothing, which is how a design change is lost in silence."""
        declared = set()
        from pipeline import design
        t = design.tokens()
        for group in (t["colour"]["light"], t["colour"]["dark"], t["colour"]["plate"], t["grid"], t["type"]):
            declared |= set(group)
        declared |= {m["name"] for m in t["motion"]["tokens"]}
        used = set(re.findall(r"var\(--([a-z0-9-]+)\)", digest_html.PAGE_CSS))
        self.assertEqual(sorted(used - declared), [], "named in the page, absent from the record")

    def test_the_reduced_column_reaches_the_page(self):
        block = self.html.split("@media (prefers-reduced-motion: reduce)")[1]
        self.assertIn("--enter-overlay: 0ms", block)
        self.assertIn("--pulse: 0ms", block)

    def test_a_card_a_posting_and_the_legs_on_it(self):
        self.assertEqual(self.html.count('<details class="card"'), 2)
        self.assertIn("Creative Technologist", self.html)
        self.assertIn('<span class="leg pm">product-motion</span>', self.html)
        self.assertIn("USD 145,000-205,000", self.html)

    def test_the_page_is_complete_without_the_script(self):
        """Every card is in the document and shown. The script adds the filters
        and nothing else, so a blocked script costs the filters and not the week."""
        body = self.html.split("<script>")[0]
        self.assertEqual(body.count('<details class="card"'), 2)
        cards = body.split('<div class="grid" id="grid">')[1].split("</div>\n<p class=")[0]
        self.assertNotIn("hidden", cards, "no card is hidden before the script runs")
        self.assertIn("Creative Technologist", cards, "the cards are markup, not data for a script")

    def test_a_posting_title_cannot_reach_the_script(self):
        """Titles come from strangers. An earlier draft handed the rows to the
        page as JSON inside a script tag, and json.dumps does not escape
        </script>, so a title could close the tag and run."""
        script = self.html.split("<script>")[1]
        self.assertNotIn("Creative Technologist", script, "no posting content in the script at all")

    def test_the_heading_says_dates_not_a_week_number(self):
        """2026-W36 is the thirty sixth week of the calendar year and also the
        first digest ever run, so a heading reading "Week 36" reads as a
        counter that is wrong. The ISO week stays where it sorts."""
        self.assertIn("Shortlist, the week to 6 September 2026", self.html)
        self.assertIn("31 August to 6 September 2026", self.html)
        self.assertNotIn("Week 36 Shortlist", self.html)
        self.assertIn("2026-W36", self.html, "the ISO week still identifies the file")

    def test_every_scoring_rule_has_its_own_colour(self):
        """The strip under a posting is the shape of its score, so a rule that
        shares a colour with another rule is a rule you cannot read. The two
        accents differ only in hue, so the ramp is that arc and every stop is a
        colour the brand could have had."""
        from pipeline import design
        score = design.tokens()["colour"]["score"]
        for theme in ("light", "dark"):
            names = {f"score-{r}" for r in digest_html.RULES_ORDER}
            self.assertEqual(set(score[theme]), names, theme)
            self.assertEqual(len(set(score[theme].values())), len(names), f"{theme}: two rules share a colour")

    def test_the_strip_and_the_breakdown_agree(self):
        """Same encoding at two sizes. Learn the strip once and the detail
        needs no legend of its own."""
        for rule in ("remote", "comp", "intersection"):
            self.assertIn(f"var(--score-{rule})", self.html)
        self.assertNotIn('class="neg"', self.html, "sign is carried by the number, not a second colour")

    def test_the_legend_names_every_stop(self):
        for rule in digest_html.RULES_ORDER:
            self.assertIn(f'<b><i style="background:var(--score-{rule})"></i>{rule}</b>', self.html)

    def test_nothing_is_fetched_from_anywhere(self):
        """It opens from disk, off a plane, in a year. No request leaves it."""
        for pattern in ("http://", "src=", "<link", "@import", "url("):
            self.assertNotIn(pattern, self.html.replace('href="https://x/', 'X'), pattern)

    def test_the_pay_model_question_survives_into_the_page(self):
        self.assertIn("Ask whether pay is the same wherever you live", self.html)
        self.assertIn("location-adjusted", self.html)

    def test_titles_and_companies_are_escaped(self):
        self.s.upsert(posting(source="ashby", source_id="9", company_slug="luma", url="https://x/9",
                              title='Designer <script>alert(1)</script>', description="ComfyUI and interface animation.",
                              remote="remote", location="Remote - US", comp_min=150000, comp_max=200000,
                              comp_currency="USD", comp_found=1, posted_at="2026-09-02T00:00:00+00:00"),
                      "2026-09-02T00:00:00+00:00")
        for row in self.s.open_postings():
            self.s.set_score(row["id"], score(row, self.r, NOW, COMPANIES.get(row["company_slug"], {})))
        html = digest_html.render(self.s, self.r, COMPANIES, NOW)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_write_puts_a_dated_file_beside_the_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            digest.write(self.s, self.r, Path(d), COMPANIES, NOW)
            names = sorted(p.name for p in Path(d).iterdir())
            self.assertEqual(names, ["2026-W36.html", "2026-W36.md"])


if __name__ == "__main__":
    unittest.main()

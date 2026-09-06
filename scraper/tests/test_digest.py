import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper import digest
from scraper.posting import posting
from scraper.score import RULES_PATH, _deep_merge, load_rules, score
from scraper.store import Store

NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)  # inside the collect-only window, which closes on the 6th
SEEN = "2026-09-01T00:00:00+00:00"
BAND = {
    "gates": {"comp": {"pass_min_annual": 100000, "flag_min_annual": 80000, "fail_below_annual": 80000, "hourly_floor": 60}},
    "score": {"comp": {"bands": [{"midpoint_min": 120000, "points": 20}, {"midpoint_min": 100000, "points": 15}, {"midpoint_min": 80000, "points": 5}]}},
}
COMPANIES = {
    "acme": {"slug": "acme", "name": "Acme", "tier": 1},
    "brand": {"slug": "brand", "name": "Brand Co", "tier": 4},
}


def rules():
    r = load_rules(RULES_PATH, local="/nonexistent")
    return _deep_merge(r, json.loads(json.dumps(BAND)))


class Digest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.r = rules()
        self.ids = {}
        specs = {
            "apply": dict(company_slug="acme", title="Senior Creative Technologist", description="pipeline comfyui python", comp_min=140000, comp_max=165000),
            "review": dict(company_slug="brand", title="Senior Motion Designer", description="", comp_min=85000, comp_max=95000),
            "unknown": dict(company_slug="nobody", title="Senior Motion Designer", description=""),
            "hybrid": dict(company_slug="acme", title="Senior Motion Designer", description="", remote="hybrid"),
        }
        for i, (key, spec) in enumerate(specs.items(), 1):
            spec.setdefault("remote", "remote")
            spec.setdefault("location", "Remote - US")
            self.ids[key] = self.add(i, **spec)

    def add(self, i, **spec):
        p = posting(source="greenhouse", source_id=str(i), url=f"https://x/{i}", **spec)
        pid, _ = self.s.upsert(p, SEEN)
        self.rescore(pid)
        return pid

    def rescore(self, pid):
        row = self.s.get(pid)
        self.s.set_score(pid, score(row, self.r, NOW, COMPANIES.get(row["company_slug"])))

    def piles(self):
        return {k: [r["id"] for r in v] for k, v in digest.select(self.s, self.r, COMPANIES, NOW).items()}

    def test_piles(self):
        piles = self.piles()
        self.assertEqual(piles, {"apply": [self.ids["apply"]], "review": [self.ids["review"]], "overflow": [], "hidden": []})
        self.assertEqual(self.s.drop_counts(SEEN), {"comp: unlisted_salary_unknown_company": 1, "remote: remote claim is hybrid": 1})
        self.assertEqual(self.s.new_by_source(SEEN), {"greenhouse": 4})

    def test_terminal_status_is_excluded(self):
        self.s.mark(self.ids["apply"], "applied")
        self.s.mark(self.ids["review"], "reviewed")
        piles = self.piles()
        self.assertEqual(piles["apply"], [])
        self.assertEqual(piles["review"], [self.ids["review"]], "reviewed still shows until Matt moves it on")

    def test_weekly_cap_sorts_by_tier_then_score(self):
        self.r["piles"]["apply_weekly_cap"] = 1
        second = self.add(9, company_slug="brand", title="Creative Technologist", description="comfyui python houdini pipeline", comp_min=150000, comp_max=170000, remote="remote", location="Remote - US")
        piles = self.piles()
        self.assertEqual(piles["apply"], [self.ids["apply"]], "tier 1 first even at a lower score")
        self.assertEqual(piles["overflow"], [second])
        md, ids = digest.build(self.s, self.r, COMPANIES, NOW)
        self.assertIn("over the weekly cap of 1", md)
        self.assertEqual(ids, [self.ids["apply"], second, self.ids["review"]])

    def test_write_marks_and_unchanged_stay_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            path, n, page = digest.write(self.s, self.r, Path(d), COMPANIES, NOW)
            self.assertTrue(page.exists(), "the page is written beside the markdown")
            self.assertEqual(page.suffix, ".html")
            self.assertTrue(path.name.endswith("W36.md"))
            self.assertEqual(n, 2)
            text = path.read_text(encoding="utf-8")
        for needle in (
            "Collect-only until 2026-09-06",
            "## New listings by source",
            "- greenhouse: 4",
            "## Apply",
            "Senior Creative Technologist, Acme (tier 1)",
            "Lead with: local-pipeline",
            "## Review",
            "Senior Motion Designer, Brand Co (tier 4)",
            "Flags: comp:",
            "## Logged, by reason",
            "comp: unlisted_salary_unknown_company",
            "remote: remote claim is hybrid",
            "`python -m scraper mark 1 reviewed`",
        ):
            self.assertIn(needle, text)
        self.assertEqual(sum(len(v) for v in self.piles().values()), 0, "already surfaced and unchanged")
        # comp moves on the review posting: it changed, so it comes back, now in apply
        pid = self.ids["review"]
        p = posting(source="greenhouse", source_id="2", company_slug="brand", url="https://x/2", remote="remote", location="Remote - US", title="Senior Motion Designer", description="python tooling and our motion system", comp_min=150000, comp_max=160000)
        self.s.upsert(p, "2026-09-05T00:00:00+00:00")
        self.rescore(pid)
        self.assertIn(pid, self.piles()["apply"])

    def test_an_exceptional_posting_is_called_out_during_the_window(self):
        """Matt may not have this job in two months. A posting scoring 85 or
        better is named in the digest even while the window is open, because
        it will be gone before the window closes."""
        self.r["piles"]["exceptional_min"] = 70
        md, _ = digest.build(self.s, self.r, COMPANIES, NOW)
        self.assertIn("will not wait for the window to close", md)
        self.assertIn("Senior Creative Technologist, Acme", md.split("will not wait")[1])
        self.r["piles"]["exceptional_min"] = 999
        md, _ = digest.build(self.s, self.r, COMPANIES, NOW)
        self.assertNotIn("will not wait", md)

    def test_the_review_pile_is_capped_and_the_rest_are_not_marked_seen(self):
        """Ninety companies put six thousand postings in the store. A digest
        listing four hundred is a digest nobody reads, and marking them all as
        surfaced would bury them for good."""
        self.r["piles"]["review_weekly_cap"] = 1
        for i in range(20, 25):
            self.add(i, company_slug="brand", title=f"Senior Motion Designer {i}", description="", comp_min=85000, comp_max=95000, remote="remote", location="Remote - US")
        piles = digest.select(self.s, self.r, COMPANIES, NOW)
        self.assertEqual(len(piles["review"]), 1)
        self.assertEqual(len(piles["hidden"]), 5)
        md, ids = digest.build(self.s, self.r, COMPANIES, NOW)
        self.assertIn("5 more scored below", md)
        self.assertTrue(all(r["id"] not in ids for r in piles["hidden"]), "held back means it comes round again")

    def test_after_the_collect_window_the_banner_goes(self):
        later = datetime(2026, 10, 12, tzinfo=timezone.utc)  # past collect_only_until
        md, _ = digest.build(self.s, self.r, COMPANIES, later)
        self.assertNotIn("Collect-only", md)
        self.assertIn("# Digest, week 2026-W42", md)

    def test_a_stopped_scraper_says_so_at_the_top(self):
        """A digest that is quiet because nothing was found and one that is
        quiet because the nightly job stopped look identical otherwise."""
        with tempfile.TemporaryDirectory() as d:
            beat = Path(d) / "last-run.json"
            beat.write_text(json.dumps({"ran_at": "2026-08-20T04:00:00+00:00"}), encoding="utf-8")
            md, _ = digest.build(self.s, self.r, COMPANIES, NOW, heartbeat=beat)
            self.assertIn("The last poll was 15 days ago", md)
            beat.write_text(json.dumps({"ran_at": "2026-09-05T04:00:00+00:00"}), encoding="utf-8")
            md, _ = digest.build(self.s, self.r, COMPANIES, NOW, heartbeat=beat)
            self.assertNotIn("last poll was", md)
            md, _ = digest.build(self.s, self.r, COMPANIES, NOW, heartbeat=Path(d) / "missing.json")
            self.assertIn("no record of ever running", md)

    def test_the_digest_says_which_commit_built_it(self):
        """A digest run from a checkout that never pulled reads exactly like a
        current one. The stamp is the only thing that tells them apart after
        the text is pasted somewhere."""
        md, _ = digest.build(self.s, self.r, COMPANIES, NOW)
        stamp = digest.code_stamp()
        self.assertIsNotNone(stamp, "the repo is a git checkout, so the stamp should resolve")
        self.assertIn(f"Built from {stamp}.", md)
        self.assertIn(", committed 20", stamp)

    def test_the_stamp_degrades_rather_than_printing_something_untrue(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(digest.code_stamp(d))

    def test_source_health_footer(self):
        self.s.log_poll("2026-09-05T02:30:00+00:00", "lever", "brand", False, error="503 down")
        self.s.log_poll("2026-09-04T02:30:00+00:00", "ashby", "quiet", True, 0, 0)
        self.s.log_poll("2026-09-05T02:30:00+00:00", "ashby", "quiet", True, 0, 0)
        self.s.log_poll("2026-09-05T02:30:00+00:00", "greenhouse", "acme", True, 4, 0)
        md, _ = digest.build(self.s, self.r, now=NOW)
        self.assertIn("lever/brand: 503 down", md)
        self.assertIn("ashby/quiet: answers, and has had nothing open for two polls", md)
        self.assertNotIn("greenhouse/acme", md.split("## Source health")[1])

    def test_a_board_that_never_answers_is_called_what_it_is(self):
        """Workable has returned 429 for four companies on every poll for a
        week. Grouped into one line that is easy to read past, which is how a
        company stays on the list for a month without ever being polled."""
        for day in ("03", "04", "05"):
            self.s.log_poll(f"2026-09-{day}T02:30:00+00:00", "workable", "d-id", False, error="429 too many requests")
        problems = digest.source_health(self.s, SEEN, status_log="/nonexistent")
        line = next(p for p in problems if p.startswith("workable/d-id"))
        self.assertIn("3 polls", line)
        self.assertIn("on the list without being polled", line)

    def test_a_board_that_answers_sometimes_is_only_drifting(self):
        """Still failing on the latest poll, so it stays in the footer, but it
        has answered inside the window so it is drifting rather than absent."""
        self.s.log_poll("2026-09-03T02:30:00+00:00", "workable", "redox", True, 12, 2)
        for day in ("04", "05"):
            self.s.log_poll(f"2026-09-{day}T02:30:00+00:00", "workable", "redox", False, error="503 down")
        problems = digest.source_health(self.s, SEEN, status_log="/nonexistent")
        line = next(p for p in problems if p.startswith("workable/redox"))
        self.assertNotIn("without being polled", line)

    def test_an_error_that_has_since_been_fixed_leaves_the_footer(self):
        """Workable rate-limited four companies on the 5th and answered all
        four on the 6th, and the footer still led with the four 429s."""
        self.s.log_poll("2026-09-04T02:30:00+00:00", "workable", "d-id", False, error="429 too many requests")
        self.s.log_poll("2026-09-05T02:30:00+00:00", "workable", "d-id", False, error="429 too many requests")
        problems = digest.source_health(self.s, SEEN, status_log="/nonexistent")
        self.assertTrue(any(p.startswith("workable/d-id") for p in problems))
        self.s.log_poll("2026-09-06T02:30:00+00:00", "workable", "d-id", True, 2, 0)
        problems = digest.source_health(self.s, SEEN, status_log="/nonexistent")
        self.assertFalse(any(p.startswith("workable/d-id") for p in problems), "it is answering again")

    def test_a_source_still_failing_stays_in_the_footer(self):
        self.s.log_poll("2026-09-04T02:30:00+00:00", "workable", "redox", True, 12, 0)
        self.s.log_poll("2026-09-05T02:30:00+00:00", "workable", "redox", False, error="503 down")
        problems = digest.source_health(self.s, SEEN, status_log="/nonexistent")
        self.assertTrue(any(p.startswith("workable/redox") for p in problems))

    def test_a_company_off_the_list_stops_being_reported_as_broken(self):
        """Twelve studios came off the list on the 5th under the second
        principle, and workable/pixomondo went on reporting the 429 it threw
        the day it was removed. Nothing polls it any more, so nothing can ever
        mark it recovered, and the line would have stayed in the footer for
        good. A source that is not polled is not a health problem."""
        self.s.log_poll("2026-09-05T02:30:00+00:00", "workable", "pixomondo", False, error="429 too many requests")
        self.s.log_poll("2026-09-04T02:30:00+00:00", "ashby", "gone", True, 0, 0)
        self.s.log_poll("2026-09-05T02:30:00+00:00", "ashby", "gone", True, 0, 0)
        live = {"kept": {"slug": "kept"}}
        problems = digest.source_health(self.s, SEEN, status_log="/nonexistent", companies=live)
        self.assertEqual([p for p in problems if "pixomondo" in p or "gone" in p], [])
        # Without the list there is nothing to check against, so it still reports.
        problems = digest.source_health(self.s, SEEN, status_log="/nonexistent")
        self.assertTrue(any("pixomondo" in p for p in problems))

    def test_a_company_marked_dropped_is_off_the_list_too(self):
        self.s.log_poll("2026-09-05T02:30:00+00:00", "workable", "monks", False, error="429 too many requests")
        live = {"monks": {"slug": "monks", "dropped": "2026-09-05"}}
        problems = digest.source_health(self.s, SEEN, status_log="/nonexistent", companies=live)
        self.assertEqual([p for p in problems if "monks" in p], [])

    def test_an_empty_board_is_not_called_an_outage(self):
        """zero_twice_running only reads polls that succeeded, so the endpoint
        answered and returned nothing. That is a company with nothing open, not
        a broken slug, and it should not read like a 429."""
        for day in ("04", "05"):
            self.s.log_poll(f"2026-09-{day}T02:30:00+00:00", "ashby", "flawless-ai", True, 0, 0)
        live = {"flawless-ai": {"slug": "flawless-ai"}}
        line = next(p for p in digest.source_health(self.s, SEEN, status_log="/nonexistent", companies=live)
                    if p.startswith("ashby/flawless-ai"))
        self.assertIn("answers", line)
        self.assertNotIn("zero postings", line)

    def test_a_company_off_the_list_is_not_nominated_for_dropping(self):
        """company_yield reads the postings table, which keeps every row a
        company ever produced. The W36 digest asked Matt to drop monks and
        elastic and both had been off the list since the 5th, so the command it
        printed would have done nothing."""
        for i in range(20):
            self.s.upsert(posting(source="greenhouse", source_id=f"g{i}", company_slug="gone",
                                  url=f"https://x/g{i}", title="Backend Engineer"), "2026-09-05T00:00:00+00:00")
        rows = digest.dead_weight(self.s, self.r, {"kept": {"slug": "kept"}})
        self.assertEqual([ln for ln in rows if "gone" in ln], [])

    def test_the_breakdown_adds_up_to_the_score_beside_it(self):
        """Curriculum was missing from the printed list, so every entry in
        every digest was three short, or five where two areas hit, and the
        parts never summed to the total printed on the line above them."""
        import re
        md, _ = digest.build(self.s, self.r, COMPANIES, NOW)
        entries = [b for b in md.split("### ")[1:]]
        checked = 0
        for e in entries:
            head = re.search(r"score (\d+)", e)
            line = re.search(r"^Score: (.+)$", e, re.M)
            if not head or not line:
                continue
            total = sum(int(v) for v in re.findall(r"([+-]\d+)", line.group(1)))
            self.assertEqual(total, int(head.group(1)), e.splitlines()[0])
            checked += 1
        self.assertGreater(checked, 0, "no entries to check")

    def test_all_sources_answered(self):
        md, _ = digest.build(self.s, self.r, now=NOW)
        self.assertIn("All sources answered.", md)


class PayModel(unittest.TestCase):
    """Location-adjusted pay is what decides whether the move north costs money,
    so the digest asks the question rather than leaving it to offer stage."""

    def setUp(self):
        self.s = Store(":memory:")
        self.r = rules()
        p = posting(source="greenhouse", source_id="1", company_slug="acme", url="https://x/1",
                    remote="remote", location="Remote - US", title="Senior Creative Technologist",
                    description="pipeline comfyui python", comp_min=140000, comp_max=165000)
        pid, _ = self.s.upsert(p, SEEN)
        self.pid = pid

    def md(self, pay_model):
        cs = {"acme": {"slug": "acme", "name": "Acme", "tier": 1, "pay_model": pay_model}}
        row = self.s.get(self.pid)
        self.s.set_score(self.pid, score(row, self.r, NOW, cs["acme"]))
        md, _ = digest.build(self.s, self.r, cs, NOW)
        return md

    def test_location_adjusted_is_called_out(self):
        self.assertIn("location-adjusted, so the move north cuts it", self.md("location-adjusted"))

    def test_unknown_asks_the_question(self):
        self.assertIn("Ask whether pay is the same wherever you live", self.md("unknown"))

    def test_same_everywhere_says_nothing(self):
        md = self.md("same-everywhere")
        self.assertNotIn("Pay model unknown", md)
        self.assertNotIn("location-adjusted", md)


class Headquarters(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.r = rules()
        p = posting(source="greenhouse", source_id="1", company_slug="acme", url="https://x/1",
                    remote="remote", location="Remote - US", title="Senior Creative Technologist",
                    description="pipeline comfyui python", comp_min=140000, comp_max=165000)
        self.pid, _ = self.s.upsert(p, SEEN)

    def md(self, **extra):
        c = {"slug": "acme", "name": "Acme", "tier": 1, **extra}
        self.s.set_score(self.pid, score(self.s.get(self.pid), self.r, NOW, c))
        md, _ = digest.build(self.s, self.r, {"acme": c}, NOW)
        return md

    def test_a_known_location_is_printed(self):
        """The company HQ is labelled, and the posting's own location prints
        before it, because the digest used to print the HQ where a reader takes
        the posting location to be, so Reddit rows read San Francisco while the
        posting said Remote - United States."""
        md = self.md(hq="Hillsboro, OR")
        self.assertIn("HQ Hillsboro, OR", md)
        self.assertIn("remote · Remote - US · ", md)

    def test_an_unknown_location_adds_nothing(self):
        md = self.md()
        self.assertIn("Senior Creative Technologist, Acme", md)
        self.assertNotIn(" ·  · ", md, "a missing location must not leave an empty separator")


class DeadWeight(unittest.TestCase):
    """A company polling hundreds of listings and clearing none of them is
    spending budget for nothing. The digest says so and stops there: pruning
    the list is Matt's call, not a scheduled job's."""

    def setUp(self):
        self.s = Store(":memory:")
        self.r = rules()

    def add(self, slug, n, on_target=0):
        for i in range(n):
            p = posting(source="greenhouse", source_id=f"{slug}-{i}", company_slug=slug,
                        url=f"https://x/{slug}/{i}", remote="remote", location="Remote - US",
                        title="Senior Creative Technologist" if i < on_target else "Regional Sales Manager",
                        description="pipeline comfyui python" if i < on_target else "quota territory accounts",
                        comp_min=140000, comp_max=165000)
            pid, _ = self.s.upsert(p, SEEN)
            self.s.set_score(pid, score(self.s.get(pid), self.r, NOW, {"slug": slug, "tier": 1}))

    def test_a_company_with_no_hits_is_named(self):
        self.add("webflow", 20)
        out = digest.dead_weight(self.s, self.r, {"webflow": {"name": "Webflow", "hq": "San Francisco, CA"}})
        joined = "\n".join(out)
        self.assertIn("Webflow, San Francisco, CA: 20 postings, 0 on target", joined)
        self.assertIn("python -m scraper drop webflow", joined)

    def test_a_company_under_the_floor_is_left_alone(self):
        self.add("tiny", 3)
        self.assertEqual(digest.dead_weight(self.s, self.r, {}), [])

    def test_a_company_that_ever_landed_is_not_dead_weight(self):
        self.add("runway", 20, on_target=1)
        joined = "\n".join(digest.dead_weight(self.s, self.r, {}))
        self.assertNotIn("runway", joined)

    def test_the_section_is_absent_when_everything_earns_its_poll(self):
        self.add("runway", 20, on_target=2)
        md, _ = digest.build(self.s, self.r, {}, NOW)
        self.assertNotIn("Earning their poll", md)

    def test_yield_is_sorted_worst_first(self):
        self.add("a", 5)
        self.add("b", 30)
        rows = self.s.company_yield()
        self.assertEqual(rows[0]["company_slug"], "b", "most postings for nothing comes first")


class DeadWeightReasons(unittest.TestCase):
    """The dead-weight section printed counts only, so a title miss, a gate
    miss and a real absence all read the same line. Now it says why."""

    def test_the_top_reasons_print_beside_the_count(self):
        import tempfile
        from scraper.posting import posting as make
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "p.db")
            for i in range(16):
                p = make(source="greenhouse", source_id=str(i), company_slug="figma", url=f"https://x/{i}", remote="onsite", location="United States", title=f"Product Designer {i}", description="Figma.")
                pid, _ = s.upsert(p, "2026-09-05T00:00:00+00:00")
                s.set_score(pid, {"score": 0, "rules": [], "flags": [], "version": "2.0", "pile": "logged", "drop_reason": "remote: remote claim is onsite" if i < 14 else "no title fit and no intersection", "proof_lead": "x", "legs_hit": [], "curriculum": [], "title_tier": None, "remote": "fail", "comp": "pass"})
            lines = digest.dead_weight(s, {"digest": {"dead_weight_min_postings": 15}}, {"figma": {"name": "Figma"}})
            s.close()
        joined = "\n".join(lines)
        self.assertIn("Figma: 16 postings, 0 on target, 14 remote: remote claim is onsite, 2 no title fit", joined)


class PageSurvivesRerun(unittest.TestCase):
    """The markdown is the record of what arrived, the page is the surface he
    works all week. Writing the digest twice in a day used to leave the page
    with nothing on it, because select() drops a posting it has already
    surfaced and the page was reading the same selection as the record."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.s = Store(":memory:")
        self.r = rules()
        p = posting(source="greenhouse", source_id="1", company_slug="acme", url="https://x/1",
                    title="Senior Creative Technologist", remote="remote", location="Remote - US",
                    description="Pipeline and product work, comfyui, python tooling.",
                    comp_min=180000, comp_max=220000)
        pid, _ = self.s.upsert(p, SEEN)
        self.s.set_score(pid, score(self.s.get(pid), self.r, NOW, COMPANIES["acme"]))

    def test_second_run_keeps_the_week_on_the_page(self):
        first, n1, page = digest.write(self.s, self.r, self.dir, COMPANIES, NOW)
        self.assertEqual(n1, 1)
        self.assertIn("<h3>What they wrote</h3>", page.read_text(encoding="utf-8"))
        _, n2, page2 = digest.write(self.s, self.r, self.dir, COMPANIES, NOW)
        html = page2.read_text(encoding="utf-8")
        self.assertEqual(n2, 0, "the markdown still only records what is new")
        self.assertEqual(html.count('<details class="card"'), 1, "the page still carries the week")
        self.assertIn("Pipeline and product work", html)

    def test_a_posting_surfaced_before_the_week_stays_off_the_page(self):
        """kept_since is a week, not forever, or the page grows without end."""
        digest.write(self.s, self.r, self.dir, COMPANIES, NOW)
        self.s.db.execute("UPDATE postings SET digested_at = ?", ("2026-08-01T00:00:00+00:00",))
        self.s.db.commit()
        _, _, page = digest.write(self.s, self.r, self.dir, COMPANIES, NOW)
        self.assertEqual(page.read_text(encoding="utf-8").count('<details class="card"'), 0)


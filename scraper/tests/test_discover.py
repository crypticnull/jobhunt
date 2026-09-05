import json
import unittest
from datetime import datetime, timezone

from scraper import companies, discover
from scraper.http import HttpError
from scraper.score import RULES_PATH, load_rules
from scraper.store import Store

RULES = load_rules(RULES_PATH, local="/nonexistent")
NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)

REMOTIVE = {
    "jobs": [
        {"id": 1, "company_name": "Frame Co", "title": "Creative Technologist", "url": "https://r/1", "description": "ComfyUI pipeline work. Apply at https://jobs.lever.co/frameco/abc", "publication_date": "2026-09-01T10:00:00"},
        {"id": 2, "company_name": "Acme", "title": "Accountant", "url": "https://r/2", "description": "ledgers"},
        {"id": 3, "company_name": "Sales Co", "title": "Account Executive", "url": "https://r/3", "description": "Sell our motion design platform to After Effects studios."},
        {"id": 4, "company_name": "Backend Co", "title": "Senior Backend Engineer", "url": "https://r/4", "description": "REST API, automation, server-side rendering, Python, workflow orchestration, data modeling."},
    ]
}
WWR = """<rss><channel>
<item><title>Frame Co: Technical Artist</title><link>https://w/1</link><description>Houdini and real-time</description></item>
<item><title>Other Co: Copywriter</title><link>https://w/2</link><description>words</description></item>
</channel></rss>"""
HIMALAYAS = {"jobs": [
    {"title": "Motion Designer", "companyName": "Loose Co", "applicationLink": "https://h/1", "description": "<p>After Effects and Python scripting.</p>", "locationRestrictions": ["United States"], "pubDate": 1788249600},
    {"title": "Motion Designer", "companyName": "Company", "applicationLink": "https://h/2", "description": "<p>After Effects work.</p>", "locationRestrictions": ["United States"]},
    {"title": "Creative Technologist", "companyName": "Hop Co", "applicationLink": "https://h/3", "description": "<p>ComfyUI and Houdini.</p>", "locationRestrictions": ["United States"]},
]}
JOBICY = {"jobs": [{"id": 9, "jobTitle": "3D Generalist", "companyName": "Ashby Co", "url": "https://j/9", "jobDescription": "Houdini. <a href='https://jobs.ashbyhq.com/ashbyco/1'>apply</a>", "jobGeo": "USA", "pubDate": "2026-09-01 08:00:00"}]}
ARBEITNOW = {"data": [{"slug": "x", "title": "Generative Artist", "company_name": "Onsite Co", "url": "https://a/1", "description": "ComfyUI", "remote": False}]}
REMOTEOK = [
    {"legal": "notice"},
    {"id": "77", "position": "Pipeline TD", "company": "Green Co", "url": "https://ro/77", "description": "Pipeline and tooling", "apply_url": "https://boards.greenhouse.io/greenco/jobs/1", "date": "2026-09-01T00:00:00+00:00"},
]
HN_SEARCH = {"hits": [{"objectID": "500", "title": "Ask HN: Who wants to be hired? (September 2026)"}, {"objectID": "400", "title": "Ask HN: Who is hiring? (September 2026)"}]}
HN_THREAD = {
    "children": [
        {"id": 401, "author": "a", "created_at": "2026-09-01T15:00:00Z", "text": "Tiny Labs (YC S26) | Creative Technologist | REMOTE (US) | $150k-$180k<p>We build a generative video pipeline in ComfyUI and Python."},
        {"id": 402, "author": "b", "created_at": "2026-09-01T15:01:00Z", "text": "Desk Co | Motion Designer | ONSITE San Francisco | Houdini work"},
        {"id": 403, "author": "[deleted]", "text": ""},
        {"id": 404, "author": "c", "created_at": "2026-09-01T15:02:00Z", "text": "We are hiring a creative technologist, remote, ComfyUI and Houdini, no pipes in this one"},
    ]
}


def get_json(url):
    if "greenhouse" in url:
        return {"jobs": [{"id": 1, "title": "Creative Technologist", "absolute_url": "https://x/1", "location": {"name": "Remote"}}]}
    if "remotive" in url:
        return REMOTIVE
    if "himalayas" in url:
        return HIMALAYAS
    if "jobicy" in url:
        return JOBICY
    if "arbeitnow" in url:
        return ARBEITNOW
    if "remoteok" in url:
        return REMOTEOK
    if "search_by_date" in url:
        return HN_SEARCH
    if "items/400" in url:
        return HN_THREAD
    raise HttpError(url, 404, "no fixture")


# The apply button on a job page is where the company's real board leaks out.
HOP_PAGE = "<html><a href='https://boards.greenhouse.io/hopco/jobs/7'>Apply</a></html>"


def get_text(url):
    if "weworkremotely" in url:
        return WWR
    if url == "https://h/3":
        return HOP_PAGE
    return "<html>nothing here</html>"


def known(*records):
    return list(records)


class Discover(unittest.TestCase):
    def test_boards_are_harvested_and_known_companies_marked(self):
        frame = companies.record("frame-co", "Frame Co", "lever", "frameco", "studio-ai", today="2026-09-01")
        found = discover.discover(known(frame), RULES, get_json, get_text)
        by = {(i["company"], i["title"]): i for i in found}
        self.assertTrue(by[("Frame Co", "Creative Technologist")]["known"])
        self.assertEqual(by[("Frame Co", "Creative Technologist")]["ats"], ("lever", "frameco"))
        self.assertEqual(by[("Green Co", "Pipeline TD")]["ats"], ("greenhouse", "greenco"), "the apply link gives the board away")
        self.assertEqual(by[("Ashby Co", "3D Generalist")]["ats"], ("ashby", "ashbyco"), "links in the description survive to be harvested")
        self.assertIsNone(by[("Loose Co", "Motion Designer")]["ats"])
        self.assertNotIn(("Acme", "Accountant"), by)
        self.assertNotIn(("Onsite Co", "Generative Artist"), by, "arbeitnow's remote flag is respected")
        self.assertIn("comfyui", by[("Frame Co", "Creative Technologist")]["terms"])

    def test_the_jobs_that_flooded_the_first_live_run_are_gone(self):
        """The first real night added forty-eight companies, nearly all sales,
        QA and backend roles, because the scoring legs match api, automation
        and rendering. Discovery uses a tighter list now."""
        found = discover.discover([], RULES, get_json, get_text)
        titles = [i["title"] for i in found]
        self.assertNotIn("Account Executive", titles, "a sales title is out even when the description says motion design")
        self.assertNotIn("Senior Backend Engineer", titles, "api, automation and rendering are not a creative signal")
        self.assertNotIn("Accountant", titles)
        self.assertTrue(all(i["company"].lower() != "company" for i in found), "a generic company name is not a company")

    def test_a_board_one_hop_in_is_found(self):
        found = {i["company"]: i for i in discover.discover([], RULES, get_json, get_text)}
        self.assertEqual(found["Hop Co"]["ats"], ("greenhouse", "hopco"), "the apply link on the job page gives the board away")

    def test_page_fetches_are_capped(self):
        rules = json.loads(json.dumps(RULES))
        rules["discovery"]["max_page_fetches"] = 0
        found = {i["company"]: i for i in discover.discover([], rules, get_json, get_text)}
        self.assertIsNone(found["Hop Co"]["ats"], "no fetches left, so no board")
        self.assertEqual(found["Green Co"]["ats"], ("greenhouse", "greenco"), "a board in the posting itself costs no fetch")

    def test_hn_thread_is_parsed_and_only_remote_kept(self):
        found = discover.discover([], RULES, get_json, get_text, sources=("hn",))
        self.assertEqual([(i["company"], i["title"], i["location"]) for i in found], [("Tiny Labs", "Creative Technologist", "REMOTE (US)")])
        # the no-pipe comment is dropped rather than guessed at: the first real
        # run turned one into a company called
        # "beacon-ai-builds-intelligent-systems-that-make-aviation-safer"
        self.assertEqual(found[0]["url"], "https://news.ycombinator.com/item?id=401")
        self.assertEqual(found[0]["posted_at"], "2026-09-01T15:00:00+00:00")

    def test_one_dead_feed_does_not_kill_the_rest(self):
        def flaky(url):
            if "himalayas" in url:
                raise HttpError(url, 503, "down")
            return get_json(url)

        errors = []
        found = discover.discover([], RULES, flaky, get_text, errors=errors)
        self.assertEqual(errors, ["himalayas: HttpError: 503 down <https://himalayas.app/jobs/api?limit=100>"])
        self.assertTrue(any(i["company"] == "Green Co" for i in found))

    def test_render(self):
        found = discover.discover([], RULES, get_json, get_text)
        text = discover.render(found, ["hn: boom"])
        self.assertIn("Green Co (board found: greenhouse/greenco, the next poll adds it)", text)
        self.assertIn("Loose Co (no board found, the posting itself is stored)", text)
        self.assertIn("feed error: hn: boom", text)
        self.assertEqual(discover.render([]), "Nothing hit the intersection terms today.")

    def test_dates_are_normalized(self):
        self.assertEqual(discover._iso(1788249600), "2026-09-01T08:00:00+00:00")
        self.assertEqual(discover._iso("2026-09-01 08:00:00"), "2026-09-01T08:00:00")
        self.assertIsNone(discover._iso("yesterday"))


class Grow(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.data = companies.empty()
        companies.add(self.data, companies.record("frame-co", "Frame Co", "lever", "frameco", "studio-ai", today="2026-09-01"))

    def test_boards_become_companies_and_boardless_postings_are_stored(self):
        out = discover.grow(self.s, self.data, RULES, get_json, get_text, now=NOW)
        by_slug = {c["slug"]: c for c in self.data["companies"]}
        self.assertEqual(by_slug["green-co"]["ats"], {"kind": "greenhouse", "board": "greenco"})
        self.assertEqual((by_slug["green-co"]["category"], by_slug["green-co"]["tier"], by_slug["green-co"]["priority"]), ("discovered", None, 3))
        self.assertEqual(by_slug["ashby-co"]["ats"]["kind"], "ashby")
        self.assertEqual(by_slug["loose-co"]["ats"], {"kind": "manual", "board": None})
        self.assertEqual(by_slug["tiny-labs"]["ats"]["kind"], "manual")
        self.assertEqual(by_slug["hop-co"]["ats"], {"kind": "greenhouse", "board": "hopco"}, "found one hop in, still pollable")
        self.assertEqual(len(out["companies"]), 5)
        rows = {(r["company_slug"], r["source"]): r for r in self.s.open_postings()}
        self.assertIn(("loose-co", "himalayas"), rows)
        self.assertIn(("tiny-labs", "hn"), rows)
        self.assertNotIn(("green-co", "remoteok"), rows, "a pollable board's postings come from the poll, not the feed")
        self.assertNotIn(("frame-co", "remotive"), rows, "a known pollable company is left to the poll")
        hn = rows[("tiny-labs", "hn")]
        self.assertEqual((hn["comp_min"], hn["comp_max"], hn["remote_class"]), (150000, 180000, "remote"))
        self.assertIsNotNone(hn["score"])
        self.assertEqual(len(out["postings"]), 2)

    def test_the_same_role_reposted_is_one_role(self):
        """We Work Remotely reposts under -1, -2, -3 URLs. CapsLock's one job
        arrived three times in the live dry run."""
        payload = {"jobs": [
            {"id": i, "company_name": "Dup Co", "title": "Motion Designer", "url": f"https://r/dup{i}", "description": "After Effects."}
            for i in (10, 11, 12)
        ]}
        found = discover.discover([], RULES, lambda u: payload if "remotive" in u else get_json(u), get_text, sources=("remotive",))
        self.assertEqual(len(found), 1)

    def test_grow_reports_what_it_scanned(self):
        out = discover.grow(self.s, self.data, RULES, get_json, get_text, now=NOW)
        self.assertGreater(out["scanned"], out["found"], "the selectivity is the number to watch")

    def test_second_run_adds_nothing_new(self):
        discover.grow(self.s, self.data, RULES, get_json, get_text, now=NOW)
        n = len(self.data["companies"])
        out = discover.grow(self.s, self.data, RULES, get_json, get_text, now=NOW)
        self.assertEqual((len(self.data["companies"]), out["companies"], out["postings"]), (n, [], []))

    def test_caps_hold(self):
        out = discover.grow(self.s, self.data, RULES, get_json, get_text, now=NOW, board_cap=1, posting_cap=1)
        kinds = [c["ats"]["kind"] for c in out["companies"]]
        self.assertEqual(kinds.count("manual"), 1)
        self.assertEqual(len([k for k in kinds if k != "manual"]), 1)
        self.assertEqual(len(out["postings"]), 1)


class Caps(unittest.TestCase):
    """The caps were function defaults written when the list was ten long. They
    are config now, because the point of discovery is finding companies before
    they are famous and that needs room."""

    def test_the_ruleset_supplies_the_caps(self):
        r = load_rules(RULES_PATH, local="/nonexistent")
        self.assertEqual(r["discovery"]["board_cap"], 40)
        self.assertEqual(r["discovery"]["posting_cap"], 80)

    def test_an_explicit_argument_still_wins(self):
        import inspect
        sig = inspect.signature(discover.grow)
        self.assertIsNone(sig.parameters["board_cap"].default)
        self.assertIsNone(sig.parameters["posting_cap"].default)

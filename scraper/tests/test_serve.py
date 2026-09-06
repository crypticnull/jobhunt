"""The console. Every test drives the handler through a real socket, because
the thing that broke before was never the function, it was the wiring between
the page, the request and the store."""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import HTTPServer
from pathlib import Path

from scraper import serve
from scraper.posting import posting
from scraper.score import RULES_PATH, _deep_merge, load_rules, score
from scraper.store import Store

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
SEEN = "2026-09-01T00:00:00+00:00"
BAND = {
    "gates": {"comp": {"pass_min_annual": 100000, "flag_min_annual": 80000, "fail_below_annual": 80000, "hourly_floor": 60}},
    "score": {"comp": {"bands": [{"midpoint_min": 120000, "points": 20}]}},
}
BODY = "We need pipeline and product work, comfyui, python tooling, motion systems."


class Console(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.db = str(self.dir / "postings.db")
        rules = _deep_merge(load_rules(RULES_PATH, local="/nonexistent"), json.loads(json.dumps(BAND)))
        co = {"slug": "runway", "name": "Runway", "tier": 1}
        store = Store(self.db)
        p = posting(source="greenhouse", source_id="1", company_slug="runway", url="https://x/1",
                    title="Design Engineer", remote="remote", location="Remote - US",
                    description=BODY, comp_min=250000, comp_max=310000)
        self.pid, _ = store.upsert(p, SEEN)
        store.set_score(self.pid, score(store.get(self.pid), rules, NOW, co))
        store.close()

        companies = self.dir / "companies.json"
        companies.write_text(json.dumps({"version": 1, "companies": [
            {"slug": "runway", "name": "Runway", "careers_url": "https://runway/careers",
             "ats": {"kind": "ashby", "board": "runway"}, "category": "ai-video", "tier": 1,
             "size": None, "priority": 1, "lead_proof": None, "pay_model": "unknown",
             "hq": "New York, NY", "remote_notes": "", "added": "2026-09-01", "last_reviewed": "2026-09-01"},
        ]}), encoding="utf-8")

        console = serve.Console(self.db, str(companies), self.dir / "letters")
        console.rules = rules
        self.httpd = HTTPServer(("127.0.0.1", 0), serve.handler_for(console))
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.read().decode("utf-8")

    def post(self, path, payload):
        req = urllib.request.Request(self.base + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())

    def test_the_page_carries_the_posting_body(self):
        """The whole point. The bodies were always in the store and the only
        surface that showed them was a file that went stale the same night."""
        status, html = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(BODY, html)
        self.assertIn("Design Engineer", html)

    def test_the_page_has_live_controls_and_a_file_does_not(self):
        _, html = self.get("/")
        self.assertIn('class="act live"', html)
        self.assertIn('class="dec"', html)
        store = Store(self.db)
        try:
            from scraper import digest_html
            saved = digest_html.render(store, load_rules(RULES_PATH, local="/nonexistent"), None, NOW)
        finally:
            store.close()
        self.assertNotIn("act live", saved)
        self.assertIn("Pick for a letter", saved)

    def test_a_decision_reaches_the_store(self):
        status, out = self.post("/api/mark", {"id": self.pid, "state": "applied"})
        self.assertEqual((status, out["state"]), (200, "applied"))
        store = Store(self.db)
        try:
            self.assertEqual(store.state_of(self.pid), "applied")
        finally:
            store.close()

    def test_an_unknown_state_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post("/api/mark", {"id": self.pid, "state": "hired"})
        self.assertEqual(e.exception.code, 400)

    def test_the_brief_is_written_and_returned(self):
        status, out = self.post("/api/brief", {"id": self.pid})
        self.assertEqual(status, 200)
        self.assertIn("Runway", out["brief"])
        self.assertTrue(Path(out["path"]).exists())

    def test_a_missing_posting_is_a_404_not_a_stack_trace(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post("/api/brief", {"id": 9999})
        self.assertEqual(e.exception.code, 404)

    def test_the_resume_renders(self):
        status, html = self.get("/resume")
        self.assertEqual(status, 200)
        self.assertIn("Matt Rodenbeck", html)

    def test_favicon_is_answered_rather_than_logged_as_missing(self):
        with urllib.request.urlopen(self.base + "/favicon.ico") as r:
            self.assertEqual(r.status, 204)


if __name__ == "__main__":
    unittest.main()

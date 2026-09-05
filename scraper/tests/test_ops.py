"""What the 2026-09-05 review found about running unattended: a dead feed
killed the poll, a 429 was never retried, the digest named a command that did
not exist, and a backup could land in the repo root."""

import io
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scraper import companies, digest, discover, http
from scraper.__main__ import main
from scraper.store import Store

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


class Feeds(unittest.TestCase):
    def test_a_challenge_page_is_an_error_line_not_a_crash(self):
        errors = []
        html = "<!DOCTYPE html><html><body>Just a moment<br><script>challenge()</script></body></html>"
        items = discover.collect(get_json=lambda u: json.loads(html), get_text=lambda u: html, sources=("wwr", "remotive"), errors=errors)
        self.assertEqual(items, [])
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any(e.startswith("wwr: ParseError") for e in errors), errors)


class Retries(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        self.patch = mock.patch.object(http, "_sleep", lambda s: self.sleeps.append(s))
        self.patch.start()
        http._last.clear()

    def tearDown(self):
        self.patch.stop()

    def _resp(self, body):
        r = mock.MagicMock()
        r.status = 200
        r.read.return_value = body.encode()
        r.__enter__.return_value = r
        return r

    def test_a_429_is_retried_then_read(self):
        calls = []

        def urlopen(req, timeout=None):
            calls.append(req.full_url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {"Retry-After": "3"}, io.BytesIO())
            return self._resp("{}")

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            status, body = http.fetch("https://apply.workable.com/api/v1/widget/accounts/d-id")
        self.assertEqual((status, body), (200, "{}"))
        self.assertEqual(len(calls), 2)
        self.assertIn(3.0, self.sleeps, "Retry-After is honoured")

    def test_a_404_is_not_retried(self):
        def urlopen(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO())

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(http.HttpError) as cm:
                http.fetch("https://boards-api.greenhouse.io/v1/boards/nope/jobs")
        self.assertEqual(cm.exception.status, 404)

    def test_requests_to_one_host_are_paced(self):
        with mock.patch.object(urllib.request, "urlopen", lambda req, timeout=None: self._resp("{}")):
            http.fetch("https://apply.workable.com/a")
            http.fetch("https://apply.workable.com/b")
        self.assertTrue(any(0 < s <= http.MIN_GAP for s in self.sleeps), self.sleeps)


class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.companies = self.root / "companies.json"
        data = {"version": 1, "companies": [
            companies.record("acme", "Acme", "greenhouse", "acme", "product-inhouse", 2, "https://acme.com/careers"),
            companies.record("webflow", "Webflow", "greenhouse", "webflow", "product-inhouse", 2, "https://webflow.com/careers"),
        ]}
        companies.save(self.companies, data)
        self.db = self.root / "postings.db"
        Store(self.db).close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_drop_removes_a_company_and_names_an_unknown_one(self):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            rc = main(["--companies", str(self.companies), "--db", str(self.db), "drop", "webflow", "nobody"])
        self.assertEqual(rc, 1)
        left = [c["slug"] for c in companies.load(self.companies)["companies"]]
        self.assertEqual(left, ["acme"])
        self.assertIn("unknown   nobody", out.getvalue())

    def test_backup_refuses_an_empty_target(self):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            rc = main(["--companies", str(self.companies), "--db", str(self.db), "backup", "--to", ""])
        self.assertEqual(rc, 2)
        self.assertIn("empty", err.getvalue())

    def test_backup_refuses_the_repo_root(self):
        from scraper.__main__ import ROOT
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            rc = main(["--companies", str(self.companies), "--db", str(self.db), "backup", "--to", str(ROOT)])
        self.assertEqual(rc, 2)
        self.assertIn("inside the repo", err.getvalue())


class Footer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Store(Path(self.tmp.name) / "p.db")

    def tearDown(self):
        self.s.close()
        self.tmp.cleanup()

    def test_the_same_error_every_night_is_one_line(self):
        for day in ("01", "02", "03"):
            self.s.log_poll(f"2026-09-{day}T04:00:00+00:00", "workable", "d-id", False, error="HttpError: 429 Too Many Requests")
        lines = digest.source_health(self.s, "2026-08-30", status_log=Path(self.tmp.name) / "none", now=NOW)
        self.assertEqual(len([ln for ln in lines if "d-id" in ln]), 1)
        self.assertIn("3 polls, last 2026-09-03", lines[0])

    def test_the_status_log_reaches_the_digest(self):
        log = Path(self.tmp.name) / "nightly-status.log"
        log.write_text("Sat 09/05/2026  4:00:01.12 push failed\n", encoding="utf-8")
        lines = digest.source_health(self.s, "2026-08-30", status_log=log, now=datetime.now(timezone.utc))
        self.assertTrue(any("scheduled task" in ln and "push failed" in ln for ln in lines), lines)

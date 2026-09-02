import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scraper import companies
from scraper.__main__ import main


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "companies.json")
        self.db = str(Path(self.tmp.name) / "postings.db")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(["--companies", self.path, "--db", self.db, *argv])
        return code, out.getvalue()

    def test_add_detects_and_writes(self):
        with mock.patch("scraper.adapters.detect", return_value=("lever", "acme", 3)):
            code, out = self.run_cli("add", "https://acme.com/careers", "--category", "ai-video", "--name", "Acme")
        self.assertEqual(code, 0)
        self.assertIn("added acme: lever/acme, 3 postings live", out)
        data = companies.load(self.path)
        self.assertEqual(data["companies"][0]["ats"], {"kind": "lever", "board": "acme"})
        self.assertEqual(data["companies"][0]["careers_url"], "https://acme.com/careers")

    def test_add_fails_cleanly_when_undetectable(self):
        with mock.patch("scraper.adapters.detect", return_value=None):
            code, out = self.run_cli("add", "https://acme.com/careers", "--category", "ai-video")
        self.assertEqual(code, 2)
        self.assertIn("could not detect", out)

    def test_add_manual_skips_detection(self):
        code, out = self.run_cli("add", "https://acme.com/careers", "--category", "brand-inhouse", "--kind", "manual", "--name", "Acme")
        self.assertEqual(code, 0)
        self.assertEqual(companies.load(self.path)["companies"][0]["ats"]["kind"], "manual")

    def test_check_exit_code_reflects_dead(self):
        data = companies.empty()
        companies.add(data, companies.record("a", "A", "greenhouse", "a", "ai-video", today="2026-09-01"))
        companies.save(self.path, data)
        with mock.patch("scraper.adapters.probe", return_value=(False, 0, "404")):
            code, out = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("DEAD", out)
        with mock.patch("scraper.adapters.probe", return_value=(True, 4, None)):
            code, out = self.run_cli("check")
        self.assertEqual(code, 0)

    def test_import_reads_a_file_and_reports(self):
        src = Path(self.tmp.name) / "companies.txt"
        src.write_text("# comment\nai-video | https://acme.com/careers | Acme\n\nstudio-ai | https://nowhere.com/jobs | Nowhere\nai-video | https://acme.com/careers | Acme\n", encoding="utf-8")
        detect = lambda url: ("greenhouse", "acme", 5) if "acme" in url else None
        with mock.patch("scraper.adapters.detect", side_effect=detect):
            code, out = self.run_cli("import", str(src), "--priority", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("added     Acme: greenhouse/acme, 5 postings live", out)
        self.assertIn("unknown   Nowhere", out)
        self.assertIn("1 added, 1 already there, 1 without a detectable ATS", out)
        data = companies.load(self.path)
        self.assertEqual([(c["slug"], c["tier"], c["priority"]) for c in data["companies"]], [("acme", 1, 1)])
        with mock.patch("scraper.adapters.detect", side_effect=detect):
            code, out = self.run_cli("import", str(src), "--manual")
        self.assertIn("added     Nowhere: manual", out)
        self.assertEqual(len(companies.load(self.path)["companies"]), 2)

    def test_import_refuses_a_bad_line(self):
        src = Path(self.tmp.name) / "companies.txt"
        src.write_text("startup | https://acme.com | Acme\n", encoding="utf-8")
        code, out = self.run_cli("import", str(src))
        self.assertEqual(code, 2)
        self.assertIn("line 1", out)

    def test_stats_on_empty_store(self):
        code, out = self.run_cli("stats")
        self.assertEqual(code, 0)
        self.assertIn("postings 0", out)

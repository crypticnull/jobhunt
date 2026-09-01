import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scraper import companies, manual
from scraper.__main__ import main
from scraper.store import Store


class FromText(unittest.TestCase):
    def test_file_source(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "posting.txt"
            f.write_text("Remote role. Pays $150,000 - $180,000.", encoding="utf-8")
            text, url = manual.read_source(str(f))
        self.assertIn("Remote role", text)
        self.assertIsNone(url)

    def test_url_source_is_reduced_to_text(self):
        text, url = manual.read_source("https://acme.com/jobs/1", get_text=lambda u: "<p>Hello <b>there</b></p>")
        self.assertEqual((text, url), ("Hello there", "https://acme.com/jobs/1"))

    def test_posting_shape(self):
        p = manual.from_text("acme", "Creative Engineer", "text", location="Remote - US")
        self.assertEqual((p["source"], p["source_id"], p["remote"], p["url"]), ("manual", None, "remote", "manual:acme"))
        self.assertEqual(manual.from_text("acme", "X", "t", remote="hybrid")["remote"], "hybrid")


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.companies = str(self.dir / "companies.json")
        self.db = str(self.dir / "postings.db")
        data = companies.empty()
        companies.add(data, companies.record("acme", "Acme", "manual", None, "ai-video", today="2026-09-01"))
        companies.save(self.companies, data)
        self.src = self.dir / "posting.txt"
        self.src.write_text("Senior role, fully remote. Base pay $150,000 to $180,000. ComfyUI and pipeline work.", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(["--companies", self.companies, "--db", self.db, *argv])
        return code, out.getvalue()

    def test_adds_scored_row_and_is_idempotent(self):
        code, out = self.run_cli("add-posting", str(self.src), "--company", "acme", "--title", "Senior Creative Technologist", "--url", "https://acme.com/jobs/9", "--location", "Remote")
        self.assertEqual(code, 0, out)
        self.assertIn("added posting 1", out)
        self.assertIn("next: python -m letters brief 1", out)
        s = Store(self.db)
        row = s.get(1)
        s.close()
        self.assertEqual((row["source"], row["url"], row["remote_class"], row["comp_min"], row["comp_max"]), ("manual", "https://acme.com/jobs/9", "remote", 150000, 180000))
        self.assertIsNotNone(row["score"])
        code, out = self.run_cli("add-posting", str(self.src), "--company", "acme", "--title", "Senior Creative Technologist")
        self.assertIn("updated posting 1", out)

    def test_unknown_company_is_refused(self):
        code, out = self.run_cli("add-posting", str(self.src), "--company", "nobody", "--title", "X")
        self.assertEqual(code, 2)
        self.assertIn("not on the list", out)

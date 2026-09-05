import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scraper import companies
from scraper import __main__ as main_mod
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
            code, out = self.run_cli("import", str(src), "--priority", "1", "--no-guess")
        self.assertEqual(code, 0, out)
        self.assertIn("added     Acme: greenhouse/acme, 5 postings live", out)
        self.assertIn("unknown   Nowhere", out)
        self.assertIn("1 added (0 found by guessing the board slug), 1 already there, 1 with no board found", out)
        data = companies.load(self.path)
        self.assertEqual([(c["slug"], c["tier"], c["priority"]) for c in data["companies"]], [("acme", 1, 1)])
        with mock.patch("scraper.adapters.detect", side_effect=detect):
            code, out = self.run_cli("import", str(src), "--manual", "--no-guess")
        self.assertIn("added     Nowhere: manual", out)
        self.assertEqual(len(companies.load(self.path)["companies"]), 2)

    def test_import_falls_back_to_guessing_the_slug(self):
        src = Path(self.tmp.name) / "companies.txt"
        src.write_text("ai-video | https://nowhere.example/careers | Luma AI\n", encoding="utf-8")
        with mock.patch("scraper.adapters.detect", return_value=None), mock.patch("scraper.adapters.guess", return_value=("lever", "lumaai", 4)):
            code, out = self.run_cli("import", str(src))
        self.assertEqual(code, 0, out)
        self.assertIn("added     Luma AI: lever/lumaai, 4 postings live", out)
        self.assertIn("1 added (1 found by guessing the board slug)", out)

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


class SeedFiles(unittest.TestCase):
    """The nightly job points import at a directory, so a seed list dropped into
    data/seeds is taken in on its own rather than waiting for a command."""

    def test_a_directory_yields_every_txt_sorted(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("b.txt", "a.txt", "notes.md"):
                (Path(d) / name).write_text("", encoding="utf-8")
            names = [f.name for f in main_mod.seed_files(d)]
            self.assertEqual(names, ["a.txt", "b.txt"])

    def test_a_file_yields_itself(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "seeds.txt"
            f.write_text("", encoding="utf-8")
            self.assertEqual(main_mod.seed_files(str(f)), [f])

    def test_a_missing_path_yields_that_path_so_the_error_is_reported(self):
        self.assertEqual(main_mod.seed_files("/nonexistent/x.txt"), [Path("/nonexistent/x.txt")])

    def test_the_shipped_seed_file_parses(self):
        root = Path(__file__).resolve().parents[2]
        rows = main_mod.parse_import_lines((root / "data" / "seeds" / "2026-09-05-narrowing.txt").read_text(encoding="utf-8"))
        self.assertGreater(len(rows), 10)
        self.assertTrue(all(u.startswith("http") for _, u, _, _ in rows))


class SeedHeadquarters(unittest.TestCase):
    """A seed line may carry a fourth field, `City, ST`. Matt moves to
    Washington or Oregon in June 2027, so where a company sits is worth
    recording even while the search is remote-only."""

    def test_three_fields_still_parse_with_no_headquarters(self):
        rows = main_mod.parse_import_lines("ai-video | https://x.com/careers | X")
        self.assertEqual(rows, [("ai-video", "https://x.com/careers", "X", None)])

    def test_a_fourth_field_is_the_headquarters(self):
        rows = main_mod.parse_import_lines("studio-ai | https://laika.com/careers | Laika | Hillsboro, OR")
        self.assertEqual(rows[0][3], "Hillsboro, OR")

    def test_an_empty_fourth_field_reads_as_unknown(self):
        rows = main_mod.parse_import_lines("ai-video | https://x.com/careers | X |")
        self.assertIsNone(rows[0][3])

    def test_five_fields_are_refused(self):
        with self.assertRaises(ValueError):
            main_mod.parse_import_lines("ai-video | https://x.com/careers | X | Bend, OR | extra")

    def test_the_western_seed_file_parses_and_every_row_states_a_location(self):
        root = Path(__file__).resolve().parents[2]
        rows = main_mod.parse_import_lines((root / "data" / "seeds" / "2026-09-05-western.txt").read_text(encoding="utf-8"))
        self.assertGreater(len(rows), 50)
        self.assertTrue(all(hq and ", " in hq for *_, hq in rows), "every western seed states City, ST")

    def test_a_record_carries_the_headquarters_through(self):
        r = companies.record("laika", "Laika", "greenhouse", "laika", "studio-ai", hq="Hillsboro, OR")
        self.assertEqual(r["hq"], "Hillsboro, OR")
        self.assertIsNone(companies.record("x", "X", "greenhouse", "x", "ai-video")["hq"])

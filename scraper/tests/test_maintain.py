import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scraper import maintain
from scraper.posting import posting
from scraper.store import Store


class Maintain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "postings.db"
        s = Store(self.db)
        pid, _ = s.upsert(posting(source="lever", source_id="1", company_slug="acme", title="T", url="https://x", remote="remote"))
        s.mark(pid, "applied", letter_path="data/local/letters/acme-1.md")
        s.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_is_a_working_copy_and_prunes(self):
        dest = self.dir / "backups"
        for d in ("2026-09-01", "2026-09-02", "2026-09-03"):
            target = maintain.backup(self.db, dest, keep=2, today=d)
        self.assertEqual(sorted(p.name for p in dest.iterdir()), ["postings-2026-09-02.db", "postings-2026-09-03.db"])
        n = sqlite3.connect(str(target)).execute("SELECT COUNT(*) FROM postings").fetchone()[0]
        self.assertEqual(n, 1)

    def test_export_status(self):
        target, n = maintain.export_status(self.db, self.dir / "exports", month="2026-09")
        self.assertEqual((target.name, n), ("status-2026-09.json", 2))
        rows = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual([r["state"] for r in rows], ["new", "applied"])
        self.assertEqual(rows[1]["company_slug"], "acme")

    def test_fixture_trims_and_writes(self):
        payload = {"jobs": [{"id": i} for i in range(5)]}
        target = maintain.fixture("greenhouse", "acme", self.dir / "fx", get_json=lambda u: payload, keep=2)
        self.assertEqual(target.name, "greenhouse.json")
        self.assertEqual(len(json.loads(target.read_text(encoding="utf-8"))["jobs"]), 2)
        with self.assertRaises(KeyError):
            maintain.fixture("linkedin", "x", self.dir)


class Heartbeat(unittest.TestCase):
    def test_it_records_the_run_and_reads_back(self):
        from scraper import companies as C
        s = Store(":memory:")
        s.upsert(posting(source="greenhouse", source_id="1", company_slug="acme", title="X", url="https://x/1", remote="remote"))
        recs = [
            C.record("acme", "Acme", "greenhouse", "acme", "ai-video", today="2026-09-01"),
            C.record("hand", "Hand", "manual", None, "ai-video", today="2026-09-01"),
        ]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "last-run.json"
            beat = maintain.heartbeat(s, recs, path, ran_at="2026-09-02T04:00:00+00:00", errors=2)
            self.assertEqual((beat["companies"], beat["pollable"], beat["open"], beat["poll_errors"]), (2, 1, 1, 2))
            self.assertEqual(maintain.last_run(path), beat)
        self.assertIsNone(maintain.last_run(Path("/nonexistent/last-run.json")))

import tempfile
import unittest
from pathlib import Path

from pipeline import frontmatter as fm
from pipeline.ingest import IngestError, ingest
from pipeline.tests.test_media_frontmatter import jpeg_bytes, png_bytes

RECORD = """---
slug: quest-2025
title: Quest 2025
year: 2025
summary: Hand written, stays.
hero: { src: assets/hero.svg, width: 1600, height: 900, alt: "Placeholder alt" }
video: { provider: r2, mp4: [https://cdn/x.mp4], hls: null, poster: null, width: 1920, height: 1080, duration: null }
stills: []
process: [{ kind: storyboard, src: assets/logo-loop_storyboard_v01.png, width: 1, height: 1, alt: "Kept alt", caption: "Kept caption" }]
---

The story stays too.
"""


class Ingest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.projects = root / "projects"
        self.drop = root / "drop"
        self.drop.mkdir()
        pdir = self.projects / "quest-2025"
        (pdir / "assets").mkdir(parents=True)
        (pdir / "index.md").write_text(RECORD, encoding="utf-8")
        (pdir / "assets" / "hero.svg").write_text('<svg viewBox="0 0 1600 900"></svg>')
        (pdir / "assets" / "logo-loop_storyboard_v01.png").write_bytes(png_bytes(1200, 675))
        self.logs = []

    def tearDown(self):
        self.tmp.cleanup()

    def log(self, s):
        self.logs.append(s)

    def probes(self):
        return {
            "probe_video": lambda p: {"width": 3840, "height": 2160, "duration": 24.0},
            "make_poster": lambda src, out: Path(out).write_bytes(jpeg_bytes(1920, 1080)),
        }

    def test_full_drop_updates_record_and_keeps_hand_written_fields(self):
        (self.drop / "quest_2025_key-art_hero_v02.png").write_bytes(png_bytes(2560, 1440))
        (self.drop / "quest_2025_key-art_still_v01.jpg").write_bytes(jpeg_bytes(1920, 1080))
        (self.drop / "quest_2025_logo-loop_styleframe_v01.png").write_bytes(png_bytes(1600, 900))
        (self.drop / "quest_2025_logo-loop_final_v03.mp4").write_bytes(b"not really video")
        out = ingest(self.drop, projects_dir=self.projects, log=self.log, **self.probes())
        s = out[0]
        self.assertEqual((s["created"], s["hero"], s["stills"], s["process"], s["video"], s["poster"]), (False, "assets/hero.png", 1, 2, "quest_2025_logo-loop_final_v03.mp4", "extracted"))
        text = (self.projects / "quest-2025" / "index.md").read_text(encoding="utf-8")
        front, body = fm.split(text)
        self.assertIn("summary: Hand written, stays.", text)
        self.assertIn("The story stays too.", body)
        hero = fm.get(front, "hero")
        self.assertEqual((hero["src"], hero["width"], hero["height"]), ("assets/hero.png", 2560, 1440))
        self.assertEqual(hero["alt"], "Quest 2025 hero still", "new hero source gets a fresh alt")
        video = fm.get(front, "video")
        self.assertEqual((video["provider"], video["mp4"], video["width"], video["height"], video["duration"], video["poster"]), ("r2", ["https://cdn/x.mp4"], 3840, 2160, 24.0, "assets/poster.jpg"))
        process = {p["src"]: p for p in fm.get(front, "process")}
        self.assertEqual(process["assets/logo-loop_storyboard_v01.png"]["alt"], "Kept alt")
        self.assertEqual(process["assets/logo-loop_storyboard_v01.png"]["caption"], "Kept caption")
        self.assertEqual(process["assets/logo-loop_storyboard_v01.png"]["width"], 1200, "sizes come from disk, never from the old record")
        self.assertEqual(process["assets/logo-loop_styleframe_v01.png"]["kind"], "styleframe")
        self.assertEqual(fm.get(front, "stills")[0]["width"], 1920)
        self.assertFalse((self.projects / "quest-2025" / "assets" / "quest_2025_logo-loop_final_v03.mp4").exists(), "video never enters the repo")
        self.assertTrue((self.projects / "quest-2025" / "assets" / "poster.jpg").exists())

    def test_one_bad_name_refuses_the_whole_drop(self):
        (self.drop / "quest_2025_key-art_still_v01.jpg").write_bytes(jpeg_bytes(10, 10))
        (self.drop / "Quest Final.mp4").write_bytes(b"x")
        with self.assertRaises(IngestError):
            ingest(self.drop, projects_dir=self.projects, log=self.log, **self.probes())
        self.assertFalse((self.projects / "quest-2025" / "assets" / "key-art_still_v01.jpg").exists())
        self.assertTrue(any("try quest_final_final_v01.mp4" in l or "try " in l for l in self.logs))

    def test_dry_run_writes_nothing(self):
        (self.drop / "quest_2025_key-art_still_v01.jpg").write_bytes(jpeg_bytes(10, 10))
        before = (self.projects / "quest-2025" / "index.md").read_text(encoding="utf-8")
        out = ingest(self.drop, projects_dir=self.projects, dry_run=True, log=self.log, **self.probes())
        self.assertEqual(out[0]["stills"], 1)
        self.assertEqual((self.projects / "quest-2025" / "index.md").read_text(encoding="utf-8"), before)
        self.assertFalse((self.projects / "quest-2025" / "assets" / "key-art_still_v01.jpg").exists())

    def test_new_project_is_scaffolded_and_needs_a_hero(self):
        (self.drop / "summit_2026_opener_still_v01.jpg").write_bytes(jpeg_bytes(10, 10))
        with self.assertRaises(IngestError):
            ingest(self.drop, projects_dir=self.projects, log=self.log, **self.probes())
        (self.drop / "summit_2026_opener_hero_v01.jpg").write_bytes(jpeg_bytes(1920, 1080))
        out = ingest(self.drop, projects_dir=self.projects, log=self.log, **self.probes())
        self.assertTrue(out[0]["created"])
        text = (self.projects / "summit-2026" / "index.md").read_text(encoding="utf-8")
        self.assertIn("title: Summit 2026", text)
        self.assertIn("summary: TODO", text)
        self.assertIn("hero: { src: assets/hero.jpg, width: 1920, height: 1080", text)

    def test_highest_version_wins(self):
        (self.drop / "quest_2025_key-art_still_v01.jpg").write_bytes(jpeg_bytes(10, 10))
        (self.drop / "quest_2025_key-art_still_v03.jpg").write_bytes(jpeg_bytes(20, 20))
        out = ingest(self.drop, projects_dir=self.projects, log=self.log, **self.probes())
        self.assertEqual(out[0]["copied"], ["key-art_still_v03.jpg"])

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pipeline import encode
from pipeline import frontmatter as fm

RECORD = """---
slug: quest-2025
title: Quest 2025
hero: { src: assets/hero.png, width: 2560, height: 1440, alt: "Hero" }
video: { provider: none, mp4: [], hls: null, poster: assets/poster.jpg, width: 3840, height: 2160, duration: 24.0 }
---

Story.
"""


class Encode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "quest_2025_logo-loop_final_v03.mp4"
        self.src.write_bytes(b"x")
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def fake_run(self, cmd, **kw):
        self.calls.append(cmd)
        Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(cmd[-1]).write_bytes(b"encoded")
        if cmd[-1].endswith(".m3u8"):
            (Path(cmd[-1]).parent / "seg_000.ts").write_bytes(b"ts")
        return SimpleNamespace(returncode=0, stderr="")

    def test_ladder_and_manifest(self):
        m = encode.encode(self.src, "quest-2025", self.root / "encodes", run=self.fake_run)
        self.assertEqual([x["height"] for x in m["mp4"]], [1080, 720])
        self.assertEqual(m["hls"], "hls/index.m3u8")
        self.assertEqual(len(self.calls), 3)
        self.assertIn("-crf", self.calls[0])
        self.assertIn("scale=-2:720", self.calls[1])
        self.assertIn("+faststart", self.calls[0])
        saved = json.loads((self.root / "encodes" / "quest-2025" / "manifest.json").read_text())
        self.assertEqual(saved, m)
        self.assertEqual(encode.load_manifest("quest-2025", self.root / "encodes"), m)

    def test_no_hls(self):
        m = encode.encode(self.src, "quest-2025", self.root / "encodes", hls=False, run=self.fake_run)
        self.assertIsNone(m["hls"])
        self.assertEqual(len(self.calls), 2)

    def test_failed_ffmpeg_raises(self):
        with self.assertRaises(encode.EncodeError):
            encode.encode(self.src, "q", self.root, run=lambda cmd, **kw: SimpleNamespace(returncode=1, stderr="boom"))

    def test_publish_sets_urls_and_keeps_probe_fields(self):
        projects = self.root / "projects"
        (projects / "quest-2025").mkdir(parents=True)
        (projects / "quest-2025" / "index.md").write_text(RECORD, encoding="utf-8")
        m = encode.encode(self.src, "quest-2025", self.root / "encodes", run=self.fake_run)
        v = encode.publish("quest-2025", m, "https://media.example.com/", projects)
        self.assertEqual(v["provider"], "r2")
        self.assertEqual(v["mp4"], ["https://media.example.com/quest-2025/quest-2025_1080p.mp4", "https://media.example.com/quest-2025/quest-2025_720p.mp4"])
        self.assertEqual(v["hls"], "https://media.example.com/quest-2025/hls/index.m3u8")
        self.assertEqual((v["width"], v["height"], v["duration"], v["poster"]), (3840, 2160, 24.0, "assets/poster.jpg"))
        text = (projects / "quest-2025" / "index.md").read_text(encoding="utf-8")
        self.assertIn("Story.", text)
        self.assertEqual(fm.get(fm.split(text)[0], "hero")["alt"], "Hero")

    def test_upload_commands(self):
        m = encode.encode(self.src, "quest-2025", self.root / "encodes", run=self.fake_run)
        cmds = encode.upload_commands("quest-2025", m, "portfolio-media", self.root / "encodes")
        self.assertEqual(len(cmds), 4)
        self.assertTrue(cmds[0].startswith("npx wrangler r2 object put portfolio-media/quest-2025/quest-2025_1080p.mp4 --file "))
        self.assertTrue(any("hls/index.m3u8" in c for c in cmds))

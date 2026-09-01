import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from pipeline import frontmatter as fm
from pipeline.media import MediaError, image_size


def png_bytes(w, h):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def jpeg_bytes(w, h):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
    sof0 = b"\xff\xc0" + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", h, w) + b"\x03" + b"\x00" * 9
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


def webp_bytes(w, h):
    dims = struct.pack("<I", w - 1)[:3] + struct.pack("<I", h - 1)[:3]
    vp8x = b"VP8X" + struct.pack("<I", 10) + b"\x00\x00\x00\x00" + dims
    return b"RIFF" + struct.pack("<I", 4 + len(vp8x)) + b"WEBP" + vp8x


class ImageSize(unittest.TestCase):
    def test_headers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.png").write_bytes(png_bytes(2560, 1440))
            (root / "b.jpg").write_bytes(jpeg_bytes(1920, 1080))
            (root / "c.webp").write_bytes(webp_bytes(800, 600))
            (root / "d.gif").write_bytes(b"GIF89a" + struct.pack("<HH", 320, 240))
            (root / "e.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900"></svg>')
            (root / "f.svg").write_text('<svg width="120px" height="80"></svg>')
            (root / "g.bin").write_bytes(b"nope")
            self.assertEqual(image_size(root / "a.png"), (2560, 1440))
            self.assertEqual(image_size(root / "b.jpg"), (1920, 1080))
            self.assertEqual(image_size(root / "c.webp"), (800, 600))
            self.assertEqual(image_size(root / "d.gif"), (320, 240))
            self.assertEqual(image_size(root / "e.svg"), (1600, 900))
            self.assertEqual(image_size(root / "f.svg"), (120, 80))
            with self.assertRaises(MediaError):
                image_size(root / "g.bin")

    def test_real_placeholder_heroes(self):
        root = Path(__file__).resolve().parents[2] / "data" / "projects"
        for svg in root.glob("*/assets/hero.svg"):
            self.assertEqual(image_size(svg), (1600, 900), svg)


class Frontmatter(unittest.TestCase):
    TEXT = '---\nslug: quest-2025\ntitle: Quest 2025\ntools: [Cinema 4D, After Effects]\nhero: { src: assets/hero.svg, width: 1600, height: 900, alt: "Quest, with a comma" }\nvideo: { provider: none, mp4: [https://x/a.mp4], hls: null, poster: null, width: 1920, height: 1080, duration: 24.5 }\nstills: []\n---\n\nBody stays.\n'

    def test_roundtrip_and_types(self):
        front, body = fm.split(self.TEXT)
        self.assertEqual(body, "\nBody stays.\n")
        self.assertEqual(fm.get(front, "tools"), ["Cinema 4D", "After Effects"])
        hero = fm.get(front, "hero")
        self.assertEqual(hero, {"src": "assets/hero.svg", "width": 1600, "height": 900, "alt": "Quest, with a comma"})
        video = fm.get(front, "video")
        self.assertEqual((video["mp4"], video["hls"], video["duration"]), (["https://x/a.mp4"], None, 24.5))
        self.assertEqual(fm.join(front, body), self.TEXT)

    def test_set_key_replaces_or_appends_and_quotes_when_needed(self):
        front, body = fm.split(self.TEXT)
        front = fm.set_key(front, "stills", [{"src": "assets/a.jpg", "width": 1, "height": 2, "alt": "plain"}])
        front = fm.set_key(front, "process", [{"kind": "wip", "src": "assets/b.png", "width": 3, "height": 4, "alt": "a: colon", "caption": ""}])
        text = fm.join(front, body)
        self.assertIn('stills: [{ src: assets/a.jpg, width: 1, height: 2, alt: plain }]', text)
        self.assertIn('alt: "a: colon", caption: ""', text)
        self.assertEqual(text.count("slug: quest-2025"), 1)
        self.assertEqual(fm.get(fm.split(text)[0], "process")[0]["alt"], "a: colon")

    def test_scalars(self):
        self.assertEqual(fm.parse_value("null"), None)
        self.assertEqual(fm.parse_value("true"), True)
        self.assertEqual(fm.parse_value("12"), 12)
        self.assertEqual(fm.parse_value("'quoted, yes'"), "quoted, yes")
        self.assertEqual(fm.emit("2025"), '"2025"', "a numeric-looking string stays a string")
        self.assertEqual(fm.emit("null"), '"null"')

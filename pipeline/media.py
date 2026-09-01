"""Dimensions and durations without a media library. Images are read from
their headers in the standard library; video goes through ffprobe and
ffmpeg, which are on the workstation already."""

import json
import re
import shutil
import struct
import subprocess
from pathlib import Path


class MediaError(Exception):
    pass


def image_size(path):
    """(width, height) for png, jpeg, gif, webp and svg."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".svg":
        return _svg_size(path.read_text(encoding="utf-8", errors="replace"))
    with path.open("rb") as f:
        head = f.read(32)
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            w, h = struct.unpack(">II", head[16:24])
            return w, h
        if head.startswith(b"GIF8"):
            w, h = struct.unpack("<HH", head[6:10])
            return w, h
        if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
            return _webp_size(head, f)
        if head.startswith(b"\xff\xd8"):
            f.seek(2)
            return _jpeg_size(f)
    raise MediaError(f"{path.name}: not a png, jpeg, gif, webp or svg I can read")


def _jpeg_size(f):
    while True:
        marker = f.read(2)
        if len(marker) < 2 or marker[0] != 0xFF:
            raise MediaError("jpeg: no size marker found")
        code = marker[1]
        if code in (0xD8, 0x01) or 0xD0 <= code <= 0xD7:
            continue
        length = struct.unpack(">H", f.read(2))[0]
        if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            data = f.read(5)
            h, w = struct.unpack(">HH", data[1:5])
            return w, h
        f.seek(length - 2, 1)


def _webp_size(head, f):
    chunk = head[12:16]
    if chunk == b"VP8X":
        f.seek(24)
        b = f.read(6)
        w = 1 + (b[0] | b[1] << 8 | b[2] << 16)
        h = 1 + (b[3] | b[4] << 8 | b[5] << 16)
        return w, h
    if chunk == b"VP8L":
        f.seek(21)
        b = f.read(4)
        bits = b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8 ":
        f.seek(26)
        w, h = struct.unpack("<HH", f.read(4))
        return w & 0x3FFF, h & 0x3FFF
    raise MediaError("webp: unknown chunk")


def _svg_size(text):
    def attr(name):
        m = re.search(rf'\b{name}="([\d.]+)(?:px)?"', text)
        return float(m.group(1)) if m else None

    w, h = attr("width"), attr("height")
    if w and h:
        return int(round(w)), int(round(h))
    m = re.search(r'viewBox="([\d.\s,-]+)"', text)
    if m:
        parts = re.split(r"[\s,]+", m.group(1).strip())
        if len(parts) == 4:
            return int(round(float(parts[2]))), int(round(float(parts[3])))
    raise MediaError("svg: no width/height or viewBox")


def video_info(path, ffprobe="ffprobe"):
    """{width, height, duration} via ffprobe."""
    if shutil.which(ffprobe) is None:
        raise MediaError(f"{ffprobe} not found; install ffmpeg or pass --ffprobe")
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise MediaError(f"ffprobe failed on {Path(path).name}: {out.stderr.strip()}")
    data = json.loads(out.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    duration = (data.get("format") or {}).get("duration")
    return {
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "duration": round(float(duration), 2) if duration else None,
    }


def extract_poster(video, out_path, ffmpeg="ffmpeg", at=1.0):
    if shutil.which(ffmpeg) is None:
        raise MediaError(f"{ffmpeg} not found; install ffmpeg or pass --ffmpeg")
    cmd = [ffmpeg, "-y", "-v", "error", "-ss", str(at), "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out_path)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise MediaError(f"ffmpeg failed extracting a poster from {Path(video).name}: {out.stderr.strip()}")
    return Path(out_path)

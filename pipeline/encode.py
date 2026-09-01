"""Encode a final for the web and publish its URLs into the record.

    python -m pipeline.encode encode SRC --slug quest-2025 [--out data/local/encodes] [--no-hls]
    python -m pipeline.encode publish quest-2025 --base-url https://media.example.com
    python -m pipeline.encode upload quest-2025 --bucket portfolio-media [--run]

Hand-tuned progressive MP4s at 1080 and 720, plus an HLS rendition for the
longer pieces, written under data/local/encodes so nothing heavy enters
the repo (ADR-0007). publish sets provider r2 and the URLs on the record
and leaves width, height, duration and the poster to what ingest probed.
upload prints the wrangler commands, or runs them with --run."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import frontmatter as fm

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "data" / "projects"
ENCODES = ROOT / "data" / "local" / "encodes"

# height -> x264 settings. crf 18 is visually lossless for motion work; the
# 720 rendition is the phone's fallback.
LADDER = [
    (1080, ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p"]),
    (720, ["-c:v", "libx264", "-preset", "slow", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p"]),
]
AUDIO = ["-c:a", "aac", "-b:a", "160k"]


class EncodeError(Exception):
    pass


def _run(cmd, run=None):
    run = run or subprocess.run
    out = run(cmd, capture_output=True, text=True)
    if getattr(out, "returncode", 0) != 0:
        raise EncodeError(f"{cmd[0]} failed: {getattr(out, 'stderr', '').strip()}")
    return out


def encode(src, slug, out_dir=ENCODES, hls=True, ffmpeg="ffmpeg", run=None):
    """Write the ladder and a manifest.json under out_dir/slug. Returns the manifest."""
    if run is None and shutil.which(ffmpeg) is None:
        raise EncodeError(f"{ffmpeg} not found; install ffmpeg or pass --ffmpeg")
    src = Path(src)
    dest = Path(out_dir) / slug
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {"slug": slug, "source": src.name, "mp4": [], "hls": None}
    for height, video_args in LADDER:
        target = dest / f"{slug}_{height}p.mp4"
        cmd = [ffmpeg, "-y", "-v", "error", "-i", str(src), "-vf", f"scale=-2:{height}", *video_args, *AUDIO, "-movflags", "+faststart", str(target)]
        _run(cmd, run)
        manifest["mp4"].append({"height": height, "file": target.name})
    if hls:
        hls_dir = dest / "hls"
        hls_dir.mkdir(exist_ok=True)
        cmd = [
            ffmpeg, "-y", "-v", "error", "-i", str(src), "-vf", "scale=-2:1080", *LADDER[0][1], *AUDIO,
            "-f", "hls", "-hls_time", "4", "-hls_playlist_type", "vod",
            "-hls_segment_filename", str(hls_dir / "seg_%03d.ts"), str(hls_dir / "index.m3u8"),
        ]
        _run(cmd, run)
        manifest["hls"] = "hls/index.m3u8"
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_manifest(slug, out_dir=ENCODES):
    path = Path(out_dir) / slug / "manifest.json"
    if not path.exists():
        raise EncodeError(f"no manifest for {slug} under {out_dir}; run encode first")
    return json.loads(path.read_text(encoding="utf-8"))


def publish(slug, manifest, base_url, projects_dir=PROJECTS, provider="r2"):
    """Set provider and URLs on the record's video field. Everything ingest
    probed stays. Returns the new video value."""
    record = Path(projects_dir) / slug / "index.md"
    if not record.exists():
        raise EncodeError(f"no record at {record}")
    text = record.read_text(encoding="utf-8")
    front, body = fm.split(text)
    video = dict(fm.get(front, "video") or {"width": 1920, "height": 1080, "duration": None, "poster": None})
    base = base_url.rstrip("/") + "/" + slug
    video["provider"] = provider
    video["mp4"] = [f"{base}/{m['file']}" for m in sorted(manifest["mp4"], key=lambda m: -m["height"])]
    video["hls"] = f"{base}/{manifest['hls']}" if manifest.get("hls") else None
    front = fm.set_key(front, "video", video)
    record.write_text(fm.join(front, body), encoding="utf-8")
    return video


def upload_commands(slug, manifest, bucket, out_dir=ENCODES, wrangler="npx wrangler"):
    """The wrangler put commands for everything in the manifest, in order."""
    dest = Path(out_dir) / slug
    files = [m["file"] for m in manifest["mp4"]]
    if manifest.get("hls"):
        files += sorted(p.relative_to(dest).as_posix() for p in (dest / "hls").glob("*") if p.is_file())
    return [f"{wrangler} r2 object put {bucket}/{slug}/{f} --file {dest / f}" for f in files]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m pipeline.encode", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ENCODES))
    ap.add_argument("--projects", default=str(PROJECTS))
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("encode")
    e.add_argument("src")
    e.add_argument("--slug", required=True)
    e.add_argument("--no-hls", action="store_true")
    e.add_argument("--ffmpeg", default="ffmpeg")

    p = sub.add_parser("publish")
    p.add_argument("slug")
    p.add_argument("--base-url", required=True, help="where the bucket is served from, e.g. https://media.example.com")

    u = sub.add_parser("upload")
    u.add_argument("slug")
    u.add_argument("--bucket", required=True)
    u.add_argument("--run", action="store_true", help="execute instead of printing")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "encode":
            m = encode(args.src, args.slug, args.out, hls=not args.no_hls, ffmpeg=args.ffmpeg)
            print(f"encoded {len(m['mp4'])} mp4(s)" + (" and hls" if m["hls"] else "") + f" under {Path(args.out) / args.slug}")
        elif args.cmd == "publish":
            v = publish(args.slug, load_manifest(args.slug, args.out), args.base_url, args.projects)
            print(f"{args.slug}: provider {v['provider']}, {len(v['mp4'])} mp4 url(s)" + (", hls" if v["hls"] else ""))
        else:
            cmds = upload_commands(args.slug, load_manifest(args.slug, args.out), args.bucket, args.out)
            for c in cmds:
                print(c)
                if args.run:
                    subprocess.run(c, shell=True, check=True)
    except EncodeError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

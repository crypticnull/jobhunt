"""Turn a folder of named files into record fields.

    python -m pipeline.ingest path/to/drop [--slug quest-2025] [--dry-run]

Every file is parsed against docs/naming.md; one bad name refuses the whole
drop with the corrected forms printed, because a half-ingested project is
worse than none. Images are copied into the project's assets directory
under their canonical names and probed for size. A final video is probed
for size and duration and a poster frame is pulled from it, but the video
itself never enters the repo. Then the record's hero, video, stills and
process fields are rewritten from what is on disk, alt text and captions
carried over where the source path is unchanged."""

import argparse
import shutil
import sys
from pathlib import Path

from . import frontmatter as fm
from . import media
from .naming import NamingError, parse

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "data" / "projects"
OWNED = ("hero", "video", "stills", "process")


class IngestError(Exception):
    pass


def _title(slug):
    return " ".join(w.capitalize() for w in slug.split("-"))


def _stub_record(slug, year):
    return "\n".join([
        "---",
        f"slug: {slug}",
        f"title: {_title(slug)}",
        "franchise: null",
        f"year: {year}",
        "client: TODO",
        "role: Senior motion designer",
        "disciplines: []",
        "tools: []",
        "turnaround: null",
        "summary: TODO one sentence for the card",
        "featured: false",
        "archive: false",
        "order: 99",
        "hero: null",
        "video: { provider: none, mp4: [], hls: null, poster: null, width: 1920, height: 1080, duration: null }",
        "stills: []",
        "process: []",
        "---",
        "",
        "TODO the project story.",
        "",
    ])


def plan(drop, slug=None):
    """Parse every file in the drop. Returns (parsed_by_slug, errors)."""
    files = sorted(p for p in Path(drop).iterdir() if p.is_file() and not p.name.startswith("."))
    parsed, errors = {}, []
    for f in files:
        try:
            d = parse(f.name)
        except NamingError as e:
            errors.append(e)
            continue
        d["path"] = f
        key = slug or d["slug"]
        parsed.setdefault(key, []).append(d)
    return parsed, errors


def _existing_text(entries, src, key):
    for e in entries or []:
        if isinstance(e, dict) and e.get("src") == src and e.get(key):
            return e[key]
    return None


def apply(slug, items, projects_dir=PROJECTS, dry_run=False, probe_video=None, make_poster=None, log=print):
    """Copy, probe and rewrite one project's record. Returns a summary dict."""
    probe_video = probe_video or media.video_info
    make_poster = make_poster or media.extract_poster
    pdir = Path(projects_dir) / slug
    record = pdir / "index.md"
    assets = pdir / "assets"
    year = items[0]["year"]
    created = not record.exists()
    text = record.read_text(encoding="utf-8") if record.exists() else _stub_record(slug, year)
    front, body = fm.split(text)
    title = fm.get(front, "title") or _title(slug)
    old = {k: fm.get(front, k) for k in OWNED}
    video = dict(old["video"] or {"provider": "none", "mp4": [], "hls": None, "poster": None, "width": 1920, "height": 1080, "duration": None})
    summary = {"slug": slug, "created": created, "copied": [], "video": None, "poster": None}

    # highest version wins per deliverable and stage
    best = {}
    for d in items:
        k = (d["deliverable"], d["stage"])
        if k not in best or d["version"] > best[k]["version"]:
            best[k] = d

    if not dry_run:
        assets.mkdir(parents=True, exist_ok=True)
    for d in best.values():
        if d["media"] == "video":
            info = probe_video(d["path"])
            video.update({"width": info["width"], "height": info["height"], "duration": info["duration"]})
            summary["video"] = d["name"]
            if not video.get("poster") and (d["deliverable"], "poster") not in best:
                target = assets / "poster.jpg"
                if not dry_run:
                    make_poster(d["path"], target)
                video["poster"] = "assets/poster.jpg"
                summary["poster"] = "extracted"
            continue
        target = assets / d["canonical"]
        if not dry_run:
            if d["stage"] in ("hero", "poster"):
                for stale in assets.glob(f"{d['stage']}.*"):
                    if stale != target:
                        stale.unlink()  # hero and poster are singletons
            shutil.copy2(d["path"], target)
        summary["copied"].append(d["canonical"])

    # rebuild the owned fields from disk
    hero, stills, process = None, [], []
    on_disk = sorted(assets.iterdir()) if assets.exists() else []
    if dry_run:
        on_disk = list({*on_disk, *(assets / d["canonical"] for d in best.values() if d["media"] == "image")})
    if dry_run:
        for d in best.values():
            if d["stage"] in ("hero", "poster"):
                on_disk = [f for f in on_disk if not (f.name.startswith(d["stage"] + ".") and f.name != d["canonical"])]
    for f in sorted(on_disk):
        src = f"assets/{f.name}"
        if f.name.startswith("hero."):
            w, h = _size(f, best, "hero")
            hero = {"src": src, "width": w, "height": h, "alt": (old["hero"] or {}).get("alt") if (old["hero"] or {}).get("src") == src else None}
            hero["alt"] = hero["alt"] or f"{title} hero still"
            continue
        if f.name.startswith("poster."):
            video["poster"] = src
            continue
        parts = f.stem.split("_")
        if len(parts) < 3:
            continue
        deliverable, stage = parts[0], parts[1]
        w, h = _size(f, best, stage, deliverable)
        if stage == "still":
            stills.append({"src": src, "width": w, "height": h, "alt": _existing_text(old["stills"], src, "alt") or f"{title}, {deliverable.replace('-', ' ')} still"})
        elif stage in ("storyboard", "styleframe", "wip", "breakdown"):
            process.append({
                "kind": stage,
                "src": src,
                "width": w,
                "height": h,
                "alt": _existing_text(old["process"], src, "alt") or f"{title} {stage}, {deliverable.replace('-', ' ')}",
                "caption": _existing_text(old["process"], src, "caption") or "",
            })
    if hero is None and old["hero"]:
        hero = old["hero"]
    if hero is None:
        raise IngestError(f"{slug}: a record needs a hero still; add {items[0]['project']}_{year}_<deliverable>_hero_v01.png to the drop")

    front = fm.set_key(front, "hero", hero)
    front = fm.set_key(front, "video", video)
    front = fm.set_key(front, "stills", stills)
    front = fm.set_key(front, "process", process)
    if not dry_run:
        pdir.mkdir(parents=True, exist_ok=True)
        record.write_text(fm.join(front, body), encoding="utf-8")
    summary.update({"hero": hero["src"], "stills": len(stills), "process": len(process)})
    return summary


def _size(path, best, stage, deliverable=None):
    """Probe the file on disk; in a dry run the file may only exist in the drop."""
    if path.exists():
        return media.image_size(path)
    for d in best.values():
        if d["stage"] == stage and (deliverable is None or d["deliverable"] == deliverable):
            return media.image_size(d["path"])
    raise IngestError(f"cannot size {path}")


def ingest(drop, slug=None, projects_dir=PROJECTS, dry_run=False, log=print, **probes):
    parsed, errors = plan(drop, slug)
    if errors:
        for e in errors:
            log(f"refused  {e.name}: {e.problem}")
            log(f"         try {e.suggestion}")
        raise IngestError(f"{len(errors)} file(s) refused; nothing was ingested")
    if not parsed:
        raise IngestError(f"nothing to ingest in {drop}")
    summaries = []
    for key, items in parsed.items():
        s = apply(key, items, projects_dir, dry_run=dry_run, log=log, **probes)
        summaries.append(s)
        verb = "would write" if dry_run else ("created" if s["created"] else "updated")
        log(f"{verb}  data/projects/{key}/index.md: hero {s['hero']}, {s['stills']} still(s), {s['process']} process file(s)"
            + (f", video {s['video']}" if s["video"] else "") + (f", poster {s['poster']}" if s["poster"] else ""))
    return summaries


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m pipeline.ingest", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("drop", help="a folder of files named per docs/naming.md")
    ap.add_argument("--slug", help="force every file into this record instead of {project}-{year}")
    ap.add_argument("--projects", default=str(PROJECTS))
    ap.add_argument("--dry-run", action="store_true", help="report without copying or writing")
    args = ap.parse_args(argv)
    try:
        ingest(args.drop, slug=args.slug, projects_dir=args.projects, dry_run=args.dry_run)
    except (IngestError, media.MediaError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Walk a folder of unsorted archive material and report what is in it.

    python -m pipeline.survey "X:/_CLAUDE/26_09_01_Job_Hunt/jobhunt/assets/_PORTFOLIO"

`pipeline.ingest` takes a flat drop of files already named per docs/naming.md.
This takes the opposite: a nested folder straight off a working drive, with
whatever names the projects happened to use. It reads, and never writes into
the folder it is given.

The output is the manifest docs/asset-intake.md describes, written to
data/local/intake, which is gitignored. Three things make it reviewable
rather than a wall of paths:

  junk is dropped        caches, previews, auto-saves and proxies never appear
  sequences collapse     a 4,000 frame render is one row with a count, because
                         listing every frame buries the six files that matter
  a name is proposed     naming.suggest turns each candidate into the name it
                         would need before ingest would take it

Everything it guesses is a guess, and the confidence column says so. Nothing
here decides anything; it produces the list a person then edits.
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .naming import IMAGE_EXT, STAGES, VIDEO_EXT, suggest

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "local" / "intake"

# Directories whose contents are never source material. Matched case-insensitively
# against each path part, so one entry covers every level of nesting.
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".astro", "dist",
    "cache", "caches", "proxy", "proxies", "preview", "previews",
    "autosave", "auto-save", "adobe premiere pro auto-save",
    "adobe premiere pro preview files", "adobe premiere pro captured audio",
    "adobe after effects auto-save", "ae auto-save",
    "backup", "backups", "thumbs", ".thumbnails", "temp", "tmp",
    "recovered", "conformed", "media cache", "media cache files",
}
SKIP_FILES = {".ds_store", "thumbs.db", "desktop.ini", "icon\r"}
SKIP_EXT = {"tmp", "lock", "part", "crdownload", "pek", "cfa", "mpgindex"}

DOC_EXT = {"pdf"}
RAW_IMAGE_EXT = {"tif", "tiff", "exr", "dpx", "tga", "bmp"}
SOURCE_EXT = {"aep", "aepx", "c4d", "hip", "hiplc", "hipnc", "blend", "prproj",
              "psd", "psb", "ai", "sesx", "ma", "mb", "fbx", "obj", "abc", "indd"}
AUDIO_EXT = {"wav", "mp3", "aif", "aiff", "m4a", "flac"}
DEV_EXT = {"py", "js", "jsx", "jsfl", "json", "csv", "txt", "md", "sh", "ps1", "expression"}
EXTRA_VIDEO_EXT = {"avi", "mxf", "m4v", "mts", "r3d", "braw"}

# Path keywords that name a stage. Order matters: the first hit wins, so the
# specific words sit above the vague ones. "frame" is last because it appears
# inside "styleframe" and "keyframe" and on its own means very little.
STAGE_HINTS = [
    ("storyboard", ("storyboard", "story board", "boards", "_sb_", "thumbnail")),
    ("styleframe", ("styleframe", "style frame", "stylefr", "lookdev", "look dev",
                    "styleboard", "concept", "exploration", "direction", "pitch")),
    ("breakdown", ("breakdown", "wireframe", "turntable", "aov", "passes", "contact sheet")),
    ("wip", ("wip", "work in progress", "review", "rough")),
    ("hero", ("key art", "keyart", "key-art", "hero")),
    ("poster", ("poster",)),
    ("final", ("final", "delivery", "deliverable", "master", "approved", "_out", "exports")),
    ("still", ("still", "grab", "frame")),
]

# Folder or filename fragments that identify a project. Longest match wins so
# "nitro create" beats "nitro" and "power awards" beats "power".
PROJECT_HINTS = {
    "quest": "quest",
    "nitro create": "nitro-create", "nitro-create": "nitro-create", "nitrocreate": "nitro-create", "nitro": "nitro-create",
    "summit": "summit",
    "power awards": "pag", "awards gala": "pag", "pag": "pag", "gala": "pag",
    "banfield": "banfield",
    "liveramp": "liveramp", "live ramp": "liveramp",
    "power camp": "power-camp",
    "soiree": "hq-soiree", "hq soiree": "hq-soiree",
    "hvhz": "hvhz-doors",
    "bill of rights": "bill-of-rights", "bill-of-rights": "bill-of-rights",
    "voidfall": "game", "survivors": "game",
    "ford": "ford", "linkedin": "linkedin", "oportun": "oportun",
}
# Every individual word used by a project hint, so "create" from "nitro create"
# cannot survive into a deliverable.
PROJECT_WORDS = {w for hint in PROJECT_HINTS for w in hint.split()} | set(PROJECT_HINTS.values())

SEQ = re.compile(r"^(?P<base>.*?)[._-]?(?P<num>\d{3,})$")
VERSION = re.compile(r"(?:^|[._\s-])v(\d{1,3})(?:$|[._\s-])", re.I)
TRAILING_INDEX = re.compile(r"[._\s-](\d{1,3})$")
YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def kind_of(ext):
    if ext in VIDEO_EXT or ext in EXTRA_VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT or ext in RAW_IMAGE_EXT:
        return "image"
    if ext in DOC_EXT:
        return "doc"
    if ext in SOURCE_EXT:
        return "source"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in DEV_EXT:
        return "dev"
    return "other"


def skipped(path, root):
    """True when a path is under a junk directory or is itself junk."""
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:
        if part.lower() in SKIP_DIRS or part.lower().startswith("_old"):
            return True
    name = rel.name.lower()
    if name in SKIP_FILES or name.startswith("._") or name.startswith("~"):
        return True
    return name.rpartition(".")[2] in SKIP_EXT


def guess_project(text):
    """Longest hint wins, so a folder named 'Nitro Create' does not read as
    'nitro' matching something else."""
    low = text.lower()
    best = None
    for hint, slug in PROJECT_HINTS.items():
        if hint in low and (best is None or len(hint) > len(best[0])):
            best = (hint, slug)
    return best[1] if best else None


def guess_year(text, fallback=None):
    """Prefer a four-digit year in the path. A folder stamped 26_09_01 is a
    date in year-month-day with a two-digit year, which is Matt's convention,
    so it is read that way rather than as 2026 pieces."""
    years = YEAR.findall(text)
    if years:
        return int(years[-1])
    m = re.search(r"(?<!\d)(\d{2})[_-](\d{2})[_-](\d{2})(?!\d)", text)
    if m and 1 <= int(m.group(2)) <= 12:
        return 2000 + int(m.group(1))
    return fallback


def guess_stage(text, kind):
    # Kind wins over any keyword for these three. A .aep inside a folder called
    # Delivery is still a project file, and proposing it as a final would put a
    # name on something ingest cannot take and Matt should never upload.
    if kind in ("source", "dev", "audio"):
        return kind
    low = text.lower()
    for stage, words in STAGE_HINTS:
        if any(w in low for w in words):
            # A video that reads as a still or a board is a final; the word came
            # from a folder name that applies to the images beside it.
            if kind == "video" and stage in ("still", "storyboard", "styleframe", "hero", "poster"):
                return "final"
            return stage
    if kind == "video":
        return "final"
    if kind == "source":
        return "source"
    if kind == "dev":
        return "dev"
    if kind == "image":
        return "still"
    return "unknown"


def guess_deliverable(stem):
    """The words left after the project, year, stage and version are taken out.
    Two tokens at most, because a deliverable is 'logo-loop', not a sentence."""
    tokens = [t for t in re.split(r"[\s_\-.]+", stem.lower()) if t]
    drop = set()
    for stage, words in STAGE_HINTS:
        drop.add(stage)
        drop.update(w.replace(" ", "") for w in words)
    out = []
    for t in tokens:
        t = re.sub(r"[^a-z0-9]+", "", t)
        if not t or t in drop or YEAR.fullmatch(t) or re.fullmatch(r"v?\d+", t):
            continue
        if t in PROJECT_WORDS or guess_project(t):
            continue
        out.append(t)
    return "-".join(out[:2]) if out else "unknown"


def guess_version(stem):
    """v03 in the name wins. Failing that a trailing index is the version, which
    is what keeps 'boards_01' and 'boards_02' from proposing the same name."""
    m = VERSION.search(stem)
    if m:
        return min(int(m.group(1)), 999)
    m = TRAILING_INDEX.search(stem)
    if m:
        return min(int(m.group(1)), 999)
    return 1


def collapse(paths):
    """Group numbered frames. Three or more files sharing a stem base and
    extension inside one directory become a single row carrying the count."""
    groups = defaultdict(list)
    singles = []
    for p in paths:
        stem, _, ext = p.name.rpartition(".")
        m = SEQ.match(stem)
        if m and m.group("base"):
            groups[(p.parent, m.group("base"), ext.lower())].append(p)
        else:
            singles.append(p)
    rows = []
    for (parent, base, ext), members in groups.items():
        if len(members) >= 3:
            rows.append((sorted(members)[0], len(members), sum(m.stat().st_size for m in members)))
        else:
            singles.extend(members)
    for p in singles:
        rows.append((p, 1, p.stat().st_size))
    return sorted(rows, key=lambda r: str(r[0]).lower())


def survey(folder):
    root = Path(folder)
    if not root.is_dir():
        raise SystemExit(f"not a folder: {folder}")
    files, skipped_n = [], 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if skipped(p, root):
            skipped_n += 1
            continue
        files.append(p)

    rows = []
    for path, count, size in collapse(files):
        rel = path.relative_to(root)
        ext = path.name.rpartition(".")[2].lower()
        kind = kind_of(ext)
        context = str(rel)
        project = guess_project(context)
        year = guess_year(context)
        stage = guess_stage(context, kind)
        stem = path.name.rpartition(".")[0]
        deliverable = guess_deliverable(stem)
        known = sum(x is not None and x != "unknown" for x in (project, year, stage if stage != "unknown" else None))
        confidence = ("high" if known == 3 else "medium" if known == 2 else "low")
        notes = []
        if count > 1:
            notes.append(f"sequence of {count} files")
        if ext == "pdf":
            notes.append("pdf, export pages to jpg before ingest")
        if kind == "source":
            notes.append("project file, record the path and leave it where it is")
        note = "; ".join(notes)
        # Only image and video files are proposed a name, because those are the
        # only two ingest accepts. Everything else is located, not staged.
        proposed = ""
        if project and year and stage in STAGES and ext in IMAGE_EXT | VIDEO_EXT:
            try:
                proposed = suggest(f"{project}_{year}_{deliverable}_{stage}_v{guess_version(stem):02d}.{ext}")
            except Exception:
                proposed = ""
        rows.append({
            "path": str(path),
            "bytes": size,
            "modified": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat(),
            "project": project or "unknown",
            "year": year or "",
            "deliverable": deliverable,
            "stage": stage,
            "confidence": confidence,
            "note": note,
            "proposed": proposed,
        })
    return rows, skipped_n


COLUMNS = ["path", "bytes", "modified", "project", "year", "deliverable", "stage", "confidence", "note", "proposed"]


def write(rows, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    return out


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def summary(rows, skipped_n, log=print):
    """A block short enough to paste into a chat. The per-project table is the
    part that says whether a project has enough material to be a case study."""
    log(f"{len(rows)} entries, {human(sum(r['bytes'] for r in rows))}, {skipped_n} junk files skipped")
    log("")
    by_project = defaultdict(Counter)
    sizes = Counter()
    for r in rows:
        key = f"{r['project']} {r['year']}".strip()
        by_project[key][r["stage"]] += 1
        sizes[key] += r["bytes"]
    log(f"{'project':<22} {'files':>6} {'size':>10}  stages")
    for key in sorted(by_project, key=lambda k: (k.startswith("unknown"), k)):
        stages = by_project[key]
        total = sum(stages.values())
        detail = ", ".join(f"{s} {n}" for s, n in stages.most_common())
        log(f"{key:<22} {total:>6} {human(sizes[key]):>10}  {detail}")
    log("")
    conf = Counter(r["confidence"] for r in rows)
    log("confidence: " + ", ".join(f"{k} {conf[k]}" for k in ("high", "medium", "low") if conf[k]))
    unknown = [r for r in rows if r["project"] == "unknown"]
    if unknown:
        folders = Counter(str(Path(r["path"]).parent) for r in unknown)
        log(f"\n{len(unknown)} entries could not be matched to a project. Top folders:")
        for folder, n in folders.most_common(10):
            log(f"  {n:>5}  {folder}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m pipeline.survey", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="the folder to read; it is never written to")
    ap.add_argument("--out", default=None, help="TSV path (default data/local/intake/<folder>.tsv)")
    args = ap.parse_args(argv)

    rows, skipped_n = survey(args.folder)
    out = Path(args.out) if args.out else DEFAULT_OUT / (Path(args.folder).name.strip("_.").lower() + ".tsv")
    write(rows, out)
    summary(rows, skipped_n)
    print(f"\nmanifest: {out}")
    print("Edit the project, year, deliverable and stage columns, then hand it back.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

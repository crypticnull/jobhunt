"""The filename token spec from docs/naming.md, as a parser that refuses
politely: a bad name raises NamingError carrying the corrected form."""

import re

STAGES = {
    "final": "video",
    "hero": "hero",
    "poster": "poster",
    "still": "still",
    "storyboard": "process",
    "styleframe": "process",
    "wip": "process",
    "breakdown": "process",
}
VIDEO_EXT = {"mp4", "mov", "webm", "mkv"}
IMAGE_EXT = {"jpg", "jpeg", "png", "webp", "gif", "svg"}

_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
PATTERN = re.compile(
    rf"^(?P<project>{_SLUG})_(?P<year>\d{{4}})_(?P<deliverable>{_SLUG})_(?P<stage>[a-z]+)_v(?P<version>\d{{2,3}})\.(?P<ext>[a-z0-9]+)$"
)


class NamingError(ValueError):
    def __init__(self, name, problem, suggestion):
        self.name, self.problem, self.suggestion = name, problem, suggestion
        super().__init__(f"{name}: {problem}. Try: {suggestion}")


def suggest(name):
    """Best-effort corrected form. Spaces and underscores separate tokens,
    hyphens stay inside them. Placeholders in angle brackets mark what the
    file name did not say."""
    base, _, ext = name.rpartition(".")
    if not base:
        base, ext = ext, ""
    ext = ext.lower()
    if ext == "jpeg":
        ext = "jpg"
    tokens = []
    for raw in re.split(r"[\s_]+", base.lower().strip()):
        t = re.sub(r"[^a-z0-9-]+", "", raw).strip("-")
        t = re.sub(r"-{2,}", "-", t)
        if t:
            tokens.append(t)
    version = next((t for t in tokens if re.fullmatch(r"v\d{1,3}", t)), None)
    tokens = [t for t in tokens if t != version]
    version = f"v{int(version[1:]):02d}" if version else "v01"
    year = next((t for t in tokens if re.fullmatch(r"(19|20)\d{2}", t)), None)
    tokens = [t for t in tokens if t != year]
    stage = next((t for t in tokens if t in STAGES), None)
    tokens = [t for t in tokens if t != stage]
    if stage is None:
        if ext in VIDEO_EXT:
            stage = "final"
            if len(tokens) >= 3:
                tokens = tokens[:-1]  # the odd last token was a mis-named stage
        else:
            stage = "<stage>"
    project = tokens[0] if tokens else "<project>"
    deliverable = "-".join(tokens[1:]) if len(tokens) > 1 else "<deliverable>"
    return f"{project}_{year or '<year>'}_{deliverable}_{stage}_{version}.{ext or '<ext>'}"


def parse(name):
    m = PATTERN.match(name)
    if not m:
        raise NamingError(name, "does not match {project}_{year}_{deliverable}_{stage}_vNN.{ext}", suggest(name))
    d = m.groupdict()
    stage, ext = d["stage"], d["ext"]
    if stage not in STAGES:
        raise NamingError(name, f"stage {stage!r} is not one of {', '.join(STAGES)}", suggest(name))
    if stage == "final" and ext not in VIDEO_EXT:
        raise NamingError(name, f"a final must be a video, not .{ext}", suggest(name))
    if stage != "final" and ext not in IMAGE_EXT:
        raise NamingError(name, f"{stage} must be an image, not .{ext}", suggest(name))
    d["version"] = int(d["version"])
    d["year"] = int(d["year"])
    d["slug"] = f"{d['project']}-{d['year']}"
    d["media"] = "video" if ext in VIDEO_EXT else "image"
    d["field"] = STAGES[stage]
    d["name"] = name
    d["canonical"] = canonical(d)
    return d


def canonical(d):
    """The name inside the project's assets directory. The project and year
    are the directory, so they drop; hero and poster are singletons."""
    ext = "jpg" if d["ext"] == "jpeg" else d["ext"]
    if d["stage"] in ("hero", "poster"):
        return f"{d['stage']}.{ext}"
    return f"{d['deliverable']}_{d['stage']}_v{d['version']:02d}.{ext}"

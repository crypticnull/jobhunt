"""The curriculum, pointed both ways.

Matt's ask was that the curriculum influence the job search rather than be
derived from it, and both directions run off one vocabulary in
`scoring.json` under `curriculum`.

Forwards, `alignment` names which target areas a posting exercises. That
scores, whether or not he can claim the skill yet, because a job asking for
what he is learning is the job the learning is for. This is the half that
steers the funnel.

Backwards, `gaps` counts the same vocabulary across the postings that already
cleared into a pile, subtracts what `data/skills.json` says he can claim, and
what is left is the study list, ranked by how often the market asks for it.
That is the half that says what to do next.

Nothing here decides anything. Forwards it is five points out of a hundred,
backwards it is a list in the digest.
"""

import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_PATH = ROOT / "data" / "skills.json"


def _pattern(term):
    if re.search(r"[\\^$.|?*+()\[\]{}]", term):
        return re.compile(term, re.IGNORECASE)
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", re.IGNORECASE)


def load_skills(path=None):
    """The terms Matt can claim today. A missing file means an empty claim,
    which makes every vocabulary term a gap rather than crashing the digest."""
    path = Path(path or SKILLS_PATH)
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {s["term"].lower() for s in data.get("skills", [])}


def alignment(text, rules):
    """Which curriculum target areas a posting exercises, in config order."""
    c = rules.get("curriculum") or {}
    vocab = c.get("vocabulary") or {}
    text = (text or "").lower()
    return [area for area in c.get("targets", []) if any(_pattern(t).search(text) for t in vocab.get(area, []))]


def points(areas, rules):
    s = (rules.get("score") or {}).get("curriculum") or {}
    if len(areas) >= 2:
        return s.get("two_or_more_areas", 0)
    if len(areas) == 1:
        return s.get("one_area", 0)
    return 0


def gaps(rows, rules, skills=None):
    """[{term, area, postings, share, median_comp}] for vocabulary terms the
    target postings ask for and Matt cannot claim, most-asked first.

    `rows` are postings that already cleared into a pile, because what a
    dropped posting wants is not a reason to learn anything."""
    c = rules.get("curriculum") or {}
    vocab = c.get("vocabulary") or {}
    floor = c.get("min_postings", 3)
    claimed = load_skills() if skills is None else set(skills)
    total = len(rows)
    if not total:
        return []
    texts = [((r.get("description") or "") + " " + (r.get("title") or "")).lower() for r in rows]
    comps = [r.get("comp_max") or r.get("comp_min") for r in rows]

    out = []
    for area, terms in vocab.items():
        for term in terms:
            if term.lower() in claimed:
                continue
            pat = _pattern(term)
            hits = [i for i, t in enumerate(texts) if pat.search(t)]
            if len(hits) < floor:
                continue
            paid = [comps[i] for i in hits if comps[i]]
            out.append({
                "term": term,
                "area": area,
                "postings": len(hits),
                "share": round(100 * len(hits) / total),
                "median_comp": int(statistics.median(paid)) if paid else None,
            })
    return sorted(out, key=lambda g: (-g["postings"], g["term"]))


def report(rows, rules, skills=None, limit=None):
    """The study list as digest lines. Empty when nothing clears the floor."""
    found = gaps(rows, rules, skills)
    if not found:
        return []
    limit = limit or (rules.get("curriculum") or {}).get("report_top", 12)
    out = ["", "## Curriculum", "",
           f"What the {len(rows)} postings you are looking at ask for and the skills file does not claim, most-asked first. This is the study list, and it is the same vocabulary that steers the search, so learning down this list moves the piles.", ""]
    for g in found[:limit]:
        comp = f", median {g['median_comp'] // 1000}k" if g["median_comp"] else ""
        out.append(f"- {g['term']} ({g['area']}): {g['postings']} of {len(rows)}, {g['share']}%{comp}")
    if len(found) > limit:
        out.append(f"- and {len(found) - limit} more below the top {limit}")
    return out

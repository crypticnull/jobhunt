"""The weekly digest: a markdown file that explains its own reasoning.

Three lanes, strong, borderline, and comp not posted, each entry carrying
the rules that put it there and the id to mark it with. Postings that
carry a terminal status, or were already surfaced and have not changed,
stay out. A footer names any source that errored or returned nothing twice
running, so rot is visible within a week."""

import hashlib
from datetime import datetime, timedelta, timezone

from .score import lane
from .store import TERMINAL, utcnow


def digest_hash(row):
    key = "|".join(str(row.get(k)) for k in ("title", "comp_min", "comp_max", "remote_class")) + f"|{round(row.get('score') or 0)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _week(now):
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def select(store, rules):
    """Open, non-terminal, scored postings not already surfaced unchanged, split by lane."""
    lanes = {"strong": [], "borderline": [], "no_comp": []}
    below = 0
    for row in store.open_postings():
        if row["score"] is None:
            continue
        if store.state_of(row["id"]) in TERMINAL:
            continue
        if row["digested_at"] and row["digest_hash"] == digest_hash(row):
            continue
        which = lane({"score": row["score"]}, rules)
        if which == "below":
            below += 1
            continue
        if not row["comp_found"]:
            lanes["no_comp"].append(row)
        else:
            lanes[which].append(row)
    for k in lanes:
        lanes[k].sort(key=lambda r: (-(r["score"] or 0), r["first_seen"]))
    return lanes, below


def _comp(row):
    if not row["comp_found"]:
        return "comp not posted"
    lo, hi, cur = row["comp_min"], row["comp_max"], row["comp_currency"] or ""
    if lo is not None and hi is not None and lo != hi:
        return f"{cur} {lo:,}-{hi:,}".strip()
    return f"{cur} {(lo if lo is not None else hi):,}".strip()


def _entry(row, company_names):
    import json

    detail = json.loads(row["score_json"] or "{}")
    top = sorted(detail.get("rules", []), key=lambda r: -abs(r["value"]))[:4]
    why = ", ".join(f"{r['rule']} {r['value']:+d} ({r['why']})" for r in top)
    flags = ", ".join(detail.get("flags", []))
    name = company_names.get(row["company_slug"], row["company_slug"])
    lines = [
        f"### {row['title']}, {name}",
        f"{row['remote_class']} · {_comp(row)} · first seen {row['first_seen'][:10]} · score {round(row['score'])}",
        f"Why: {why}" if why else "Why: no rules fired",
    ]
    if flags:
        lines.append(f"Flags: {flags}")
    lines.append(f"{row['url']}  (id {row['id']}, mark with `python -m scraper mark {row['id']} interested`)")
    return "\n".join(lines) + "\n"


def source_health(store, since):
    """Sources that errored since `since`, or returned zero postings on their last two polls."""
    problems = []
    for r in store.poll_errors_since(since):
        problems.append(f"{r['source']}/{r['company_slug']}: {r['error']} ({r['ran_at'][:10]})")
    for slug, source in store.zero_twice_running():
        problems.append(f"{source}/{slug}: zero postings on the last two polls")
    return problems


def build(store, rules, company_names=None, now=None, since=None):
    """Returns (markdown, included_row_ids)."""
    now = now or datetime.now(timezone.utc)
    since = since or (now - timedelta(days=7)).isoformat()
    company_names = company_names or {}
    lanes, below = select(store, rules)
    n = sum(len(v) for v in lanes.values())
    stats = store.stats()
    out = [
        f"# Digest, week {_week(now)}",
        "",
        f"{stats['open']} open postings, {n} surfaced ({len(lanes['strong'])} strong, {len(lanes['borderline'])} borderline, "
        f"{len(lanes['no_comp'])} without comp), {below} below threshold. Ruleset {rules['version']}.",
        "",
    ]
    for title, key in (("Strong", "strong"), ("Borderline", "borderline"), ("Comp not posted", "no_comp")):
        out.append(f"## {title}")
        out.append("")
        if not lanes[key]:
            out.append("Nothing this week.")
            out.append("")
        for row in lanes[key]:
            out.append(_entry(row, company_names))
    out.append("## Source health")
    out.append("")
    problems = source_health(store, since)
    out.extend(f"- {p}" for p in problems) if problems else out.append("All sources answered.")
    out.append("")
    ids = [r["id"] for v in lanes.values() for r in v]
    return "\n".join(out), ids


def write(store, rules, path_dir, company_names=None, now=None):
    """Build, write data/local/digests/<week>.md, and mark the surfaced postings."""
    now = now or datetime.now(timezone.utc)
    md, ids = build(store, rules, company_names, now)
    path_dir.mkdir(parents=True, exist_ok=True)
    path = path_dir / f"{_week(now)}.md"
    path.write_text(md, encoding="utf-8")
    store.mark_digested(ids, utcnow(), digest_hash)
    return path, len(ids)

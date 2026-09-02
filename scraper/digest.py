"""The Monday digest, per the search protocol: new listings by source, the
apply pile sorted by company tier then score and capped for the week, the
review pile with its flag reasons, drop counts by reason, and the source
health footer. Postings past `reviewed`, or already surfaced and unchanged,
stay out. During the collect-only window the piles still print, with a
banner, so the gates can be checked against what they throw away."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from .store import TERMINAL, utcnow


def digest_hash(row):
    key = "|".join(str(row.get(k)) for k in ("title", "comp_min", "comp_max", "remote_class", "pile")) + f"|{round(row.get('score') or 0)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _week(now):
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def _tier(row, companies):
    c = (companies or {}).get(row["company_slug"]) or {}
    return c.get("tier") or 9


def select(store, rules, companies=None, now=None):
    """{"apply": rows, "review": rows, "overflow": rows} plus the ids surfaced.
    Apply is sorted by tier then score and capped at the weekly cap; the rest
    of it becomes overflow and prints under review."""
    piles = {"apply": [], "review": []}
    for row in store.open_postings():
        if row["score"] is None or row.get("pile") in (None, "logged"):
            continue
        if store.state_of(row["id"]) in TERMINAL:
            continue
        if row["digested_at"] and row["digest_hash"] == digest_hash(row):
            continue
        piles[row["pile"]].append(row)
    piles["apply"].sort(key=lambda r: (_tier(r, companies), -(r["score"] or 0), r["first_seen"]))
    piles["review"].sort(key=lambda r: (-(r["score"] or 0), r["first_seen"]))
    cap = rules["piles"]["apply_weekly_cap"]
    piles["overflow"] = piles["apply"][cap:]
    piles["apply"] = piles["apply"][:cap]
    return piles


def _comp(row):
    if not row["comp_found"]:
        return "comp not posted"
    lo, hi, cur = row["comp_min"], row["comp_max"], row["comp_currency"] or ""
    if lo is not None and hi is not None and lo != hi:
        return f"{cur} {lo:,}-{hi:,}".strip()
    return f"{cur} {(lo if lo is not None else hi):,}".strip()


def _entry(row, companies):
    detail = json.loads(row["score_json"] or "{}")
    sc = {r["rule"]: r for r in detail.get("rules", [])}
    parts = [f"{k} {sc[k]['value']:+d}" for k in ("remote", "comp", "intersection", "title", "company", "freshness", "human", "deductions") if k in sc]
    company = (companies or {}).get(row["company_slug"]) or {}
    name = company.get("name", row["company_slug"])
    tier = company.get("tier")
    lines = [
        f"### {row['title']}, {name}" + (f" (tier {tier})" if tier else ""),
        f"{row['remote_class']} · {_comp(row)} · first seen {row['first_seen'][:10]} · score {round(row['score'])}"
        + (f" · legs {', '.join(detail.get('legs_hit') or [])}" if detail.get("legs_hit") else ""),
        "Score: " + ", ".join(parts),
    ]
    if detail.get("flags"):
        lines.append("Flags: " + "; ".join(detail["flags"]))
    if detail.get("proof_lead"):
        lines.append(f"Lead with: {detail['proof_lead']}")
    lines.append(f"{row['url']}  (id {row['id']}, `python -m scraper mark {row['id']} reviewed`)")
    return "\n".join(lines) + "\n"


def source_health(store, since):
    problems = [f"{r['source']}/{r['company_slug']}: {r['error']} ({r['ran_at'][:10]})" for r in store.poll_errors_since(since)]
    problems += [f"{source}/{slug}: zero postings on the last two polls" for slug, source in store.zero_twice_running()]
    return problems


def build(store, rules, companies=None, now=None, since=None):
    """Returns (markdown, surfaced_ids). `companies` is {slug: record}."""
    now = now or datetime.now(timezone.utc)
    since = since or (now - timedelta(days=7)).isoformat()
    piles = select(store, rules, companies, now)
    by_source = store.new_by_source(since)
    drops = store.drop_counts(since)
    stats = store.stats()
    collect_until = rules["tuning"].get("collect_only_until")
    out = [f"# Digest, week {_week(now)}", ""]
    if collect_until and now.date().isoformat() < collect_until:
        out += [f"Collect-only until {collect_until}: nothing is applied to yet. Read the piles to check the gates aren't throwing away obvious fits.", ""]
        rare = [r for r in piles["apply"] + piles["overflow"] if (r["score"] or 0) >= rules["piles"].get("exceptional_min", 999)]
        if rare:
            out += ["**These will not wait for the window to close.** A posting scoring this well is rare, and a job this good is gone in a fortnight.", ""]
            out += [f"- {r['title']}, {((companies or {}).get(r['company_slug']) or {}).get('name', r['company_slug'])}, score {round(r['score'])}, {r['url']}" for r in rare]
            out += [""]
    out += [
        f"{stats['open']} open postings. This week: {sum(by_source.values())} new, {len(piles['apply'])} to apply"
        + (f" (+{len(piles['overflow'])} over the weekly cap of {rules['piles']['apply_weekly_cap']}, pushed to review)" if piles["overflow"] else "")
        + f", {len(piles['review']) + len(piles['overflow'])} to review, {sum(drops.values())} logged. Ruleset {rules['version']}.",
        "",
        "## New listings by source",
        "",
    ]
    out += [f"- {src}: {n}" for src, n in sorted(by_source.items(), key=lambda kv: -kv[1])] or ["- none"]
    new_companies = sorted(
        (c for c in (companies or {}).values() if c.get("category") == "discovered" and c.get("added", "") >= since[:10]),
        key=lambda c: (c["ats"]["kind"] == "manual", c["name"].lower()),
    )
    if new_companies:
        out += ["", "## Companies the feeds found this week", ""]
        out += [f"- {c['name']}: " + (f"{c['ats']['kind']} board, polled from now on" if c["ats"]["kind"] != "manual" else "no board, hand check") for c in new_companies]
    out += ["", "## Apply", ""]
    out += [_entry(r, companies) for r in piles["apply"]] or ["Nothing this week.", ""]
    out += ["## Review", ""]
    review = piles["overflow"] + piles["review"]
    out += [_entry(r, companies) for r in review] or ["Nothing this week.", ""]
    out += ["## Logged, by reason", ""]
    out += [f"- {n:>3}  {reason}" for reason, n in sorted(drops.items(), key=lambda kv: -kv[1])] or ["- none"]
    out += ["", "## Source health", ""]
    problems = source_health(store, since)
    out += [f"- {p}" for p in problems] or ["All sources answered."]
    out.append("")
    ids = [r["id"] for r in piles["apply"] + review]
    return "\n".join(out), ids


def write(store, rules, path_dir, companies=None, now=None):
    now = now or datetime.now(timezone.utc)
    md, ids = build(store, rules, companies, now)
    path_dir.mkdir(parents=True, exist_ok=True)
    path = path_dir / f"{_week(now)}.md"
    path.write_text(md, encoding="utf-8")
    store.mark_digested(ids, utcnow(), digest_hash)
    return path, len(ids)

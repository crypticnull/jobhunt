"""The Monday digest, per the search protocol: new listings by source, the
apply pile sorted by company tier then score and capped for the week, the
review pile with its flag reasons, drop counts by reason, and the source
health footer. Postings past `reviewed`, or already surfaced and unchanged,
stay out. During the collect-only window the piles still print, with a
banner, so the gates can be checked against what they throw away."""

import hashlib
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone

from .maintain import last_run
from .store import TERMINAL, utcnow
from . import curriculum as curriculum_mod


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
    # The review pile is unbounded by nature. Polling ninety companies put six
    # thousand postings in the store, and a digest listing four hundred of them
    # is a digest nobody reads. The rest stay in the store, unsurfaced, and come
    # back next week rather than being marked as seen.
    room = max(rules["piles"].get("review_weekly_cap", 40) - len(piles["overflow"]), 0)
    piles["hidden"] = piles["review"][room:]
    piles["review"] = piles["review"][:room]
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
        f"{row['remote_class']}"
        + (f" · {row['location']}" if row["location"] else "")
        + f" · {_comp(row)}"
        + (f" · HQ {company['hq']}" if company.get("hq") else "")
        + f" · first seen {row['first_seen'][:10]} · score {round(row['score'])}"
        + (f" · legs {', '.join(detail.get('legs_hit') or [])}" if detail.get("legs_hit") else ""),
        "Score: " + ", ".join(parts),
    ]
    if detail.get("flags"):
        lines.append("Flags: " + "; ".join(detail["flags"]))
    if detail.get("curriculum"):
        lines.append("Curriculum: " + ", ".join(detail["curriculum"]))
    if detail.get("proof_lead"):
        lines.append(f"Lead with: {detail['proof_lead']}")
    pay = company.get("pay_model", "unknown")
    if pay == "location-adjusted":
        lines.append("Pay: location-adjusted, so the move north cuts it. Ask on the first call.")
    elif pay == "unknown":
        lines.append("Pay model unknown. Ask whether pay is the same wherever you live.")
    lines.append(f"{row['url']}  (id {row['id']}, `python -m scraper mark {row['id']} reviewed`)")
    return "\n".join(lines) + "\n"


def _short_reason(reason):
    """A drop reason as a few words: the prefix and the first clause."""
    head = (reason or "").split(":")[0].strip()
    rest = (reason or "")[len(head) + 1 :].strip()
    if head in ("remote", "comp", "title", "disqualifier") and rest:
        return f"{head}: {rest.split(',')[0][:40]}"
    return (reason or "")[:48]


def dead_weight(store, rules, companies=None):
    """Companies that have been polled enough to have shown something and have
    shown nothing. Reported, never acted on: the list is Matt's and a scheduled
    job does not get to shorten it."""
    floor = rules.get("digest", {}).get("dead_weight_min_postings", 15)
    rows = [r for r in store.company_yield() if r["on_target"] == 0 and r["postings"] >= floor
            and not ((companies or {}).get(r["company_slug"]) or {}).get("dropped")]
    if not rows:
        return []
    reasons = store.company_drop_reasons()
    out = ["", "## Earning their poll", "",
           f"Polled {floor} or more postings and cleared none of them. The two most common drop reasons print beside each, so a gate miss and a real absence stop reading the same: a design-forward company whose postings all died on the remote claim is worth a look before it is dropped.", ""]
    for r in rows:
        c = (companies or {}).get(r["company_slug"]) or {}
        name = c.get("name", r["company_slug"])
        where = f", {c['hq']}" if c.get("hq") else ""
        why = ", ".join(f"{n} {_short_reason(reason)}" for reason, n in reasons.get(r["company_slug"], [])[:2])
        out.append(f"- {name}{where}: {r['postings']} postings, 0 on target" + (f", {why}" if why else ""))
    out += ["", "Drop the ones you agree with: `python -m scraper drop " + " ".join(r["company_slug"] for r in rows[:5]) + "`"]
    return out


STATUS_LOG = Path(__file__).resolve().parent.parent / "data" / "local" / "nightly-status.log"


def _status_lines(path, now, days=7):
    """The last few lines the scheduled scripts wrote about their own failures,
    when the file is recent. The heartbeat only proves the poll ran; this is
    how a failed push or backup reaches the Sunday page."""
    try:
        p = Path(path)
        if not p.exists():
            return []
        age = now.timestamp() - p.stat().st_mtime
        if age > days * 86400:
            return []
        lines = [ln.strip() for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        return [f"scheduled task: {ln}" for ln in lines[-4:]]
    except OSError:
        return []


def source_health(store, since, status_log=None, now=None):
    counted = {}
    for r in store.poll_errors_since(since):
        key = (r["source"], r["company_slug"], r["error"])
        counted.setdefault(key, []).append(r["ran_at"][:10])
    dead = store.never_answered(since)
    problems = []
    for (source, slug, error), days in counted.items():
        when = f"{len(days)} polls, last {days[0]}" if len(days) > 1 else days[0]
        line = f"{source}/{slug}: {error} ({when})"
        if len(days) > 1 and (source, slug) in dead:
            line += ". It has not answered once this week, so it is on the list without being polled. Check the slug or drop it."
        problems.append(line)
    problems += [f"{source}/{slug}: zero postings on the last two polls" for slug, source in store.zero_twice_running()]
    problems += _status_lines(status_log or STATUS_LOG, now or datetime.now(timezone.utc))
    return problems


def _staleness(now, beat, days=2):
    """A line when the scraper has not run lately. A digest that looks quiet
    because nothing was found and one that looks quiet because the poll stopped
    are the same page otherwise."""
    if not beat or not beat.get("ran_at"):
        return "The scraper has no record of ever running. Check the scheduled task."
    try:
        ran = datetime.fromisoformat(str(beat["ran_at"]).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ran.tzinfo is None:
        ran = ran.replace(tzinfo=timezone.utc)
    late = (now - ran).days
    if late >= days:
        return f"The last poll was {late} days ago, on {str(beat['ran_at'])[:10]}. Nothing below is fresh; check the scheduled task."
    return None


def code_stamp(root=None):
    """The commit this digest was built from. A digest printed from a checkout
    that never pulled reads exactly like a current one, and once the text is
    pasted somewhere there is nothing left to tell them apart. So the page
    carries the tree it came from, the way the site masthead does. Degrades to
    None rather than printing something untrue."""
    root = str(root or Path(__file__).resolve().parent.parent)
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h, committed %cs"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def build(store, rules, companies=None, now=None, since=None, heartbeat=None):
    """Returns (markdown, surfaced_ids). `companies` is {slug: record}."""
    now = now or datetime.now(timezone.utc)
    since = since or (now - timedelta(days=7)).isoformat()
    piles = select(store, rules, companies, now)
    by_source = store.new_by_source(since)
    drops = store.drop_counts(since)
    stats = store.stats()
    collect_until = rules["tuning"].get("collect_only_until")
    stamp = code_stamp()
    out = [f"# Digest, week {_week(now)}", ""]
    stale = _staleness(now, last_run(heartbeat) if heartbeat else None)
    if stale:
        out += [f"**{stale}**", ""]
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
        + f", {len(piles['review']) + len(piles['overflow'])} to review, {sum(drops.values())} logged. Ruleset {rules['version']}."
        + (f" Built from {stamp}." if stamp else ""),
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
    if piles.get("hidden"):
        lowest = round(min(r["score"] or 0 for r in piles["review"])) if piles["review"] else 0
        out += [f"{len(piles['hidden'])} more scored below {lowest} and are held back rather than marked as seen. They return next week if nothing better arrives.", ""]
    out += ["## Logged, by reason", ""]
    out += [f"- {n:>3}  {reason}" for reason, n in sorted(drops.items(), key=lambda kv: -kv[1])] or ["- none"]
    # The same population the nightly writes to data/curriculum.md, so the two
    # study lists never disagree by construction.
    out += curriculum_mod.report(store.study_rows(), rules)
    out += dead_weight(store, rules, companies)
    out += ["", "## Source health", ""]
    problems = source_health(store, since)
    out += [f"- {p}" for p in problems] or ["All sources answered."]
    out.append("")
    ids = [r["id"] for r in piles["apply"] + review]  # held-back rows are deliberately not marked
    return "\n".join(out), ids


def write(store, rules, path_dir, companies=None, now=None, heartbeat=None):
    now = now or datetime.now(timezone.utc)
    md, ids = build(store, rules, companies, now, heartbeat=heartbeat)
    path_dir.mkdir(parents=True, exist_ok=True)
    path = path_dir / f"{_week(now)}.md"
    path.write_text(md, encoding="utf-8")
    store.mark_digested(ids, utcnow(), digest_hash)
    return path, len(ids)

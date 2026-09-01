"""The search protocol as scoring, not gates. Every rule contributes a signed
number and a reason; the digest shows the reasons, so a borderline posting
arrives with the argument for and against it. Nothing is ever dropped."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "data" / "scoring.json"
LOCAL_PATH = ROOT / "data" / "local" / "scoring.local.json"


def load_rules(path=RULES_PATH, local=LOCAL_PATH):
    with open(path, encoding="utf-8") as f:
        rules = json.load(f)
    local = Path(local)
    if local.exists():
        with local.open(encoding="utf-8") as f:
            rules.update(json.load(f))
    return rules


def _pattern(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")


def _hits(terms, text):
    return [t for t in terms if _pattern(t).search(text)]


def _days_since(iso, now):
    if not iso:
        return None
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return max(0, (now - then).days)


def score(p, rules, now=None):
    """p is a posting row (title, description, remote_class, comp_min, comp_max,
    comp_found, posted_at, first_seen). Returns {"score", "rules", "flags", "version"}."""
    now = now or datetime.now(timezone.utc)
    w, t = rules["weights"], rules["terms"]
    title = (p.get("title") or "").lower()
    desc = (p.get("description") or "").lower()
    text = f"{title}\n{desc}"
    out, flags = [], []

    def add(rule, value, why):
        if value:
            out.append({"rule": rule, "value": value, "why": why})

    remote = p.get("remote_class") or "unclear"
    add("remote", w["remote"].get(remote, 0), remote)
    if remote == "remote":
        hedges = _hits(t["remote_hedge"], desc)
        if hedges:
            add("remote_hedge", w["remote_hedge"], ", ".join(hedges[:3]))
            flags.append("remote hedged")

    junior = _hits(t["junior"], title)
    senior = _hits(t["senior"], title)
    if junior:
        add("seniority", w["junior_penalty"], ", ".join(junior))
    elif senior:
        add("seniority", w["senior_bonus"], ", ".join(senior))

    in_title = _hits(t["intersection"], title)
    in_desc = [x for x in _hits(t["intersection"], desc) if x not in in_title]
    raw = w["intersection_term"] * (w["intersection_title_multiplier"] * len(in_title) + len(in_desc))
    add("intersection", min(raw, w["intersection_cap"]), ", ".join(in_title + in_desc)[:120])

    pen = _hits(t["penalty"], text)
    add("penalty", max(w["penalty_term"] * len(pen), w["penalty_cap"]), ", ".join(pen)[:120])

    band = rules.get("comp_band")
    if not band:
        flags.append("no comp band configured")
    elif not p.get("comp_found"):
        add("comp", w["comp"]["absent"], "not posted")
        flags.append("comp not posted")
    else:
        lo = p.get("comp_min") if p.get("comp_min") is not None else p.get("comp_max")
        hi = p.get("comp_max") if p.get("comp_max") is not None else p.get("comp_min")
        if hi < band["min"]:
            add("comp", w["comp"]["below_band"], f"{lo:,}-{hi:,} below band")
        elif lo > band["max"]:
            add("comp", w["comp"]["above_band"], f"{lo:,}-{hi:,} above band")
        elif lo >= band["min"] and hi <= band["max"]:
            add("comp", w["comp"]["in_band"], f"{lo:,}-{hi:,} in band")
        elif lo <= band["max"] and hi >= band["min"]:
            add("comp", w["comp"]["partial_overlap"], f"{lo:,}-{hi:,} overlaps band")

    days = _days_since(p.get("posted_at") or p.get("first_seen"), now)
    if days is not None:
        full = w["freshness_days"]
        if days <= full:
            add("freshness", w["freshness_bonus"], f"{days}d old")
        elif days <= 2 * full:
            add("freshness", round(w["freshness_bonus"] * (2 * full - days) / full), f"{days}d old")

    return {
        "score": sum(r["value"] for r in out),
        "rules": out,
        "flags": flags,
        "version": rules["version"],
    }


def lane(result, rules):
    """strong | borderline | below, from the thresholds alone. Comp absence is a
    flag the digest turns into its own lane, never a reason to drop."""
    th = rules["thresholds"]
    if result["score"] >= th["strong"]:
        return "strong"
    if result["score"] >= th["borderline"]:
        return "borderline"
    return "below"

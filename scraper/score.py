"""The search protocol as code. docs/search-protocol.md is the human twin,
data/scoring.json is the machine twin, this module runs it.

Two hard gates first, remote is real and comp isn't insulting. A listing
that fails either is dropped, and a drop is a row with pile "logged" and a
reason, never a deletion, so the digest can count drops by reason and the
rules can be tuned at the checkpoint. Then disqualifiers, then a 100 point
score, deductions for underpaid tells, and a threshold sort into apply,
review and logged. The scraper never decides to apply. It decides what
Matt looks at."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "data" / "scoring.json"
LOCAL_PATH = ROOT / "data" / "local" / "scoring.local.json"

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


def _deep_merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_rules(path=RULES_PATH, local=LOCAL_PATH):
    with open(path, encoding="utf-8") as f:
        rules = json.load(f)
    local = Path(local)
    if local.exists():
        with local.open(encoding="utf-8") as f:
            _deep_merge(rules, json.load(f))
    return rules


def comp_configured(rules):
    c = rules["gates"]["comp"]
    return c.get("pass_min_annual") is not None and c.get("flag_min_annual") is not None


def _term(term):
    """A term list entry: plain phrases get non-alphanumeric boundaries, anything with regex syntax runs as a regex."""
    if re.search(r"[\\^$.|?*+()\[\]{}]", term):
        return re.compile(term, re.IGNORECASE)
    return re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", re.IGNORECASE)


def _hits(terms, text):
    return [t for t in terms if _term(t).search(text)]


def normalize_title(title):
    t = re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def parse_states(text, rules):
    """A list of two-letter codes, ["US"] for nationwide, or None when the text names no list.
    Two or more codes or state names in one run count as a list; a single mention does not."""
    low = (text or "").lower()
    for token in rules["gates"]["remote"]["nationwide_tokens"]:
        if _term(token).search(low):
            return ["US"]
    found = []
    for m in re.finditer(r"\b((?:[A-Z]{2})(?:\s*[,/&]\s*|\s+and\s+|\s+or\s+)(?:[A-Z]{2}(?:\s*[,/&]\s*|\s+and\s+|\s+or\s+)?)+)\b", text or ""):
        codes = [c for c in re.findall(r"[A-Z]{2}", m.group(1)) if c in US_STATES]
        if len(codes) >= 2:
            found.extend(codes)
    names = [STATE_NAMES[n] for n in STATE_NAMES if re.search(r"\b" + n + r"\b", low)]
    if len(names) >= 2:
        found.extend(names)
    return sorted(set(found)) if found else None


def _days_since(iso, now):
    if not iso:
        return None
    try:
        then = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return max(0, (now - then).days)


def is_pacific(p, states, rules):
    """Pacific hours, or a state list that names one of the states Matt is moving to."""
    r = rules["gates"]["remote"]
    text = (p.get("location") or "") + "\n" + (p.get("description") or "")
    if any(_term(t).search(text.lower()) for t in r.get("pacific_phrases", [])):
        return True
    future = rules.get("candidate", {}).get("future_states", [])
    return bool(states and states != ["US"] and any(s in states for s in future))


def gate_remote(p, rules):
    """(result, reasons, pacific). Pacific is only meaningful on a pass."""
    r = rules["gates"]["remote"]
    claim = p.get("remote_class") or "unclear"
    body = (p.get("description") or "").lower()
    loc = (p.get("location") or "").lower()
    reasons = []
    if claim in r["fail_claims"]:
        return "fail", [f"remote claim is {claim}"], False
    fails = _hits(r["fail_phrases"], body + "\n" + loc)
    if fails:
        return "fail", [f"fake-remote phrase: {', '.join(fails[:3])}"], False
    # A posting whose location names another country and no US marker is not a
    # US remote role, whatever its remote claim says. Checked against the
    # location only, never the body, because a US role can mention EMEA teams.
    abroad = _hits(r.get("fail_location_patterns", []), loc)
    if abroad and not _hits(r["nationwide_tokens"], loc) and not parse_states(loc, rules):
        return "fail", [f"location is outside the US: {', '.join(abroad[:2])}"], False
    states = parse_states((p.get("location") or "") + "\n" + (p.get("description") or ""), rules)
    if states and states != ["US"]:
        if any(s not in states for s in r["fail_if_state_list_excludes"]):
            return "fail", [f"state list excludes {', '.join(r['fail_if_state_list_excludes'])}: {', '.join(states)}"], False
        if all(s not in states for s in r["flag_if_state_list_excludes_all_of"]):
            reasons.append(f"state list has no {' or '.join(r['flag_if_state_list_excludes_all_of'])} yet: {', '.join(states)}")
    nationwide = states == ["US"] or any(_term(t).search(loc) for t in r["nationwide_tokens"])
    if not nationwide:
        tz_ok = any(_term(t).search(body + "\n" + loc) for t in r["ok_timezone_phrases"])
        # A time zone phrase is excused by an ok phrase; a payroll-default shape like "Remote (…)" is excused by a real state list.
        flagged = [
            f for f in _hits(r["flag_phrases"], loc + "\n" + body)
            if not (tz_ok and ("time" in f or "hours" in f)) and not (states and "time" not in f and "hours" not in f)
        ]
        if flagged:
            reasons.append(f"payroll-default or timezone language: {', '.join(flagged[:2])}")
    pacific = is_pacific(p, states, rules)
    if claim in r["require_claim"]:
        result = "flag" if reasons else "pass"
        if result == "pass" and pacific:
            reasons.append("pacific hours")
        return result, reasons, pacific
    if "remote" in body:
        reasons.append("remote in the body but not the location")
        return "flag", reasons, False
    return "fail", ["remote not stated"], False


def gate_comp(p, rules, company):
    c = rules["gates"]["comp"]
    body = (p.get("description") or "").lower()
    fails = _hits(c["fail_phrases"], body)
    if fails:
        return "fail", [f"unpaid work: {fails[0]}"], None
    lo, hi = p.get("comp_min"), p.get("comp_max")
    tier = (company or {}).get("tier")
    size = (company or {}).get("size")
    if lo is None and hi is None:
        if tier in c["unlisted_ok_if_tier_in"]:
            return "pass", [f"unlisted, tier {tier}"], None
        if size and size > c["unlisted_ok_if_size_over"]:
            return "pass", [f"unlisted, size {size}"], None
        return "fail", ["unlisted_salary_unknown_company"], None
    if not comp_configured(rules):
        return "flag", ["comp band not configured, add data/local/scoring.local.json"], None
    hi = hi if hi is not None else lo
    lo = lo if lo is not None else hi
    mid = (lo + hi) / 2
    contract = p.get("employment_type") in ("contract", "freelance")
    if contract and c.get("hourly_floor") and hi < c["hourly_floor"] * c["annualize_hourly_multiplier"]:
        return "fail", [f"contract max {hi:,.0f} is under the hourly floor, annualized, and the floor is firm"], mid
    if hi >= c["pass_min_annual"]:
        return "pass", [f"max {hi:,.0f} clears the floor"], mid
    if hi >= c["flag_min_annual"]:
        note = "worth a look at this tier" if tier in (1, 2) else "soft drop at this tier, review only"
        return "flag", [f"max {hi:,.0f} under the floor, {note}"], mid
    return "fail", [f"max {hi:,.0f} is below the floor"], mid


def disqualify(p, rules, now):
    d = rules["disqualifiers"]["drop"]
    tnorm = normalize_title(p.get("title"))
    for pat in d["title_patterns"]:
        if re.search(pat, tnorm, re.IGNORECASE):
            return f"title: {pat}"
    body = (p.get("description") or "").lower()
    hits = _hits(d["phrases"], body)
    if hits:
        return f"disqualifier: {hits[0]}"
    posted = _days_since(p.get("posted_at"), now)
    seen = _days_since(p.get("last_seen"), now)
    if posted is not None and posted > d["stale_after_days"] and seen is not None and seen > d["stale_unseen_days"]:
        return "stale"
    return None


def legs_hit(p, rules):
    text = f"{p.get('title') or ''}\n{p.get('description') or ''}".lower()
    legs = rules["score"]["intersection"]["legs"]
    return [leg for leg, terms in legs.items() if _hits(terms, text)]


def title_tier(p, legs, rules):
    t = rules["score"]["title"]
    tnorm = normalize_title(p.get("title"))
    if any(_term(pat).search(tnorm) for pat in t["tier_a"]["patterns"]):
        return "A", t["tier_a"]["points"]
    if any(_term(pat).search(tnorm) for pat in t["tier_b"]["patterns"]) and any(l in legs for l in t["tier_b"]["requires_any_leg"]):
        return "B", t["tier_b"]["points"]
    if any(_term(pat).search(tnorm) for pat in t["tier_c"]["patterns"]):
        return "C", t["tier_c"]["points"]
    return None, 0


def evaluate(p, rules, company=None, now=None):
    now = now or datetime.now(timezone.utc)
    company = company or {}
    tier = company.get("tier")
    out = {"version": rules["version"], "flags": [], "deduction_hits": [], "legs_hit": [], "title_tier": None, "proof_lead": rules["proof_lead_by_tier"].get(str(tier), rules["proof_lead_by_tier"]["unknown"])}

    remote_result, remote_reasons, pacific = gate_remote(p, rules)
    out["remote"] = {"result": remote_result, "reasons": remote_reasons, "pacific": pacific}
    comp_result, comp_reasons, mid = gate_comp(p, rules, company)
    out["comp"] = {"result": comp_result, "reasons": comp_reasons, "midpoint": mid}
    out["disqualified"] = disqualify(p, rules, now)

    drop = None
    if remote_result == "fail":
        drop = "remote: " + remote_reasons[0]
    elif comp_result == "fail":
        drop = "comp: " + comp_reasons[0]
    elif out["disqualified"]:
        drop = out["disqualified"]
    if drop:
        out.update({"score": {"total": 0}, "pile": "logged", "drop_reason": drop})
        return out

    if remote_result == "flag":
        out["flags"] += [f"remote: {r}" for r in remote_reasons]
    if comp_result == "flag":
        out["flags"] += [f"comp: {r}" for r in comp_reasons]
    body = (p.get("description") or "").lower()
    flag_rules = rules["disqualifiers"]["flag"]
    engine = _hits(flag_rules["engine"]["phrases"], body)
    if engine:
        out["flags"].append(f"{flag_rules['engine']['reason']}: {', '.join(engine[:3])}")

    s = rules["score"]
    legs = legs_hit(p, rules)
    out["legs_hit"] = legs
    tt, title_points = title_tier(p, legs, rules)
    out["title_tier"] = tt
    fe = flag_rules.get("frontend")
    if fe and tt not in fe.get("skip_if_title_tier_in", []):
        hits = _hits(fe["phrases"], body)
        if hits:
            out["flags"].append(f"{fe['reason']}: {', '.join(hits[:3])}")
    comp_points = 0
    if comp_result == "flag" and mid is not None:
        comp_points = s["comp"]["flagged"]
    elif mid is not None:
        for band in sorted(s["comp"]["bands"], key=lambda b: -b["midpoint_min"]):
            if mid >= band["midpoint_min"]:
                comp_points = band["points"]
                break
    elif tier in rules["gates"]["comp"]["unlisted_ok_if_tier_in"]:
        comp_points = s["comp"]["unlisted_tier_1_3"]
    else:
        comp_points = s["comp"]["unlisted_size_over_200_no_tier"]
    days = _days_since(p.get("posted_at") or p.get("first_seen"), now)
    fresh = 0
    if days is not None:
        for w in sorted(s["freshness"]["within_days"], key=lambda w: w["days"]):
            if days <= w["days"]:
                fresh = w["points"]
                break
    hits = _hits(rules["deductions"]["phrases"], body + "\n" + (p.get("title") or "").lower())
    out["deduction_hits"] = hits
    deductions = min(len(hits) * rules["deductions"]["per_hit"], rules["deductions"]["cap"])
    score = {
        "remote": s["remote"]["flagged"] if remote_result != "pass" else (s["remote"]["pacific"] if pacific else s["remote"]["pass"]),
        "comp": comp_points,
        "intersection": min(len(legs), s["intersection"]["max_legs"]) * s["intersection"]["per_leg"],
        "title": title_points,
        "company": s["company_tier"].get(str(tier), s["company_tier"]["unknown"]),
        "freshness": fresh,
        "human": s["human"]["points_if_contact_hint"] if p.get("contact_hint") else 0,
        "deductions": -deductions,
    }
    score["total"] = sum(score.values())
    out["score"] = score
    piles = rules["piles"]
    if score["total"] >= piles["apply_min"] and not (out["flags"] and piles["flagged_always_review"]):
        out["pile"] = "apply"
    elif score["total"] >= piles["review_min"] or out["flags"]:
        out["pile"] = "review"
    else:
        out["pile"] = "logged"
    out["drop_reason"] = None if out["pile"] != "logged" else "under review threshold"
    return out


def score(p, rules, now=None, company=None):
    """The row-level result the store keeps. `score` is the total (0 when
    dropped), `rules` is the per-component breakdown the brief and digest
    print, and `evaluation` is everything else."""
    ev = evaluate(p, rules, company, now)
    comp_rules = []
    for key, why in (
        ("remote", "; ".join(ev["remote"]["reasons"]) or ev["remote"]["result"]),
        ("comp", "; ".join(ev["comp"]["reasons"]) or ev["comp"]["result"]),
        ("intersection", ", ".join(ev["legs_hit"]) or "no legs"),
        ("title", f"tier {ev['title_tier']}" if ev["title_tier"] else "no title tier"),
        ("company", f"tier {(company or {}).get('tier') or 'unknown'}"),
        ("freshness", "posted recently" if ev["score"].get("freshness") else "older"),
        ("human", "contact named" if p.get("contact_hint") else "no contact"),
        ("deductions", ", ".join(ev["deduction_hits"][:4]) or "none"),
    ):
        value = ev["score"].get(key, 0)
        if value:
            comp_rules.append({"rule": key, "value": value, "why": why})
    return {
        "score": ev["score"]["total"],
        "rules": comp_rules,
        "flags": ev["flags"],
        "version": ev["version"],
        "pile": ev["pile"],
        "drop_reason": ev["drop_reason"],
        "proof_lead": ev["proof_lead"],
        "legs_hit": ev["legs_hit"],
        "title_tier": ev["title_tier"],
        "remote": ev["remote"],
        "comp": ev["comp"],
    }


def lane(result, rules):
    """Backwards-compatible name for the pile."""
    return result.get("pile", "logged")

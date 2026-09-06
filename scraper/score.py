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
from . import curriculum as curriculum_mod
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


_STATE_ANCHOR = re.compile(
    r"\b(?:eligible|located|reside|residing|based|live|living|hire|hiring|open to|candidates|employees|authorized|work)\b[^.]{0,40}?\b(?:in|from|within)\b",
    re.IGNORECASE,
)
_PAY_BOILERPLATE = re.compile(r"pay (?:range|transparency)|salary range|compensation range|base salary|base pay", re.IGNORECASE)


def _state_windows(body):
    """The stretches of a body that can name where a hire may live. Pay
    transparency boilerplate lists California, Colorado, New York and
    Washington on every posting and is not a residency list."""
    out = []
    for m in _STATE_ANCHOR.finditer(body or ""):
        window = body[m.end() : m.end() + 200]
        if not _PAY_BOILERPLATE.search(body[max(0, m.start() - 80) : m.end() + 200]):
            out.append(window)
    return "\n".join(out)


def _state_list(text):
    found = []
    low = (text or "").lower()
    for m in re.finditer(r"\b((?:[A-Z]{2})(?:\s*[,/&]\s*|\s+and\s+|\s+or\s+)(?:[A-Z]{2}(?:\s*[,/&]\s*|\s+and\s+|\s+or\s+)?)+)\b", text or ""):
        codes = [c for c in re.findall(r"[A-Z]{2}", m.group(1)) if c in US_STATES]
        if len(codes) >= 2:
            found.extend(codes)
    names = [STATE_NAMES[n] for n in STATE_NAMES if re.search(r"\b" + n + r"\b", low)]
    if len(names) >= 2:
        found.extend(names)
    return found


# Two-letter codes that are not also ISO country codes. Berlin, DE has to stay
# foreign, but Vancouver, WA has to come back, so the escape below only trusts
# a code that cannot be read as a country.
_UNAMBIGUOUS_CODES = frozenset(
    "AK AZ CT DC FL HI IA KS MI NC ND NH NJ NM NV NY OH OK OR RI TX UT WA WI WV WY".split()
)


def us_state_marker(text):
    """True when a location names a US state at all, by full name or by a code
    that cannot be a country. `_state_list` needs two states before it will
    call something a residency list, which is right for deciding where a role
    lets you live but wrong for deciding whether a city is American. Dublin,
    OH and Vancouver, WA were both being dropped as outside the US, because
    Dublin and Vancouver are on the abroad list and one state code did not
    count for anything."""
    low = (text or "").lower()
    if any(re.search(r"\b" + n + r"\b", low) for n in STATE_NAMES):
        return True
    return any(c in _UNAMBIGUOUS_CODES for c in re.findall(r"\b[A-Z]{2}\b", text or ""))


def parse_states(text, rules, body=""):
    """A list of two-letter codes, ["US"] for nationwide, or None when the text names no list.
    Two or more codes or state names in one run count as a list; a single mention does not.

    `text` is the location and is read whole. `body` is the description and is
    read only where it can name a residency rule: the multiword nationwide
    tokens anywhere, state lists only inside a window after a residency anchor.
    Before 2026-09-05 the whole body was read and the bare token "us" matched
    "join us", so every posting was nationwide and the state-list and time zone
    rules only ever fired on bodies that never said "us"."""
    low = (text or "").lower()
    tokens = rules["gates"]["remote"]["nationwide_tokens"]
    for token in tokens:
        if _term(token).search(low):
            return ["US"]
    body_low = (body or "").lower()
    if body_low:
        for token in tokens:
            if " " in token or "-" in token:  # multiword tokens carry their own context
                if _term(token).search(body_low):
                    return ["US"]
    found = _state_list(text or "")
    if body:
        found.extend(_state_list(_state_windows(body)))
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
    def american(text, low):
        return bool(_hits(r["nationwide_tokens"], low)) or bool(parse_states(low, rules)) or us_state_marker(text)

    abroad = _hits(r.get("fail_location_patterns", []), loc)
    if abroad and not american(p.get("location") or "", loc):
        return "fail", [f"location is outside the US: {', '.join(abroad[:2])}"], False
    # A region in the title scopes the role itself, which is not the same as a
    # region in the body, where a US posting can name the EMEA team it works
    # with. "Deal Strategy Analyst - EMEA" and "Forward Deployed Creative
    # [KSA]" both came through on a blank location and sat in the review pile
    # for a week. Same two escapes as the location, so "Designer, US & Canada"
    # and a title naming a US city in a state still pass.
    title = (p.get("title") or "").lower()
    scoped = _hits(r.get("fail_location_patterns", []), title)
    if scoped and not american(p.get("title") or "", title):
        return "fail", [f"title is scoped to {', '.join(scoped[:2])}"], False
    states = parse_states(p.get("location") or "", rules, body=p.get("description") or "")
    if states and states != ["US"]:
        if any(s not in states for s in r["fail_if_state_list_excludes"]):
            return "fail", [f"state list excludes {', '.join(r['fail_if_state_list_excludes'])}: {', '.join(states)}"], False
        if all(s not in states for s in r["flag_if_state_list_excludes_all_of"]):
            reasons.append(f"state list has no {' or '.join(r['flag_if_state_list_excludes_all_of'])} yet: {', '.join(states)}")
    nationwide = states == ["US"] or any(_term(t).search(loc) for t in r["nationwide_tokens"])
    tz_ok = any(_term(t).search(body + "\n" + loc) for t in r["ok_timezone_phrases"])
    # A time zone phrase is excused by an ok phrase and flags even on a
    # nationwide posting, since Eastern-only on "Remote - US" is still a
    # constraint. A payroll-default shape like "Remote (…)" is excused by a
    # real state list or a nationwide location.
    tz_flags, shape_flags = [], []
    for f in _hits(r["flag_phrases"], loc + "\n" + body):
        is_tz = "time" in f or "hours" in f
        if is_tz and not tz_ok:
            tz_flags.append(f)
        elif not is_tz and not nationwide and not states:
            shape_flags.append(f)
    if shape_flags:
        reasons.append(f"payroll-default language: {', '.join(shape_flags[:2])}")
    if tz_flags:
        reasons.append(f"timezone language: {', '.join(tz_flags[:2])}")
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
    needs = t["tier_a"].get("requires_any_leg_for") or {}
    for pat in t["tier_a"]["patterns"]:
        if _term(pat).search(tnorm):
            if pat in needs.get("patterns", []) and not any(l in legs for l in needs.get("legs", [])):
                break  # a Technical Director with no software, pipeline or generative leg is a film TD
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

    s = rules["score"]
    legs = legs_hit(p, rules)
    out["legs_hit"] = legs
    tt, title_points = title_tier(p, legs, rules)
    out["title_tier"] = tt
    # The curriculum points forward. A posting asking for what Matt is
    # learning scores for it whether or not he can claim the skill yet,
    # because that is the job the learning is for.
    aligned = curriculum_mod.alignment(f"{p.get('title') or ''}\n{p.get('description') or ''}", rules)
    out["curriculum"] = aligned
    curriculum_points = curriculum_mod.points(aligned, rules)
    # Engine and frontend language flag rather than drop, and neither holds a
    # title that has already earned a tier: every design engineering posting
    # names React, and the engine words that are left are the real engines.
    for key in ("engine", "frontend"):
        fr = flag_rules.get(key)
        if fr and tt not in fr.get("skip_if_title_tier_in", []):
            hits = _hits(fr["phrases"], body)
            if hits:
                out["flags"].append(f"{fr['reason']}: {', '.join(hits[:3])}")
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
        "curriculum": curriculum_points,
        "freshness": fresh,
        "human": s["human"]["points_if_contact_hint"] if p.get("contact_hint") else 0,
        "deductions": -deductions,
    }
    score["total"] = sum(score.values())
    out["score"] = score
    piles = rules["piles"]
    # Relevance floor. Remote 22 plus comp 20 plus a tier 1 company plus
    # freshness is 57, over the review threshold, on a posting with no title
    # fit and no intersection leg at all. That is how a Backend Engineer at a
    # good company reaches the review pile, and with a cap of 40 a week it is
    # how the pile fills with work Matt would never take. A posting has to be
    # about something he does before comp and prestige can carry it.
    craft = piles.get("relevance_legs") or []
    leg_hit = any(l in craft for l in legs) if craft else bool(legs)
    # And the leg has to be corroborated by the title. At an AI company the
    # About Us block says generative and product in every posting, so the legs
    # fire on an Economist and a Revenue Accounting Manager the same as on a
    # designer. A tiered title still passes on its own; this governs the
    # rescue only, and the two halves get separate drop reasons so the digest
    # shows which one is doing the work.
    craft_titles = piles.get("relevance_title_terms") or []
    title_craft = not craft_titles or bool(_hits(craft_titles, normalize_title(p.get("title"))))
    relevant = out["title_tier"] is not None or (leg_hit and title_craft)
    if not relevant:
        out["pile"] = "logged"
        out["drop_reason"] = "no title fit and no intersection" if not leg_hit else "intersection but the title names no craft"
        return out
    # The apply pile is what the letter generator reads. A posting whose title
    # does not fit is not one Matt can write a credible letter for, whatever the
    # body scores, and it is how an Economist and a PCB Layout Engineer reached
    # apply on generic body language. They still reach review.
    apply_tiers = piles.get("apply_title_tiers", ["A", "B", "C"])
    titled = out["title_tier"] in apply_tiers or not piles.get("apply_requires_title_tier")
    # A flag holds a posting in review so Matt decides, except where the title is
    # tier A. Creative Technologist at Luma is the stated bullseye and it scored
    # 70 and sat in review because the body mentions Unity. The flag still prints
    # on the row, so he still decides, but a tier A title reaches the pile the
    # letter generator reads.
    override = out["title_tier"] in (piles.get("flag_override_title_tiers") or [])
    # A soft flag halves the remote marks and prints on the row but does not
    # hold a tiered title in review. Payroll-default shapes like "Remote - New
    # York" are soft: once the "us" bug was fixed they fire on real matches,
    # and the point of fixing the gate was to surface those, not to move them
    # from apply to review.
    soft = piles.get("soft_flag_prefixes") or []
    hard_flags = [f for f in out["flags"] if not (out["title_tier"] and any(f.startswith(x) for x in soft))]
    held = bool(hard_flags) and piles["flagged_always_review"] and not override
    if titled and score["total"] >= piles["apply_min"] and not held:
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
        ("curriculum", ", ".join(ev.get("curriculum") or []) or "no curriculum area"),
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
        "curriculum": ev.get("curriculum") or [],
        "title_tier": ev["title_tier"],
        "remote": ev["remote"],
        "comp": ev["comp"],
    }


def lane(result, rules):
    """Backwards-compatible name for the pile."""
    return result.get("pile", "logged")

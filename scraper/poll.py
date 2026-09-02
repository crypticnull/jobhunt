"""One poll: every pollable company on the list, each isolated, each logged,
every posting enriched and scored on the way in."""

import re
from datetime import datetime

from . import http, salary
from .adapters import ADAPTERS
from .score import load_rules, score
from .store import fingerprint, utcnow


_CONTRACT = re.compile(r"\b(contract|contractor|contract-to-hire|freelance|freelancer|1099|hourly)\b", re.IGNORECASE)
_PART_TIME = re.compile(r"\bpart[- ]time\b", re.IGNORECASE)


def employment_type_of(title, text):
    """contract, part-time, or None when nothing says otherwise. The word
    'contract' in a title is decisive; in the body it only counts when the
    posting isn't plainly full-time."""
    title, text = title or "", text or ""
    if _CONTRACT.search(title):
        return "contract"
    if _PART_TIME.search(title + "\n" + text):
        return "part-time"
    if _CONTRACT.search(text) and not re.search(r"\bfull[- ]time\b", text, re.IGNORECASE):
        return "contract"
    return None


def enrich(p):
    """Fill comp from the description when the ATS gave none, and work out
    the employment type, because the hourly floor only applies to contract
    and freelance work and an hourly rate is contract pay by definition."""
    hourly = False
    if p.get("comp_min") is None and p.get("comp_max") is None:
        found = salary.extract(p.get("description"))
        if found:
            p["comp_min"], p["comp_max"], p["comp_currency"], note = found
            hourly = bool(note)
            p["comp_note"] = "from text" + (", hourly annualized" if note else "")
    if not p.get("employment_type"):
        p["employment_type"] = "contract" if hourly else employment_type_of(p.get("title"), p.get("description"))
    return p


def poll(store, companies, get_json=None, now=None, rules=None):
    """`companies` are the list records; each posting is scored against its own company's tier and size."""
    get_json = get_json or http.get_json
    now = now or utcnow()
    rules = rules or load_rules()
    score_now = datetime.fromisoformat(now)
    results = []
    listed = {c["slug"] for c in companies}
    store.close_unlisted(listed, now)
    for c in companies:
        slug, kind, board = c["slug"], c["ats"]["kind"], c["ats"]["board"]
        mod = ADAPTERS.get(kind)
        if mod is None or not board:
            results.append({"slug": slug, "kind": kind, "ok": None, "seen": 0, "new": 0, "closed": 0, "error": "no adapter"})
            continue
        try:
            payload = mod.fetch(board, get_json) if hasattr(mod, "fetch") else get_json(mod.endpoint(board))
            seen, new = [], 0
            for p in mod.parse(payload):
                p["company_slug"] = slug
                enrich(p)
                pid, is_new = store.upsert(p, now)
                store.set_score(pid, score(store.get(pid), rules, score_now, company=c))
                seen.append(fingerprint(p))
                new += int(is_new)
            closed = store.close_missing(slug, kind, seen, now)
            store.log_poll(now, kind, slug, True, len(seen), new)
            results.append({"slug": slug, "kind": kind, "ok": True, "seen": len(seen), "new": new, "closed": closed, "error": None})
        except Exception as e:  # one bad company must never end the nightly run
            err = f"{type(e).__name__}: {e}"
            store.log_poll(now, kind, slug, False, error=err)
            results.append({"slug": slug, "kind": kind, "ok": False, "seen": 0, "new": 0, "closed": 0, "error": err})
    return results

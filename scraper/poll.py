"""One poll: every pollable company on the list, each isolated, each logged,
every posting enriched and scored on the way in."""

from datetime import datetime

from . import http, salary
from .adapters import ADAPTERS
from .score import load_rules, score
from .store import fingerprint, utcnow


def enrich(p):
    """Fill comp from the description when the ATS gave none."""
    if p.get("comp_min") is None and p.get("comp_max") is None:
        found = salary.extract(p.get("description"))
        if found:
            p["comp_min"], p["comp_max"], p["comp_currency"], note = found
            p["comp_note"] = "from text" + (", hourly annualized" if note else "")
    return p


def poll(store, companies, get_json=None, now=None, rules=None):
    get_json = get_json or http.get_json
    now = now or utcnow()
    rules = rules or load_rules()
    score_now = datetime.fromisoformat(now)
    results = []
    for c in companies:
        slug, kind, board = c["slug"], c["ats"]["kind"], c["ats"]["board"]
        mod = ADAPTERS.get(kind)
        if mod is None or not board:
            results.append({"slug": slug, "kind": kind, "ok": None, "seen": 0, "new": 0, "closed": 0, "error": "no adapter"})
            continue
        try:
            payload = get_json(mod.endpoint(board))
            seen, new = [], 0
            for p in mod.parse(payload):
                p["company_slug"] = slug
                enrich(p)
                pid, is_new = store.upsert(p, now)
                store.set_score(pid, score(store.get(pid), rules, score_now))
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

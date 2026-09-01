"""One poll: every pollable company on the list, each isolated, each logged."""

from . import http
from .adapters import ADAPTERS
from .store import fingerprint, utcnow


def poll(store, companies, get_json=None, now=None):
    get_json = get_json or http.get_json
    now = now or utcnow()
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
                _, is_new = store.upsert(p, now)
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

"""The target company list: load, save, add, check, stale.

The list is public, data/companies.json, so it can be read and edited from
anywhere and the nightly discovery step can push what it adds. Contacts and
notes are the private half and live in data/local/companies.notes.json,
keyed by slug, merged in on load and split out on save. The committed
data/companies.example.json has the same shape and powers tests and the demo."""

import json
import re
from datetime import date, datetime
from pathlib import Path

from . import adapters

CATEGORIES = ("ai-video", "studio-ai", "product-inhouse", "brand-inhouse", "discovered")
# The protocol's company tiers map onto the four categories one to one.
TIER_BY_CATEGORY = {"ai-video": 1, "studio-ai": 2, "product-inhouse": 3, "brand-inhouse": 4, "discovered": None}
KINDS = ("greenhouse", "lever", "ashby", "workable", "smartrecruiters", "recruitee", "rss", "manual")
VERSION = 1


PRIVATE_FIELDS = ("contacts", "notes")


def empty():
    return {"version": VERSION, "companies": []}


def notes_path(path):
    """The private sidecar for a list: data/companies.json pairs with data/local/companies.notes.json."""
    return Path(path).parent / "local" / "companies.notes.json"


def load(path, notes=None):
    path = Path(path)
    if not path.exists():
        return empty()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if data.get("version") != VERSION:
        raise ValueError(f"{path}: unsupported companies file version {data.get('version')!r}")
    notes = Path(notes) if notes else notes_path(path)
    private = {}
    if notes.exists():
        with notes.open(encoding="utf-8") as f:
            private = json.load(f)
    for c in data["companies"]:
        c.setdefault("contacts", [])
        c.setdefault("notes", "")
        c.update({k: v for k, v in private.get(c["slug"], {}).items() if k in PRIVATE_FIELDS})
    return data


def save(path, data, notes=None):
    """The public file never carries contacts or notes; those go to the sidecar,
    which is only written when there is something private to keep."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["companies"].sort(key=lambda c: (c.get("priority", 9), c["slug"]))
    public = {"version": data["version"], "companies": [{k: v for k, v in c.items() if k not in PRIVATE_FIELDS} for c in data["companies"]]}
    with path.open("w", encoding="utf-8") as f:
        json.dump(public, f, indent=2, ensure_ascii=False)
        f.write("\n")
    private = {c["slug"]: {k: c[k] for k in PRIVATE_FIELDS if c.get(k)} for c in data["companies"] if any(c.get(k) for k in PRIVATE_FIELDS)}
    notes = Path(notes) if notes else notes_path(path)
    if private or notes.exists():
        notes.parent.mkdir(parents=True, exist_ok=True)
        with notes.open("w", encoding="utf-8") as f:
            json.dump(private, f, indent=2, ensure_ascii=False)
            f.write("\n")


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "company"


def record(slug, name, kind, board, category, priority=2, careers_url=None, lead_proof=None, today=None, tier=None, size=None):
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {CATEGORIES}, got {category!r}")
    if kind not in KINDS:
        raise ValueError(f"ats kind must be one of {KINDS}, got {kind!r}")
    today = today or date.today().isoformat()
    return {
        "slug": slug,
        "name": name,
        "careers_url": careers_url,
        "ats": {"kind": kind, "board": board},
        "category": category,
        "tier": int(tier) if tier else TIER_BY_CATEGORY[category],
        "size": int(size) if size else None,
        "priority": int(priority),
        "lead_proof": lead_proof,
        # Asked on the first call. Location-adjusted pay is what decides whether
        # the move north costs money, so it is a field rather than a note.
        "pay_model": "unknown",
        "remote_notes": "",
        "contacts": [],
        "notes": "",
        "added": today,
        "last_reviewed": today,
    }


def add(data, rec):
    if any(c["slug"] == rec["slug"] for c in data["companies"]):
        raise ValueError(f"{rec['slug']} is already on the list")
    data["companies"].append(rec)
    return rec


def check(data, probe=None):
    """Probe every pollable company's endpoint. Returns one result dict per company."""
    probe = probe or adapters.probe
    out = []
    for c in data["companies"]:
        kind, board = c["ats"]["kind"], c["ats"]["board"]
        if kind not in adapters.PROBE_ENDPOINTS:
            out.append({"slug": c["slug"], "kind": kind, "ok": None, "count": 0, "error": "not pollable"})
            continue
        ok, count, err = probe(kind, board)
        out.append({"slug": c["slug"], "kind": kind, "ok": ok, "count": count, "error": err})
    return out


def stale(data, days, today=None):
    today = datetime.fromisoformat(today).date() if today else date.today()
    out = []
    for c in data["companies"]:
        reviewed = datetime.fromisoformat(c["last_reviewed"]).date()
        age = (today - reviewed).days
        if age >= days:
            out.append((c["slug"], age))
    return sorted(out, key=lambda t: -t[1])

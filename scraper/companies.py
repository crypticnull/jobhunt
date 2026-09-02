"""The target company list: load, save, add, check, stale.

The real list lives in data/local/companies.json and never touches git. The
committed data/companies.example.json has the same shape and powers tests."""

import json
import re
from datetime import date, datetime
from pathlib import Path

from . import adapters

CATEGORIES = ("ai-video", "studio-ai", "product-inhouse", "brand-inhouse")
# The protocol's company tiers map onto the four categories one to one.
TIER_BY_CATEGORY = {"ai-video": 1, "studio-ai": 2, "product-inhouse": 3, "brand-inhouse": 4}
KINDS = ("greenhouse", "lever", "ashby", "workable", "smartrecruiters", "recruitee", "rss", "manual")
VERSION = 1


def empty():
    return {"version": VERSION, "companies": []}


def load(path):
    path = Path(path)
    if not path.exists():
        return empty()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if data.get("version") != VERSION:
        raise ValueError(f"{path}: unsupported companies file version {data.get('version')!r}")
    return data


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["companies"].sort(key=lambda c: (c.get("priority", 9), c["slug"]))
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
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

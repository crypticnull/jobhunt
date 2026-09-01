"""Rot watch and disaster insurance: nightly backups off the disk, a monthly
export of the status history, and fixture refresh when an endpoint drifts."""

import json
import sqlite3
from datetime import date
from pathlib import Path

from . import http
from .adapters import ADAPTERS


def backup(db_path, dest_dir, keep=14, today=None):
    """Consistent copy via the SQLite backup API. Keeps the newest `keep`."""
    today = today or date.today().isoformat()
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"postings-{today}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    olds = sorted(dest_dir.glob("postings-*.db"))
    for old in olds[:-keep] if keep else []:
        old.unlink()
    return target


def export_status(db_path, dest_dir, month=None):
    """status_log joined to its postings, as JSON, one file per month. The
    nine months of history that must not die with one disk."""
    month = month or date.today().strftime("%Y-%m")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT s.id, s.posting_id, s.state, s.noted_at, s.letter_path, s.note, p.company_slug, p.title, p.url, p.source "
        "FROM status_log s JOIN postings p ON p.id = s.posting_id ORDER BY s.id"
    ).fetchall()
    db.close()
    target = dest_dir / f"status-{month}.json"
    target.write_text(json.dumps([dict(r) for r in rows], indent=2), encoding="utf-8")
    return target, len(rows)


def fixture(kind, board, out_dir, get_json=None, get_text=None, keep=2):
    """Fetch a live payload and write a trimmed copy as the adapter's test
    fixture. Run this when an endpoint's shape drifts; the diff documents it."""
    mod = ADAPTERS.get(kind)
    if mod is None:
        raise KeyError(f"no adapter for {kind!r}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if kind == "rss":
        text = (get_text or http.get_text)(board)
        target = out_dir / "careers.rss"
        target.write_text(text, encoding="utf-8")
        return target
    get_json = get_json or http.get_json
    payload = mod.fetch(board, get_json) if hasattr(mod, "fetch") else get_json(mod.endpoint(board))
    if isinstance(payload, list):
        payload = payload[:keep]
    else:
        for key in ("jobs", "content", "offers", "results"):
            if isinstance(payload.get(key), list):
                payload[key] = payload[key][:keep]
    target = out_dir / f"{kind}.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target

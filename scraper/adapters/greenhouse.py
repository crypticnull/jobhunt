"""Greenhouse Job Board API. Keyless. content=true adds the description,
pay_transparency=true adds pay_input_ranges where the company publishes them.
Remote is a text heuristic on location.name; Greenhouse has no structured
workplace field."""

from ..posting import posting
from ._text import classify_remote, html_to_text

KIND = "greenhouse"


def endpoint(board):
    return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true&pay_transparency=true"


def _pay_range(ranges):
    lo = hi = cur = None
    for r in ranges or []:
        mn, mx = r.get("min_cents"), r.get("max_cents")
        if mn is not None:
            lo = mn // 100 if lo is None else min(lo, mn // 100)
        if mx is not None:
            hi = mx // 100 if hi is None else max(hi, mx // 100)
        cur = cur or r.get("currency_type")
    return lo, hi, cur


def parse(payload):
    for j in payload.get("jobs", []):
        loc = (j.get("location") or {}).get("name") or ""
        lo, hi, cur = _pay_range(j.get("pay_input_ranges"))
        yield posting(
            source=KIND,
            source_id=j.get("id"),
            title=j.get("title"),
            url=j.get("absolute_url"),
            location=loc,
            remote=classify_remote(loc),
            comp_min=lo,
            comp_max=hi,
            comp_currency=cur,
            description=html_to_text(j.get("content")),
            posted_at=j.get("first_published") or j.get("updated_at"),
        )

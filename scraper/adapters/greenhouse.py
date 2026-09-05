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
    """The range a remote worker would actually be paid. Greenhouse publishes one
    range per office, top tier first, and the old min-of-mins, max-of-maxes merge
    gated a location-adjusted employer on its San Francisco number. Now the range
    with the lowest maximum wins, which is the all-other-US tier when one exists
    and the only tier when not. A tier with a dropped zero is ignored rather than
    dragging the minimum down, which is where Instacart's 20,300 came from."""
    best = None
    for r in ranges or []:
        mn, mx = r.get("min_cents"), r.get("max_cents")
        if mx is None:
            continue
        hi = mx // 100
        lo = mn // 100 if mn is not None else None
        if lo is not None and hi >= 20000 and lo < hi // 5:
            lo = None  # a minimum under a fifth of the maximum is a typo, not a floor
        if best is None or hi < best[1]:
            best = (lo, hi, r.get("currency_type"))
    return best or (None, None, None)


def _remote_class(j):
    """The location decides, and the offices array, which Greenhouse ships on
    every job and the adapter used to ignore, can only make a city location
    unclear or a country location remote. An office called Remote beside a
    city means the body has to say which; it never makes a city remote on its
    own, because that is the margin the first principle protects."""
    loc = (j.get("location") or {}).get("name") or ""
    offices = [(o.get("name") or "") for o in j.get("offices") or [] if isinstance(o, dict)]
    cls = classify_remote(loc)
    office_remote = any(classify_remote(o) == "remote" for o in offices)
    if office_remote and cls == "unclear":
        return loc, "remote"
    if office_remote and cls == "onsite":
        return loc, "unclear"
    return loc, cls


def parse(payload):
    for j in payload.get("jobs", []):
        loc, remote = _remote_class(j)
        lo, hi, cur = _pay_range(j.get("pay_input_ranges"))
        yield posting(
            source=KIND,
            source_id=j.get("id"),
            title=j.get("title"),
            url=j.get("absolute_url"),
            location=loc,
            remote=remote,
            comp_min=lo,
            comp_max=hi,
            comp_currency=cur,
            description=html_to_text(j.get("content")),
            posted_at=j.get("first_published") or j.get("updated_at"),
        )

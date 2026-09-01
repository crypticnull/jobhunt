"""Recruitee careers API. Keyless, one call per company, description and
requirements inline, structured remote and hybrid flags, salary where the
company shows it."""

from ..posting import posting
from ._text import classify_remote, html_to_text

KIND = "recruitee"


def endpoint(company):
    return f"https://{company}.recruitee.com/api/offers/"


def _remote(j, loc):
    if j.get("remote"):
        return "remote"
    if j.get("hybrid"):
        return "hybrid"
    if j.get("on_site"):
        return "onsite"
    return classify_remote(loc)


def _salary(j):
    s = j.get("salary") or {}
    if not isinstance(s, dict) or s.get("min") is None and s.get("max") is None:
        return None, None, None
    return s.get("min"), s.get("max"), s.get("currency")


def parse(payload):
    for j in payload.get("offers", []):
        loc = j.get("location") or ", ".join(p for p in (j.get("city"), j.get("country")) if p)
        lo, hi, cur = _salary(j)
        desc = "\n\n".join(html_to_text(j.get(k)) for k in ("description", "requirements") if j.get(k))
        yield posting(
            source=KIND,
            source_id=j.get("id"),
            title=j.get("title"),
            url=j.get("careers_url"),
            location=loc,
            remote=_remote(j, loc),
            comp_min=lo,
            comp_max=hi,
            comp_currency=cur,
            description=desc,
            posted_at=j.get("published_at") or j.get("created_at"),
        )

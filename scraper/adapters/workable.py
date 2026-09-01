"""Workable widget API. Unofficial and it has churned before, so this adapter
ships last and is the likeliest to need a fixture refresh. details=true adds
the description. Remote comes from the telecommuting or remote flag, or the
workplace field on newer accounts."""

from ..posting import posting
from ._text import classify_remote, html_to_text

KIND = "workable"


def endpoint(account):
    return f"https://apply.workable.com/api/v1/widget/accounts/{account}?details=true"


def _location(j):
    parts = [j.get("city"), j.get("state") or j.get("region"), j.get("country")]
    return ", ".join(p for p in parts if p)


def _remote(j, loc):
    wp = (j.get("workplace") or "").lower()
    if wp in ("remote", "hybrid"):
        return wp
    if j.get("telecommuting") or j.get("remote"):
        return "remote"
    return classify_remote(loc, wp or None)


def parse(payload):
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if jobs is None and isinstance(payload, dict):
        jobs = payload.get("results", [])
    for j in jobs or []:
        loc = _location(j)
        desc = "\n\n".join(html_to_text(j.get(k)) for k in ("description", "requirements", "benefits") if j.get(k))
        yield posting(
            source=KIND,
            source_id=j.get("shortcode") or j.get("id"),
            title=j.get("title"),
            url=j.get("url") or j.get("shortlink") or j.get("application_url"),
            location=loc,
            remote=_remote(j, loc),
            description=desc,
            posted_at=j.get("published_on") or j.get("created_at"),
        )

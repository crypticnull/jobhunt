"""Lever Postings API. Keyless, returns a list. workplaceType is structured
(remote, hybrid, onsite, unspecified) and salaryRange is present when the
company fills it in."""

from datetime import datetime, timezone

from ..posting import posting
from ._text import classify_remote

KIND = "lever"


def endpoint(site):
    return f"https://api.lever.co/v0/postings/{site}?mode=json"


def _iso(ms):
    if isinstance(ms, (int, float)):
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
    return None


def parse(payload):
    for j in payload if isinstance(payload, list) else []:
        cats = j.get("categories") or {}
        loc = cats.get("location") or ", ".join(cats.get("allLocations") or [])
        sr = j.get("salaryRange") or {}
        desc = "\n\n".join(x for x in (j.get("descriptionPlain"), j.get("additionalPlain")) if x)
        yield posting(
            source=KIND,
            source_id=j.get("id"),
            title=j.get("text"),
            url=j.get("hostedUrl"),
            location=loc,
            remote=classify_remote(loc, j.get("workplaceType")),
            comp_min=sr.get("min"),
            comp_max=sr.get("max"),
            comp_currency=sr.get("currency"),
            description=desc,
            posted_at=_iso(j.get("createdAt")),
        )

"""Ashby Job Posting API. Keyless. isRemote and workplaceType are structured,
and includeCompensation=true adds tiers with typed components plus a text
summary, the cleanest comp data of the group."""

import re

from ..posting import posting
from ._text import classify_remote, html_to_text

KIND = "ashby"

_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*([kK])?")


def endpoint(name):
    return f"https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true"


def _summary_range(text):
    amounts = []
    for m in _MONEY.finditer(text or ""):
        n = float(m.group(1).replace(",", ""))
        if m.group(2):
            n *= 1000
        amounts.append(int(n))
    return (min(amounts), max(amounts)) if amounts else (None, None)


def _comp(c):
    if not c:
        return None, None, None
    for tier in c.get("compensationTiers") or []:
        for comp in tier.get("components") or []:
            if (comp.get("compensationType") or "").lower() == "salary":
                return comp.get("minValue"), comp.get("maxValue"), comp.get("currencyCode")
    lo, hi = _summary_range(c.get("scrapeableCompensationSalarySummary") or c.get("compensationTierSummary"))
    return lo, hi, ("USD" if lo is not None else None)


def parse(payload):
    for j in payload.get("jobs", []):
        loc = j.get("location") or ""
        remote = "remote" if j.get("isRemote") else classify_remote(loc, j.get("workplaceType"))
        lo, hi, cur = _comp(j.get("compensation"))
        yield posting(
            source=KIND,
            source_id=j.get("id"),
            title=j.get("title"),
            url=j.get("jobUrl"),
            location=loc,
            remote=remote,
            comp_min=lo,
            comp_max=hi,
            comp_currency=cur,
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            posted_at=j.get("publishedAt"),
        )

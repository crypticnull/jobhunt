"""SmartRecruiters Posting API. Keyless. The list carries a structured remote
flag but no description, so fetch() follows each posting's ref for the job
ad sections, capped so a large board cannot turn one poll into hundreds of
calls. A detail that fails leaves the description empty rather than failing
the company."""

from .. import http
from ..posting import posting
from ._text import classify_remote, html_to_text

KIND = "smartrecruiters"
DETAIL_CAP = 60


def endpoint(company):
    return f"https://api.smartrecruiters.com/v1/companies/{company}/postings?limit=100"


def _description(detail):
    sections = ((detail or {}).get("jobAd") or {}).get("sections") or {}
    parts = []
    for key in ("jobDescription", "qualifications", "additionalInformation", "companyDescription"):
        text = (sections.get(key) or {}).get("text")
        if text:
            parts.append(html_to_text(text))
    return "\n\n".join(parts)


def fetch(company, get_json=None):
    """List plus per-posting details, merged so parse() sees one payload."""
    get_json = get_json or http.get_json
    payload = get_json(endpoint(company))
    for j in (payload.get("content") or [])[:DETAIL_CAP]:
        ref = j.get("ref")
        if not ref:
            continue
        try:
            j["_detail"] = get_json(ref)
        except http.HttpError:
            j["_detail"] = None
    return payload


def parse(payload):
    company = ((payload.get("content") or [{}])[0].get("company") or {}).get("identifier")
    for j in payload.get("content", []):
        loc_obj = j.get("location") or {}
        loc = loc_obj.get("fullLocation") or ", ".join(p for p in (loc_obj.get("city"), loc_obj.get("region"), loc_obj.get("country")) if p)
        remote = "remote" if loc_obj.get("remote") else classify_remote(loc)
        detail = j.get("_detail")
        url = (detail or {}).get("applyUrl") or f"https://jobs.smartrecruiters.com/{company or 'company'}/{j.get('id')}"
        yield posting(
            source=KIND,
            source_id=j.get("id"),
            title=j.get("name"),
            url=url,
            location=loc,
            remote=remote,
            description=_description(detail),
            posted_at=j.get("releasedDate"),
        )

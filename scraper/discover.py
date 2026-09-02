"""Discovery feeds suggest companies for the target list. They never write
the store. Remotive caps at roughly four calls a day, so this makes two;
We Work Remotely publishes category RSS. Anything whose title or text hits
an intersection term is grouped by company and printed with the add
command to run once the company's careers page is known."""

import re
from urllib.parse import urlencode

from . import http
from .adapters import rss
from .score import load_rules

REMOTIVE = "https://remotive.com/api/remote-jobs"
REMOTIVE_CATEGORIES = ("design", "software-dev")
WWR_FEEDS = (
    "https://weworkremotely.com/categories/remote-design-jobs.rss",
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
)


def _pattern(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")


def _hits(text, terms):
    text = (text or "").lower()
    return [t for t in terms if _pattern(t).search(text)]


def remotive(get_json=None):
    get_json = get_json or http.get_json
    out = []
    for cat in REMOTIVE_CATEGORIES:
        payload = get_json(f"{REMOTIVE}?{urlencode({'category': cat, 'limit': 100})}")
        for j in payload.get("jobs", []):
            out.append({"company": j.get("company_name") or "?", "title": j.get("title") or "", "url": j.get("url") or "", "text": j.get("description") or "", "source": "remotive"})
    return out


def wwr(get_text=None):
    get_text = get_text or http.get_text
    out = []
    for feed in WWR_FEEDS:
        for p in rss.parse(get_text(feed)):
            company, _, title = p["title"].partition(":")
            if not title:
                company, title = "?", p["title"]
            out.append({"company": company.strip(), "title": title.strip(), "url": p["url"], "text": p["description"], "source": "wwr"})
    return out


def discover(known_slugs=(), rules=None, get_json=None, get_text=None):
    """[{company, title, url, source, terms, known}] for every posting that hits the intersection terms."""
    rules = rules or load_rules()
    terms = [t for leg in rules["score"]["intersection"]["legs"].values() for t in leg]
    found, seen_urls = [], set()
    for item in remotive(get_json) + wwr(get_text):
        if item["url"] in seen_urls:
            continue  # the same posting can sit in two categories or two feeds
        seen_urls.add(item["url"])
        hits = _hits(item["title"] + "\n" + item["text"], terms)
        if not hits:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", item["company"].lower()).strip("-")
        item.update({"terms": hits, "known": slug in set(known_slugs)})
        found.append(item)
    found.sort(key=lambda i: (i["known"], i["company"].lower(), -len(i["terms"])))
    return found


def render(found):
    if not found:
        return "Nothing hit the intersection terms today."
    lines, current = [], None
    for i in found:
        if i["company"] != current:
            current = i["company"]
            flag = " (on the list)" if i["known"] else ""
            lines.append(f"\n{current}{flag}")
        lines.append(f"  {i['title']}  [{', '.join(i['terms'][:4])}]  {i['url']}")
        if not i["known"]:
            lines.append(f"    add: python -m scraper add <careers-url> --category <cat> --name \"{current}\"")
    return "\n".join(lines).strip()

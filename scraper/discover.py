"""Discovery: the feeds where companies show up before anyone puts them on a
list. Six remote job feeds and the monthly Hacker News "Who is hiring"
thread are read nightly. Every posting that hits the intersection terms is
kept. When a posting's links give away a Greenhouse, Lever, Ashby or other
board, that is the company's whole board, so `grow` adds the company to
the list and the poll watches everything it posts from then on. Postings
with no board behind them are stored as postings in their own right, under
a company record that can only be checked by hand, so nothing relevant is
lost for lack of an ATS. Nothing here decides anything; the protocol gates
score what arrives."""

import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from . import adapters, companies, http
from .adapters import rss
from .adapters._text import html_to_text
from .poll import enrich
from .posting import posting
from .score import load_rules, score

REMOTIVE = "https://remotive.com/api/remote-jobs"
REMOTIVE_CATEGORIES = ("design", "software-dev")
WWR_FEEDS = (
    "https://weworkremotely.com/categories/remote-design-jobs.rss",
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
)
HIMALAYAS = "https://himalayas.app/jobs/api?limit=100"
JOBICY = "https://jobicy.com/api/v2/remote-jobs?count=50"
ARBEITNOW = "https://www.arbeitnow.com/api/job-board-api"
REMOTEOK = "https://remoteok.com/api"
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=10"
HN_ITEM = "https://hn.algolia.com/api/v1/items/{id}"
HN_LINK = "https://news.ycombinator.com/item?id={id}"

SOURCES = ("remotive", "wwr", "himalayas", "jobicy", "arbeitnow", "remoteok", "hn")


def _pattern(term):
    if re.search(r"[\\^$.|?*+()\[\]{}]", term):
        return re.compile(term, re.IGNORECASE)
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")


def _hits(text, terms):
    text = (text or "").lower()
    return [t for t in terms if _pattern(t).search(text)]


def _iso(value):
    """Feeds date things every way there is; anything unreadable is None."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat()
    s = str(value).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            d = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            return d.replace(microsecond=0).isoformat()
        except ValueError:
            continue
    return None


def _item(source, company, title, url, raw, source_id=None, location=None, posted_at=None, apply_url=None):
    return {
        "source": source,
        "source_id": str(source_id) if source_id is not None else None,
        "company": (company or "?").strip() or "?",
        "title": (title or "").strip(),
        "url": url or "",
        "apply_url": apply_url or "",
        "raw": raw or "",
        "text": html_to_text(raw or ""),
        "location": (location or "").strip(),
        "posted_at": _iso(posted_at),
    }


# the feeds


def remotive(get_json):
    out = []
    for cat in REMOTIVE_CATEGORIES:
        payload = get_json(f"{REMOTIVE}?{urlencode({'category': cat, 'limit': 100})}")
        for j in payload.get("jobs", []):
            out.append(_item("remotive", j.get("company_name"), j.get("title"), j.get("url"), j.get("description"), j.get("id"), j.get("candidate_required_location"), j.get("publication_date")))
    return out


def wwr(get_text):
    out = []
    for feed in WWR_FEEDS:
        for p in rss.parse(get_text(feed)):
            company, _, title = p["title"].partition(":")
            if not title:
                company, title = "?", p["title"]
            out.append(_item("wwr", company, title, p["url"], p["description"], p.get("source_id"), posted_at=p.get("posted_at")))
    return out


def himalayas(get_json):
    payload = get_json(HIMALAYAS)
    out = []
    for j in payload.get("jobs", []):
        loc = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
        out.append(_item("himalayas", j.get("companyName"), j.get("title"), j.get("applicationLink") or j.get("guid"), j.get("description"), j.get("guid") or j.get("applicationLink"), loc, j.get("pubDate"), j.get("applicationLink")))
    return out


def jobicy(get_json):
    payload = get_json(JOBICY)
    out = []
    for j in payload.get("jobs", []):
        out.append(_item("jobicy", j.get("companyName"), j.get("jobTitle"), j.get("url"), j.get("jobDescription"), j.get("id"), j.get("jobGeo"), j.get("pubDate")))
    return out


def arbeitnow(get_json):
    payload = get_json(ARBEITNOW)
    out = []
    for j in payload.get("data", []):
        if not j.get("remote"):
            continue
        out.append(_item("arbeitnow", j.get("company_name"), j.get("title"), j.get("url"), j.get("description"), j.get("slug"), j.get("location"), j.get("created_at")))
    return out


def remoteok(get_json):
    payload = get_json(REMOTEOK)
    out = []
    for j in payload if isinstance(payload, list) else []:
        if not isinstance(j, dict) or not j.get("position"):
            continue  # the first element is the legal notice
        out.append(_item("remoteok", j.get("company"), j.get("position"), j.get("url"), j.get("description"), j.get("id"), j.get("location"), j.get("date"), j.get("apply_url")))
    return out


def detect_board(item, get_json=None, get_text=None):
    """One hop: fetch the posting page and look for an ATS board in it. The
    feeds link to themselves, and the apply button is what points at the
    company's real board. Any failure is a None, never an exception."""
    try:
        hit = adapters.detect(item["url"], get_json, get_text)
    except Exception:
        return None
    if hit and hit[0] in adapters.ADAPTERS and hit[0] != "rss":
        return hit[0], hit[1]
    return None


def _hn_parse(text):
    """(company, title, location) from a Who is hiring comment's first line,
    which by convention reads `Company | Role | REMOTE | Salary | ...`."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    parts = [p.strip() for p in first.split("|") if p.strip()]
    if len(parts) < 2:
        return "?", "", ""  # no pipes, no convention, no reliable company name
    company = re.sub(r"\s*\(.*?\)\s*$", "", parts[0])[:80]
    title, location = "", ""
    for p in parts[1:]:
        low = p.lower()
        if not location and re.search(r"remote|onsite|on-site|hybrid|[A-Z][a-z]+, [A-Z]{2}\b", p, re.IGNORECASE):
            location = p
        elif not title and "$" not in p and not re.search(r"full[- ]time|part[- ]time|contract|visa|http", low):
            title = p
    return company, title[:120], location[:120]


def hn(get_json):
    hits = get_json(HN_SEARCH).get("hits", [])
    story = next((h for h in hits if str(h.get("title", "")).lower().startswith("ask hn: who is hiring")), None)
    if story is None:
        return []
    thread = get_json(HN_ITEM.format(id=story["objectID"]))
    out = []
    for c in thread.get("children", []):
        raw = c.get("text") or ""
        if not raw.strip() or c.get("author") in (None, "[deleted]"):
            continue
        text = html_to_text(raw)
        company, title, location = _hn_parse(text)
        out.append(_item("hn", company, title or "see the posting", HN_LINK.format(id=c["id"]), raw, c["id"], location, c.get("created_at")))
    return out


FEEDS = {"remotive": remotive, "wwr": wwr, "himalayas": himalayas, "jobicy": jobicy, "arbeitnow": arbeitnow, "remoteok": remoteok, "hn": hn}


# reading them


def collect(get_json=None, get_text=None, sources=SOURCES, errors=None):
    """Every item from every source, one source's failure never touching another's."""
    get_json = get_json or http.get_json
    get_text = get_text or http.get_text
    items = []
    for name in sources:
        fn = FEEDS[name]
        try:
            items += fn(get_text) if name == "wwr" else fn(get_json)
        except (http.HttpError, ValueError, KeyError, TypeError, AttributeError) as e:
            if errors is not None:
                errors.append(f"{name}: {type(e).__name__}: {e}")
    return items


def board_of(item):
    """The pollable (kind, board) a posting gives away through its links, or None."""
    for kind, board in adapters.candidates(" ".join((item["url"], item["apply_url"], item["raw"]))):
        if kind in adapters.ADAPTERS and kind != "rss":
            return kind, board
    return None


def _generic(name, rules):
    n = (name or "").strip().lower()
    d = rules["discovery"]
    if n in d["generic_company_names"] or not n:
        return True
    return len(n.split()) > d["max_company_name_words"]


def relevant(item, rules):
    """The terms a creative-technical posting names and a backend, QA or sales
    posting does not. The scoring legs are deliberately broad, which is right
    for a company already on the list and wrong for an open feed: `api`,
    `automation` and `rendering` match every software job ever written.
    Returns the terms that hit, empty when the posting is not for Matt."""
    d = rules["discovery"]
    title = (item["title"] or "").lower()
    for pat in d["exclude_title_patterns"]:
        if _pattern(pat).search(title):
            return []
    return _hits(item["title"] + "\n" + item["text"], d["require_any"])


def _remote(item):
    text = (item["location"] + "\n" + item["text"]).lower()
    if item["source"] == "hn":
        return "remote" in text
    return True  # the other feeds are remote-only boards; the gate vets the wording


def discover(known=(), rules=None, get_json=None, get_text=None, sources=SOURCES, errors=None):
    """[{... terms, ats, known}] for every remote posting that names something
    only a creative-technical role names, unknown companies first. `known` is
    the company list's records. A posting whose own links do not give away a
    board gets its page fetched once, up to the ruleset's cap, because the
    feeds mostly link to themselves and the board is one hop further in."""
    rules = rules or load_rules()
    known_slugs = {c["slug"] for c in known}
    known_boards = {(c["ats"]["kind"], (c["ats"]["board"] or "").lower()) for c in known}
    found, seen_urls, fetches = [], set(), 0
    cap = rules["discovery"]["max_page_fetches"]
    for item in collect(get_json, get_text, sources, errors):
        if not item["url"] or item["url"] in seen_urls:
            continue  # the same posting can sit in two categories or two feeds
        seen_urls.add(item["url"])
        if not _remote(item) or _generic(item["company"], rules):
            continue
        hits = relevant(item, rules)
        if not hits:
            continue
        ats = board_of(item)
        if ats is None and fetches < cap:
            fetches += 1
            ats = detect_board(item, get_json, get_text)
        slug = companies.slugify(item["company"])
        item.update({
            "terms": hits,
            "ats": ats,
            "slug": slug,
            "known": slug in known_slugs or (ats is not None and (ats[0], ats[1].lower()) in known_boards),
        })
        found.append(item)
    found.sort(key=lambda i: (i["known"], i["ats"] is None, i["company"].lower(), -len(i["terms"])))
    return found


def grow(store, data, rules=None, get_json=None, get_text=None, today=None, now=None, board_cap=15, posting_cap=30, errors=None):
    """Add what discovery found to the list and the store. A posting that gives
    away a board adds the company as pollable; the poll picks up its whole
    board the same night. A posting with no board adds a hand-check company
    and the posting itself, scored like any other. Caps keep one wild night
    from doubling the list. Returns {companies: [records], postings: [ids]}."""
    rules = rules or load_rules()
    now = now or datetime.now(timezone.utc)
    today = today or now.date().isoformat()
    found = discover(data["companies"], rules, get_json, get_text, errors=errors)
    by_slug = {c["slug"]: c for c in data["companies"]}
    added, stored = [], []
    for item in found:
        if item["known"] and item["slug"] not in by_slug:
            continue  # the board is on the list under another slug; the poll has it
        rec = by_slug.get(item["slug"])
        if rec is None:
            if item["ats"]:
                if len(added) >= board_cap:
                    continue
                kind, board = item["ats"]
                rec = companies.record(item["slug"], item["company"], kind, board, "discovered", 3, item["url"], today=today)
            else:
                if len(stored) >= posting_cap:
                    continue
                rec = companies.record(item["slug"], item["company"], "manual", None, "discovered", 3, item["url"], today=today)
            companies.add(data, rec)
            by_slug[item["slug"]] = rec
            added.append(rec)
        if rec["ats"]["kind"] != "manual":
            continue  # pollable: the poll stores its postings from the board itself
        if len(stored) >= posting_cap:
            continue
        p = posting(
            source=item["source"], source_id=item["source_id"] or item["url"], company_slug=rec["slug"], title=item["title"] or "see the posting",
            url=item["url"], location=item["location"] or "Remote", remote="remote", description=item["text"], posted_at=item["posted_at"],
        )
        enrich(p)
        pid, is_new = store.upsert(p, now.replace(microsecond=0).isoformat())
        store.set_score(pid, score(store.get(pid), rules, now, company=rec))
        if is_new:
            stored.append(pid)
    return {"companies": added, "postings": stored, "found": len(found)}


def render(found, errors=()):
    if not found and not errors:
        return "Nothing hit the intersection terms today."
    lines, current = [], None
    for i in found:
        if i["company"] != current:
            current = i["company"]
            if i["known"]:
                flag = " (on the list)"
            elif i["ats"]:
                flag = f" (board found: {i['ats'][0]}/{i['ats'][1]}, the next poll adds it)"
            else:
                flag = " (no board found, the posting itself is stored)"
            lines.append(f"\n{current}{flag}")
        lines.append(f"  {i['title']}  [{', '.join(i['terms'][:4])}]  {i['source']}  {i['url']}")
    for e in errors:
        lines.append(f"\nfeed error: {e}")
    return "\n".join(lines).strip()

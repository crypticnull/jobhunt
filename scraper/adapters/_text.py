"""Text helpers shared by adapters: HTML to plain text, remote classification."""

import html
import re
from html.parser import HTMLParser

_BLOCK = {
    "p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
    "tr", "section", "article", "header", "footer", "table",
}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(s):
    if not s:
        return ""
    # Greenhouse ships its HTML entity-escaped, so unescape until stable first.
    prev = None
    while prev != s:
        prev, s = s, html.unescape(s)
    p = _Text()
    p.feed(s)
    p.close()
    text = "".join(p.parts)
    text = re.sub(r"[ \t\r]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


_REMOTE_WORDS = ("remote", "anywhere", "distributed", "work from home", "wfh", "virtual", "telecommut", "home-based", "home based")

# A location that names a country or a region and no city says nothing about
# where the desk is. Before 2026-09-05 any of these was stamped onsite, which
# was 6,069 of the 9,591 logged rows and the whole reason Figma, Vercel and
# Dropbox polled a hundred postings each with none on target: Greenhouse has
# no structured workplace field, so "United States" was a hard fail before
# the body was read. Now it is unclear and the body decides.
_NO_CITY = (
    "united states", "united states of america", "us", "usa", "u.s.", "u.s.a.", "u.s", "north america",
    "americas", "america", "multiple locations", "multiple", "various", "various locations", "flexible",
    "global", "any location", "any", "nationwide", "worldwide", "n/a", "tbd", "other",
    # countries and regions, which the abroad gate in score.py then judges by the location alone
    "canada", "united kingdom", "uk", "europe", "emea", "apac", "latam", "germany", "france", "spain", "india",
    "australia", "mexico", "brazil", "ireland", "netherlands", "poland", "portugal", "israel", "japan", "singapore",
)


def _no_city(loc):
    """True when the location text is only country, region or filler words."""
    parts = [x.strip() for x in re.split(r"[;,/|()\-]+", loc) if x.strip()]
    return bool(parts) and all(x in _NO_CITY for x in parts)


def classify_remote(location="", workplace_type=None):
    """remote | hybrid | onsite | unclear. A structured workplace type wins;
    otherwise the location text decides, hybrid beating remote when both appear,
    and a country or region with no city is unclear rather than onsite."""
    wt = (workplace_type or "").strip().lower()
    if wt == "remote":
        return "remote"
    if wt == "hybrid":
        return "hybrid"
    if wt in ("onsite", "on-site", "on_site", "office", "in-office"):
        return "onsite"
    loc = (location or "").lower()
    if "hybrid" in loc:
        return "hybrid"
    if any(w in loc for w in _REMOTE_WORDS):
        return "remote"
    if not loc.strip() or _no_city(loc):
        return "unclear"
    return "onsite"

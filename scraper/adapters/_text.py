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


_REMOTE_WORDS = ("remote", "anywhere", "distributed", "work from home", "wfh")


def classify_remote(location="", workplace_type=None):
    """remote | hybrid | onsite | unclear. A structured workplace type wins;
    otherwise the location text decides, hybrid beating remote when both appear."""
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
    if not loc.strip():
        return "unclear"
    return "onsite"

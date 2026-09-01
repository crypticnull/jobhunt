"""RSS and Atom feeds. The board is the feed URL, so a company's own careers
feed slots into the same list as an ATS board. Feeds rarely say anything
about remote or pay, so those stay unclear and absent, and scoring makes
the case from the title and the description."""

import xml.etree.ElementTree as ET

from .. import http
from ..posting import posting
from ._text import html_to_text

KIND = "rss"
_ATOM = "{http://www.w3.org/2005/Atom}"


def endpoint(feed_url):
    return feed_url


def fetch(feed_url, get_json=None):
    """Feeds are XML, so this ignores get_json and reads text. Tests pass get_text."""
    return http.get_text(feed_url)


def _text(el, *tags):
    for tag in tags:
        node = el.find(tag)
        if node is not None and (node.text or "").strip():
            return node.text.strip()
    return ""


def parse(xml_text):
    if not xml_text or not str(xml_text).strip():
        return
    root = ET.fromstring(xml_text)
    items = root.findall(".//item")
    entries = root.findall(f".//{_ATOM}entry")
    for it in items:
        title = _text(it, "title")
        link = _text(it, "link")
        desc = html_to_text(_text(it, "description"))
        yield posting(
            source=KIND,
            source_id=_text(it, "guid") or link,
            title=title,
            url=link,
            location="",
            remote="remote" if "remote" in title.lower() else "unclear",
            description=desc,
            posted_at=_text(it, "pubDate") or None,
        )
    for en in entries:
        title = _text(en, f"{_ATOM}title")
        link_el = en.find(f"{_ATOM}link")
        link = (link_el.get("href") if link_el is not None else "") or ""
        desc = html_to_text(_text(en, f"{_ATOM}summary", f"{_ATOM}content"))
        yield posting(
            source=KIND,
            source_id=_text(en, f"{_ATOM}id") or link,
            title=title,
            url=link,
            location="",
            remote="remote" if "remote" in title.lower() else "unclear",
            description=desc,
            posted_at=_text(en, f"{_ATOM}published", f"{_ATOM}updated") or None,
        )

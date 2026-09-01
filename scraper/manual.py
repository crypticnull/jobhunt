"""A posting that did not come through a poller: a referral, a company not
on the list yet, a page with no feed. It becomes a normal row through
store.py, fingerprinted by content, enriched and scored like the rest, so
the letter generator treats it identically."""

from pathlib import Path

from . import http
from .adapters._text import classify_remote, html_to_text
from .posting import posting


def read_source(src, get_text=None):
    """(text, url_or_None). A URL is fetched and reduced to plain text; anything else is a file."""
    if src.startswith(("http://", "https://")):
        get_text = get_text or http.get_text
        return html_to_text(get_text(src)), src
    return Path(src).read_text(encoding="utf-8"), None


def from_text(company_slug, title, text, url=None, location="", remote=None):
    return posting(
        source="manual",
        source_id=None,
        company_slug=company_slug,
        title=title,
        url=url or f"manual:{company_slug}",
        location=location,
        remote=remote or classify_remote(location),
        description=text.strip(),
    )

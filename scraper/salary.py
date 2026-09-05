"""Pull a salary range out of description text when the ATS gave none.

Structured pay data is the exception on every platform, so this cheap regex
pass is what makes comp scoring work at all. It is deliberately modest: a
dollar range, or two dollar figures near each other, annualized when the
text says per hour. Anything cleverer earns its keep later."""

import re

_AMOUNT = r"\$\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kK])?"
_RANGE = re.compile(_AMOUNT + r"\s*(?:-|–|—|to|and)\s*" + _AMOUNT)
_SINGLE = re.compile(_AMOUNT)
_HOURLY = re.compile(r"(?:per|/|an)\s*(?:hour|hr)\b", re.IGNORECASE)
_CURRENCY = re.compile(r"\b(USD|CAD|EUR|GBP|AUD)\b")


def _num(raw, k):
    n = float(raw.replace(",", ""))
    if k:
        n *= 1000
    return int(n)


def _annualize(lo, hi, text, end):
    tail = text[end : end + 20]
    if _HOURLY.search(tail) or (hi < 500 and _HOURLY.search(text)):
        return lo * 2080, hi * 2080, "hourly"
    return lo, hi, None


def extract(text):
    """(min, max, currency, note) or None. note is 'hourly' when annualized.
    Every range in the text is tried in order and the first that reads as a
    salary wins, so a home office stipend before the base pay no longer hides
    it. A range under 20,000 after annualizing is a bonus, a stipend or a price."""
    if not text:
        return None
    for m in _RANGE.finditer(text):
        lo, hi = _num(m.group(1), m.group(2)), _num(m.group(3), m.group(4))
        lo, hi = min(lo, hi), max(lo, hi)
        lo, hi, note = _annualize(lo, hi, text, m.end())
        if hi >= 20000:
            return _with_currency(text, m, lo, hi, note)
    for m in _SINGLE.finditer(text):
        lo = hi = _num(m.group(1), m.group(2))
        lo, hi, note = _annualize(lo, hi, text, m.end())
        if hi >= 20000:
            return _with_currency(text, m, lo, hi, note)
    return None


def _with_currency(text, m, lo, hi, note):
    cur = _CURRENCY.search(text[max(0, m.start() - 30) : m.end() + 30])
    return lo, hi, (cur.group(1) if cur else "USD"), note

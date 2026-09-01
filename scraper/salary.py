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


def extract(text):
    """(min, max, currency, note) or None. note is 'hourly' when annualized."""
    if not text:
        return None
    m = _RANGE.search(text)
    if m:
        lo, hi = _num(m.group(1), m.group(2)), _num(m.group(3), m.group(4))
        span = m.group(0)
        tail = text[m.end() : m.end() + 20]
    else:
        m = _SINGLE.search(text)
        if not m:
            return None
        lo = hi = _num(m.group(1), m.group(2))
        span = m.group(0)
        tail = text[m.end() : m.end() + 20]
    lo, hi = min(lo, hi), max(lo, hi)
    note = None
    if _HOURLY.search(tail) or (hi < 500 and _HOURLY.search(text)):
        lo, hi, note = lo * 2080, hi * 2080, "hourly"
    if hi < 20000:
        return None  # a bonus, a stipend, a price, not a salary
    cur = _CURRENCY.search(text[max(0, m.start() - 30) : m.end() + 30])
    return lo, hi, (cur.group(1) if cur else "USD"), note

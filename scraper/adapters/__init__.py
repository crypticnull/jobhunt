"""Adapter registry and ATS detection.

ADAPTERS holds the kinds that can be polled. PROBE_ENDPOINTS is the cheap
health-check URL per kind; rss has none because its board is the feed URL."""

import re

from .. import http
from . import ashby, greenhouse, lever, recruitee, rss, smartrecruiters, workable

ADAPTERS = {m.KIND: m for m in (greenhouse, lever, ashby, workable, smartrecruiters, recruitee, rss)}

PROBE_ENDPOINTS = {
    "greenhouse": lambda b: f"https://boards-api.greenhouse.io/v1/boards/{b}/jobs",
    "lever": lambda b: f"https://api.lever.co/v0/postings/{b}?mode=json",
    "ashby": lambda b: f"https://api.ashbyhq.com/posting-api/job-board/{b}",
    "workable": lambda b: f"https://apply.workable.com/api/v1/widget/accounts/{b}?details=true",
    "smartrecruiters": lambda b: f"https://api.smartrecruiters.com/v1/companies/{b}/postings",
    "recruitee": lambda b: f"https://{b}.recruitee.com/api/offers/",
}

# Order matters: the first confirmed candidate wins.
_URL_PATTERNS = [
    ("greenhouse", re.compile(r"(?:boards|job-boards|boards-api)\.greenhouse\.io/(?:v1/boards/|embed/(?:job_board(?:/js)?|js)\?for=)?([A-Za-z0-9_-]+)")),
    ("lever", re.compile(r"(?:jobs|api)\.lever\.co/(?:v0/postings/)?([A-Za-z0-9_-]+)")),
    ("ashby", re.compile(r"(?:jobs|api)\.ashbyhq\.com/(?:posting-api/job-board/)?([A-Za-z0-9_.-]+)")),
    ("workable", re.compile(r"apply\.workable\.com/(?:api/v1/widget/accounts/)?([A-Za-z0-9_-]+)")),
    ("smartrecruiters", re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/([A-Za-z0-9_-]+)|api\.smartrecruiters\.com/v1/companies/([A-Za-z0-9_-]+)")),
    ("recruitee", re.compile(r"https?://([A-Za-z0-9-]+)\.recruitee\.com")),
]
_NOT_A_BOARD = {"embed", "api", "www", "app", "v1", "jobs", "job_board"}


def candidates(text):
    """(kind, board) pairs found in a URL or a page of HTML, in order of appearance, deduplicated."""
    found = []
    for kind, pat in _URL_PATTERNS:
        for m in pat.finditer(text or ""):
            board = next((g for g in m.groups() if g), None)
            if not board or board.lower() in _NOT_A_BOARD:
                continue
            pair = (kind, board)
            if pair not in found:
                found.append(pair)
    return found


def count_postings(kind, payload):
    if kind in ("greenhouse", "ashby"):
        return len(payload.get("jobs", [])) if isinstance(payload, dict) else 0
    if kind == "lever":
        return len(payload) if isinstance(payload, list) else 0
    if kind == "workable":
        return len(payload.get("jobs") or payload.get("results") or []) if isinstance(payload, dict) else 0
    if kind == "smartrecruiters":
        return len(payload.get("content", [])) if isinstance(payload, dict) else 0
    if kind == "recruitee":
        return len(payload.get("offers", [])) if isinstance(payload, dict) else 0
    return 0


def probe(kind, board, get_json=None):
    """(ok, posting_count, error). ok means the endpoint answered with parseable JSON."""
    get_json = get_json or http.get_json
    if kind not in PROBE_ENDPOINTS or not board:
        return False, 0, f"no endpoint for kind {kind!r}"
    url = PROBE_ENDPOINTS[kind](board)
    try:
        payload = get_json(url)
    except http.HttpError as e:
        return False, 0, str(e)
    return True, count_postings(kind, payload), None


# Words a company puts in its name and leaves out of its board slug. The live
# run of 2026-09-02 is the evidence: Luma AI is `lumaai`, Odyssey is
# `odysseyml`, Higgsfield is `higgsfieldai`.
_NOISE_WORDS = {"ai", "labs", "lab", "inc", "llc", "ltd", "co", "com", "studio", "studios", "the", "group", "technologies", "digital"}


def slug_variants(name):
    """The handful of board slugs a company name is likely to use, most likely
    first: joined, hyphenated, then the same two with the marketing words
    dropped, then the first word alone."""
    words = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower()).split()
    if not words:
        return []
    out = ["".join(words), "-".join(words)]
    trimmed = [w for w in words if w not in _NOISE_WORDS] or words
    if trimmed != words:
        out += ["".join(trimmed), "-".join(trimmed)]
    if len(words) > 1:
        out.append(words[0])
    return list(dict.fromkeys(out))


GUESS_KINDS = ("greenhouse", "lever", "ashby", "workable")


def guess(name, get_json=None, kinds=GUESS_KINDS, variants=4):
    """When a careers URL gives nothing away, try the company's name as a board
    slug against each ATS. A slug that answers with live postings is the board;
    an empty answer is not taken, because a wrong slug and an empty board look
    the same. Returns (kind, board, count) or None."""
    for slug in slug_variants(name)[:variants]:
        for kind in kinds:
            ok, count, _ = probe(kind, slug, get_json)
            if ok and count > 0:
                return kind, slug, count
    return None


def detect(url, get_json=None, get_text=None):
    """Work out which ATS a careers URL runs on. Tries the URL itself, then the
    page's HTML for embedded board links, and confirms each candidate against
    its public endpoint. Returns (kind, board, posting_count) or None."""
    get_json = get_json or http.get_json
    get_text = get_text or http.get_text
    cands = candidates(url)
    if not cands:
        try:
            cands = candidates(get_text(url))
        except http.HttpError:
            return None
    for kind, board in cands:
        ok, count, _ = probe(kind, board, get_json)
        if ok:
            return kind, board, count
    return None

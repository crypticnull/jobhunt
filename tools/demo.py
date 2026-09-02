"""make demo: the whole loop, offline, in under a minute.

Polls the example companies from recorded fixtures into a throwaway store,
scores and digests them, writes the brief for the top posting, assembles a
draft from the blocks, runs the voice lint on it and files it. Nothing
touches the network or data/local. What the README claims, this runs."""

import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from letters import assemble  # noqa: E402
from letters.__main__ import save_draft  # noqa: E402
from letters.voicelint import check_text  # noqa: E402
from letters.voicelint import load_rules as load_voice  # noqa: E402
from scraper import companies, digest, http  # noqa: E402
from scraper.poll import poll  # noqa: E402
from scraper.score import RULES_PATH, load_rules  # noqa: E402
from scraper.store import Store  # noqa: E402

FIX = ROOT / "scraper" / "tests" / "fixtures"
# A demo band, not the real one. The real numbers live in data/local/scoring.local.json.
DEMO_BAND = {"gates": {"comp": {"pass_min_annual": 100000, "flag_min_annual": 80000, "fail_below_annual": 80000, "hourly_floor": 60}}, "score": {"comp": {"bands": [{"midpoint_min": 120000, "points": 20}, {"midpoint_min": 100000, "points": 15}, {"midpoint_min": 80000, "points": 5}]}}}


def fixture_json(url):
    """The network, replaced by the recorded fixtures."""
    if "smartrecruiters" in url:
        name = "smartrecruiters.detail.json" if url.rstrip("/").endswith("0001") else "smartrecruiters.json"
        return json.loads((FIX / name).read_text(encoding="utf-8"))
    for name in ("greenhouse", "lever", "ashby", "workable", "recruitee"):
        if name in url:
            return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))
    raise http.HttpError(url, 503, "the demo has no fixture for this url")


def rule(title):
    print(f"\n== {title} " + "=" * max(0, 60 - len(title)))


def main():
    t0 = time.time()
    rules = load_rules(RULES_PATH, local="/nonexistent/scoring.local.json")
    from scraper.score import _deep_merge
    _deep_merge(rules, DEMO_BAND)
    voice = load_voice()
    data = companies.load(ROOT / "data" / "companies.example.json")
    names = {c["slug"]: c for c in data["companies"]}
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        store = Store(tmp / "postings.db")

        rule("poll, from recorded fixtures")
        for r in poll(store, data["companies"], get_json=fixture_json, now=now.isoformat(), rules=rules):
            status = "skip " if r["ok"] is None else ("ok   " if r["ok"] else "ERROR")
            print(f"{status} {r['slug']:<18} {r['kind']:<12} seen {r['seen']} new {r['new']}  {r['error'] or ''}".rstrip())

        rule("digest, apply and review piles, drops by reason")
        md, ids = digest.build(store, rules, names, now=now)
        print(md)

        top = next(r for r in store.open_postings() if r["pile"] == "apply")
        company = next(c for c in data["companies"] if c["slug"] == top["company_slug"])
        rule(f"brief for posting {top['id']}, {top['title']} at {company['name']}")
        chosen = assemble.select(top, company)
        brief = assemble.render_brief(top, company, chosen, voice)
        print("\n".join(brief.splitlines()[:14]) + "\n...")

        rule("a draft assembled from the blocks, then the voice lint")
        opening = assemble.fill(chosen["openings"][1][1], specific="local video models")
        close = assemble.fill(chosen["closes"][0][1], site="the site")
        draft = "\n\n".join([opening, chosen["claim"][1], chosen["proof"][2].split("\n\n")[0], close]) + "\n"
        print(draft)
        findings = check_text(draft, "letter", voice, "draft")
        print(f"voicelint: {len(findings)} finding(s)" + (" -> " + "; ".join(str(f) for f in findings) if findings else ", clean"))

        rule("save, refused unless the lint is clean, then mark applied")
        path, findings = save_draft(top, company, draft, tmp / "letters", voice, today="2026-09-07")
        if path is None:
            print("refused, the demo draft failed its own lint")
            return 1
        print(f"filed {path.name}")
        print("\n".join(path.read_text(encoding="utf-8").splitlines()[:8]))
        store.mark(top["id"], "applied", letter_path=str(path))
        s = store.stats()
        print(f"\nstats: {s['postings']} postings, {s['open']} open, by state " + ", ".join(f"{k} {v}" for k, v in sorted(s["by_state"].items())))
        store.close()

    print(f"\ndone in {time.time() - t0:.1f}s, nothing touched the network or data/local")
    return 0


if __name__ == "__main__":
    sys.exit(main())

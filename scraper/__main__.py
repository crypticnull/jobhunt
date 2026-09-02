"""python -m scraper <command>

  add URL        detect the ATS behind a careers URL and add the company
  import FILE    many companies at once from a text file, one per line: category | careers url | name
  add-posting    a posting from a URL or a file, for referrals and unpolled companies
  check          probe every company's endpoint, report dead ones
  stale          companies not reviewed in N days
  poll           read the discovery feeds, add what they give away, then fetch every pollable company
  digest         write this week's digest to data/digests (public, pushed on Sundays), or --stdout
  score          rescore every open posting with the current ruleset
  mark ID STATE  new | reviewed | applied | screen | loop | offer | rejected | skipped
  stats          counts from the store, --markdown --since DATE for the monthly snapshot
  discover       what the feeds are surfacing right now, without writing anything
  backup         copy postings.db to an off-disk directory, keep the newest fourteen
  export         the status history as JSON, one file per month
  fixture        refresh an adapter's test fixture from the live endpoint
"""

import argparse
import sys
from pathlib import Path

from . import adapters, companies, digest, discover, maintain, manual
from .poll import enrich, poll
from .score import load_rules, score
from .store import STATES, Store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPANIES = ROOT / "data" / "companies.json"
DEFAULT_DB = ROOT / "data" / "local" / "postings.db"


def cmd_add(args):
    data = companies.load(args.companies)
    kind, board, count = args.kind, args.board, None
    if kind is None:
        hit = adapters.detect(args.url)
        if hit is None:
            print(f"could not detect an ATS behind {args.url}. Pass --kind manual (or --kind/--board) to add it anyway.", file=sys.stderr)
            return 2
        kind, board, count = hit
    name = args.name or board or args.url
    slug = args.slug or companies.slugify(name)
    rec = companies.record(slug, name, kind, board, args.category, args.priority, args.url, args.lead_proof)
    companies.add(data, rec)
    companies.save(args.companies, data)
    where = f"{kind}/{board}" if board else kind
    print(f"added {slug}: {where}" + (f", {count} postings live" if count is not None else ""))
    return 0


def parse_import_lines(text):
    """[(category, url, name)] from lines like `ai-video | https://x.com/careers | X`.
    Blank lines and # comments are skipped; a bad line raises with its number."""
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split("|")]
        if len(parts) != 3 or parts[0] not in companies.CATEGORIES or not parts[1].startswith("http"):
            raise ValueError(f"line {n}: expected `category | careers url | name` with a category from {', '.join(companies.CATEGORIES)}, got {raw!r}")
        out.append(tuple(parts))
    return out


def cmd_import(args):
    try:
        rows = parse_import_lines(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 2
    data = companies.load(args.companies)
    known = {c["slug"] for c in data["companies"]}
    added, skipped, guessed, missed = 0, 0, 0, []
    for category, url, name in rows:
        slug = companies.slugify(name)
        if slug in known:
            skipped += 1
            print(f"skip      {name}: already on the list")
            continue
        hit = adapters.detect(url)
        if hit is None and not args.no_guess:
            hit = adapters.guess(name)
            if hit:
                guessed += 1
        if hit is None and not args.manual:
            missed.append((category, url, name))
            print(f"unknown   {name}: no board found behind {url}, and the name is not a board slug either")
            continue
        kind, board, count = hit or ("manual", None, None)
        rec = companies.record(slug, name, kind, board, category, args.priority, url)
        companies.add(data, rec)
        known.add(slug)
        added += 1
        where = f"{kind}/{board}" if board else kind
        print(f"added     {name}: {where}" + (f", {count} postings live" if count is not None else ""))
    companies.save(args.companies, data)
    print(f"{added} added ({guessed} found by guessing the board slug), {skipped} already there, {len(missed)} with no board found")
    if missed:
        print("Check the careers URL for these, or rerun with --manual to keep them on the list for hand checks:")
        for category, url, name in missed:
            print(f"  {category} | {url} | {name}")
    return 0


def cmd_add_posting(args):
    data = companies.load(args.companies)
    if not any(c["slug"] == args.company for c in data["companies"]):
        print(f"{args.company} is not on the list. Add the company first with: python -m scraper add <careers-url> --category ...", file=sys.stderr)
        return 2
    text, url = manual.read_source(args.src)
    p = manual.from_text(args.company, args.title, text, url=args.url or url, location=args.location or "", remote=args.remote)
    enrich(p)
    rules = load_rules()
    company = next(c for c in data["companies"] if c["slug"] == args.company)
    store = Store(args.db)
    try:
        pid, is_new = store.upsert(p)
        store.set_score(pid, score(store.get(pid), rules, company=company))
        row = store.get(pid)
    finally:
        store.close()
    print(f"{'added' if is_new else 'updated'} posting {pid}: {row['title']} at {args.company}, {row['remote_class']}, score {round(row['score'])}, pile {row['pile']}" + (f" ({row['drop_reason']})" if row['drop_reason'] else ""))
    print(f"next: python -m letters brief {pid}")
    return 0


def cmd_check(args):
    data = companies.load(args.companies)
    dead = 0
    for r in companies.check(data):
        if r["ok"] is None:
            status = "skip"
        elif r["ok"]:
            status = f"ok   {r['count']:>4}"
        else:
            status, dead = "DEAD", dead + 1
        line = f"{status:<10} {r['slug']:<28} {r['kind']}"
        print(line + (f"  {r['error']}" if r["error"] and r["ok"] is False else ""))
    print(f"{len(data['companies'])} companies, {dead} dead")
    return 1 if dead else 0


def cmd_stale(args):
    data = companies.load(args.companies)
    rows = companies.stale(data, args.days)
    for slug, age in rows:
        print(f"{age:>4}d  {slug}")
    print(f"{len(rows)} not reviewed in {args.days} days")
    return 0


def cmd_poll(args):
    data = companies.load(args.companies)
    store = Store(args.db)
    try:
        if not args.no_discover:
            feed_errors = []
            grown = discover.grow(store, data, errors=feed_errors)
            companies.save(args.companies, data)
            boards = [c for c in grown["companies"] if c["ats"]["kind"] != "manual"]
            pct = (100.0 * grown["found"] / grown["scanned"]) if grown["scanned"] else 0.0
            print(f"discover  {grown['scanned']} postings read, {grown['found']} relevant ({pct:.1f}%), {len(boards)} new boards to poll, {len(grown['postings'])} stored")
            if pct > 15:
                print("          that share looks high. If the names below are not creative-technical roles, say so and the filter gets tightened.")
            for c in boards:
                print(f"  + {c['name']}: {c['ats']['kind']}/{c['ats']['board']}")
            for e in feed_errors:
                print(f"  feed error: {e}")
        results = poll(store, data["companies"])
    finally:
        store.close()
    errors, skipped = 0, 0
    for r in results:
        if r["ok"] is None:
            skipped += 1
        elif r["ok"]:
            print(f"ok     {r['slug']:<28} seen {r['seen']:>3}  new {r['new']:>3}  closed {r['closed']:>3}")
        else:
            errors += 1
            print(f"ERROR  {r['slug']:<28} {r['error']}")
    if skipped:
        print(f"skip   {skipped} companies have no pollable board, they are checked by hand")
    print(f"{len(results)} companies, {errors} errors")
    return 0


def cmd_digest(args):
    data = companies.load(args.companies)
    by_slug = {c["slug"]: c for c in data["companies"]}
    rules = load_rules()
    store = Store(args.db)
    try:
        if args.stdout:
            md, _ = digest.build(store, rules, by_slug)
            print(md)
            return 0
        path, n = digest.write(store, rules, Path(args.out), by_slug)
    finally:
        store.close()
    print(f"wrote {path}, {n} postings surfaced")
    return 0


def cmd_score(args):
    rules = load_rules()
    by_slug = {c["slug"]: c for c in companies.load(args.companies)["companies"]}
    store = Store(args.db)
    try:
        rows = store.open_postings()
        for row in rows:
            store.set_score(row["id"], score(row, rules, company=by_slug.get(row["company_slug"])))
    finally:
        store.close()
    print(f"rescored {len(rows)} open postings with ruleset {rules['version']}")
    return 0


def cmd_mark(args):
    store = Store(args.db)
    try:
        store.mark(args.id, args.state, note=args.note, letter_path=args.letter)
        p = store.get(args.id)
    finally:
        store.close()
    print(f"{args.id} {p['company_slug']}: {p['title']} -> {args.state}")
    return 0


def cmd_stats(args):
    store = Store(args.db)
    try:
        s = store.stats(since=args.since)
    finally:
        store.close()
    if args.markdown:
        lines = ["Stats:" + (f" since {args.since}" if args.since else "")]
        if "period" in s:
            p = s["period"]
            t = p["transitions"]
            lines.append(f"- seen {p['seen']}, surfaced {p['surfaced']}, applied {t.get('applied', 0)}, "
                         f"screens {t.get('screen', 0)}, loops {t.get('loop', 0)}, offers {t.get('offer', 0)}, rejected {t.get('rejected', 0)}, "
                         f"polls {p['polls']} with {p['poll_errors']} errors")
        lines.append(f"- store: {s['postings']} postings, {s['open']} open, {s['comp_found']} with comp, "
                     + ", ".join(f"{k} {v}" for k, v in sorted(s["by_state"].items())))
        print("\n".join(lines))
        return 0
    print(f"postings {s['postings']}, open {s['open']}, with comp {s['comp_found']}")
    print("by state: " + ", ".join(f"{k} {v}" for k, v in sorted(s["by_state"].items())))
    print(f"polls {s['polls']}, errors {s['poll_errors']}")
    if "period" in s:
        p = s["period"]
        print(f"since {p['since']}: seen {p['seen']}, surfaced {p['surfaced']}, " + ", ".join(f"{k} {v}" for k, v in sorted(p["transitions"].items())))
    return 0


def cmd_discover(args):
    data = companies.load(args.companies)
    errors = []
    found = discover.discover(data["companies"], errors=errors)
    print(discover.render(found, errors))
    return 0


def cmd_backup(args):
    target = maintain.backup(args.db, args.to, keep=args.keep)
    print(f"backed up to {target}")
    return 0


def cmd_export(args):
    target, n = maintain.export_status(args.db, args.to)
    print(f"exported {n} status rows to {target}")
    return 0


def cmd_fixture(args):
    target = maintain.fixture(args.kind, args.board, args.out)
    print(f"wrote {target}; run make test to see what moved")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m scraper", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--companies", default=str(DEFAULT_COMPANIES), help="companies file (default data/companies.json; contacts and notes come from data/local/companies.notes.json)")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="postings database (default data/local/postings.db)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="detect the ATS behind a careers URL and add the company")
    a.add_argument("url")
    a.add_argument("--category", required=True, choices=companies.CATEGORIES)
    a.add_argument("--name")
    a.add_argument("--slug")
    a.add_argument("--priority", type=int, default=2, choices=(1, 2, 3))
    a.add_argument("--lead-proof", dest="lead_proof")
    a.add_argument("--kind", choices=companies.KINDS, help="skip detection and set the ATS kind")
    a.add_argument("--board", help="board slug when --kind is given")
    a.set_defaults(fn=cmd_add)

    im = sub.add_parser("import", help="many companies from a text file, one per line: category | careers url | name")
    im.add_argument("file")
    im.add_argument("--priority", type=int, default=2, choices=(1, 2, 3))
    im.add_argument("--manual", action="store_true", help="keep companies with no detectable ATS on the list as manual")
    im.add_argument("--no-guess", dest="no_guess", action="store_true", help="skip trying the company name as a board slug when the URL gives nothing away")
    im.set_defaults(fn=cmd_import)

    ap_ = sub.add_parser("add-posting", help="a posting from a URL or a file")
    ap_.add_argument("src", help="a URL to fetch, or a text file")
    ap_.add_argument("--company", required=True, help="slug on the company list")
    ap_.add_argument("--title", required=True)
    ap_.add_argument("--url", help="the posting URL when src is a file")
    ap_.add_argument("--location", default="")
    ap_.add_argument("--remote", choices=("remote", "hybrid", "onsite", "unclear"))
    ap_.set_defaults(fn=cmd_add_posting)

    c = sub.add_parser("check", help="probe every company's endpoint")
    c.set_defaults(fn=cmd_check)

    s = sub.add_parser("stale", help="companies not reviewed recently")
    s.add_argument("--days", type=int, default=60)
    s.set_defaults(fn=cmd_stale)

    p = sub.add_parser("poll", help="grow the list from the feeds, then fetch every pollable company into the store")
    p.add_argument("--no-discover", dest="no_discover", action="store_true", help="skip the discovery feeds this run")
    p.set_defaults(fn=cmd_poll)

    d = sub.add_parser("digest", help="write this week's digest")
    d.add_argument("--stdout", action="store_true", help="print instead of writing, and do not mark postings as surfaced")
    d.add_argument("--out", default=str(ROOT / "data" / "digests"), help="directory for the digest files (default data/digests)")
    d.set_defaults(fn=cmd_digest)

    sc = sub.add_parser("score", help="rescore every open posting")
    sc.set_defaults(fn=cmd_score)

    m = sub.add_parser("mark", help="record a status change")
    m.add_argument("id", type=int)
    m.add_argument("state", choices=STATES)
    m.add_argument("--note")
    m.add_argument("--letter", help="path of the letter sent")
    m.set_defaults(fn=cmd_mark)

    st = sub.add_parser("stats", help="counts from the store")
    st.add_argument("--since", help="ISO date; adds period counts for the monthly snapshot")
    st.add_argument("--markdown", action="store_true", help="a block to paste into the log")
    st.set_defaults(fn=cmd_stats)

    dv = sub.add_parser("discover", help="companies the discovery feeds keep surfacing")
    dv.set_defaults(fn=cmd_discover)

    bk = sub.add_parser("backup", help="copy postings.db off the disk")
    bk.add_argument("--to", required=True, help="destination directory, ideally not this disk")
    bk.add_argument("--keep", type=int, default=14)
    bk.set_defaults(fn=cmd_backup)

    ex = sub.add_parser("export", help="status history as JSON")
    ex.add_argument("--to", required=True)
    ex.set_defaults(fn=cmd_export)

    fx = sub.add_parser("fixture", help="refresh an adapter fixture from the live endpoint")
    fx.add_argument("kind", choices=sorted(adapters.ADAPTERS))
    fx.add_argument("board")
    fx.add_argument("--out", default=str(ROOT / "scraper" / "tests" / "fixtures"))
    fx.set_defaults(fn=cmd_fixture)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

"""python -m scraper <command>

  add URL        detect the ATS behind a careers URL and add the company
  check          probe every company's endpoint, report dead ones
  stale          companies not reviewed in N days
  poll           fetch every pollable company into postings.db, scoring on the way in
  digest         write this week's digest to data/local/digests, or --stdout
  score          rescore every open posting with the current ruleset
  mark ID STATE  record a status change for a posting
  stats          counts from the store
"""

import argparse
import sys
from pathlib import Path

from . import adapters, companies, digest
from .poll import poll
from .score import load_rules, score
from .store import STATES, Store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPANIES = ROOT / "data" / "local" / "companies.json"
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
        results = poll(store, data["companies"])
    finally:
        store.close()
    errors = 0
    for r in results:
        if r["ok"] is None:
            print(f"skip   {r['slug']:<28} {r['error']}")
        elif r["ok"]:
            print(f"ok     {r['slug']:<28} seen {r['seen']:>3}  new {r['new']:>3}  closed {r['closed']:>3}")
        else:
            errors += 1
            print(f"ERROR  {r['slug']:<28} {r['error']}")
    print(f"{len(results)} companies, {errors} errors")
    return 0


def cmd_digest(args):
    data = companies.load(args.companies)
    names = {c["slug"]: c["name"] for c in data["companies"]}
    rules = load_rules()
    store = Store(args.db)
    try:
        if args.stdout:
            md, _ = digest.build(store, rules, names)
            print(md)
            return 0
        path, n = digest.write(store, rules, Path(args.db).parent / "digests", names)
    finally:
        store.close()
    print(f"wrote {path}, {n} postings surfaced")
    return 0


def cmd_score(args):
    rules = load_rules()
    store = Store(args.db)
    try:
        rows = store.open_postings()
        for row in rows:
            store.set_score(row["id"], score(row, rules))
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
        s = store.stats()
    finally:
        store.close()
    print(f"postings {s['postings']}, open {s['open']}, with comp {s['comp_found']}")
    print("by state: " + ", ".join(f"{k} {v}" for k, v in sorted(s["by_state"].items())))
    print(f"polls {s['polls']}, errors {s['poll_errors']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m scraper", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--companies", default=str(DEFAULT_COMPANIES), help="companies file (default data/local/companies.json)")
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

    c = sub.add_parser("check", help="probe every company's endpoint")
    c.set_defaults(fn=cmd_check)

    s = sub.add_parser("stale", help="companies not reviewed recently")
    s.add_argument("--days", type=int, default=60)
    s.set_defaults(fn=cmd_stale)

    p = sub.add_parser("poll", help="fetch every pollable company into the store")
    p.set_defaults(fn=cmd_poll)

    d = sub.add_parser("digest", help="write this week's digest")
    d.add_argument("--stdout", action="store_true", help="print instead of writing, and do not mark postings as surfaced")
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
    st.set_defaults(fn=cmd_stats)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

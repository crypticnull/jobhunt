"""python -m letters <command>

  brief ID [--lead PROOF]   join the posting, company, blocks and voice rules into one brief
  save ID DRAFT             lint the draft with the letter profile, refuse or file it
  lint DRAFT                just the lint, letter profile

Nothing here sends anything. The generator drafts, Matt decides.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from scraper import companies as companies_mod
from scraper.store import Store

from . import assemble
from .voicelint import check_text, exit_code, load_rules

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPANIES = ROOT / "data" / "companies.json"
DEFAULT_DB = ROOT / "data" / "local" / "postings.db"
DEFAULT_LETTERS = ROOT / "data" / "local" / "letters"


def _load(args, posting_id):
    store = Store(args.db)
    try:
        posting = store.get(posting_id)
    finally:
        store.close()
    if posting is None:
        raise SystemExit(f"no posting with id {posting_id}")
    data = companies_mod.load(args.companies)
    company = next((c for c in data["companies"] if c["slug"] == posting["company_slug"]), None)
    if company is None:
        company = {"slug": posting["company_slug"], "name": posting["company_slug"], "category": None, "priority": None}
    return posting, company


def cmd_brief(args):
    posting, company = _load(args, args.id)
    chosen = assemble.select(posting, company, lead=args.lead)
    md = assemble.render_brief(posting, company, chosen, load_rules())
    if args.stdout:
        print(md)
        return 0
    out_dir = Path(args.letters) / "briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{company['slug']}-{posting['id']}.md"
    path.write_text(md, encoding="utf-8")
    print(f"wrote {path}")
    return 0


def save_draft(posting, company, draft_text, letters_dir, rules, today=None):
    """Lint, then file. Returns (path, findings); path is None when refused."""
    findings = check_text(draft_text, "letter", rules, "draft")
    if findings:
        return None, findings
    today = today or date.today().isoformat()
    letters_dir = Path(letters_dir)
    letters_dir.mkdir(parents=True, exist_ok=True)
    path = letters_dir / f"{company['slug']}-{posting['id']}-{today}.md"
    front = [
        "---",
        f"posting_id: {posting['id']}",
        f"company: {company['slug']}",
        f"title: {posting['title']}",
        f"url: {posting.get('url', '')}",
        f"date: {today}",
        f"voice_rules: {rules.get('version')}",
        "---",
        "",
    ]
    path.write_text("\n".join(front) + draft_text.strip() + "\n", encoding="utf-8")
    return path, []


def cmd_save(args):
    posting, company = _load(args, args.id)
    draft = Path(args.draft).read_text(encoding="utf-8")
    path, findings = save_draft(posting, company, draft, args.letters, load_rules())
    if path is None:
        for f in findings:
            print(f)
        print(f"refused: {len(findings)} finding(s). Fix the draft and save again.", file=sys.stderr)
        return exit_code(findings)
    print(f"saved {path}")
    print(f"when it's sent: python -m scraper mark {posting['id']} applied --letter {path}")
    return 0


def cmd_lint(args):
    findings = check_text(Path(args.draft).read_text(encoding="utf-8"), "letter", load_rules(), args.draft)
    for f in findings:
        print(f)
    print(f"{len(findings)} finding(s)", file=sys.stderr)
    return exit_code(findings)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m letters", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--companies", default=str(DEFAULT_COMPANIES))
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--letters", default=str(DEFAULT_LETTERS), help="where briefs and saved letters go")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("brief", help="write the brief for a posting")
    b.add_argument("id", type=int)
    b.add_argument("--lead", help="proof story id to lead with")
    b.add_argument("--stdout", action="store_true")
    b.set_defaults(fn=cmd_brief)

    s = sub.add_parser("save", help="lint a draft and file it")
    s.add_argument("id", type=int)
    s.add_argument("draft")
    s.set_defaults(fn=cmd_save)

    l = sub.add_parser("lint", help="lint a draft with the letter profile")
    l.add_argument("draft")
    l.set_defaults(fn=cmd_lint)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

"""The weekly digest as a page rather than a wall of markdown.

Same data as `digest.build`, read from the store rather than parsed back out
of the markdown, so the two cannot drift and an old digest can be re-rendered
from the rows that made it. One dated file a week beside the markdown, and it
opens from disk with nothing to install: the styles are inline and there are no
requests to anywhere.

The design is the site's, and not by imitation. Every colour, duration, curve
and measure is read from data/design/tokens.json, the same record
tools/tokens.mjs renders into the stylesheet, so a token edit moves the digest
and the portfolio together. Nothing here writes a hex, a millisecond or a
curve, which is the rule the site is held to in tools/check_tokens.mjs and the
rule this file is held to in the tests.

The interaction is one idea. Every posting is a card in a grid, so the week is
one screen: the title, the company, what it pays and the legs the body hit,
which after the 2026-09-06 split is the honest answer to whether the job has
motion in it. Opening a card spans it across the grid and shows the score
breakdown, the flags, the curriculum hits and the command to mark it. It is a
<details>, so it works with the keyboard, it works with the page printed, and
it works with the script blocked. The script only adds the filters.
"""

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from . import digest as digest_mod

TOKENS = Path(__file__).resolve().parent.parent / "data" / "design" / "tokens.json"

# The order the score prints in, matching the markdown so the two read the same.
RULES_ORDER = ("remote", "comp", "intersection", "title", "company", "curriculum", "freshness", "human", "deductions")


def _tokens(path=None):
    return json.loads(Path(path or TOKENS).read_text(encoding="utf-8"))


def _vars(pairs, indent="  "):
    return "\n".join(f"{indent}--{k}: {v};" for k, v in pairs)


def token_css(t):
    """The same custom properties tools/tokens.mjs writes, from the same record.
    Light on bare :root so an unstamped document has a full palette, the dark
    blocks only redefine, and the reduced column is a decision per movement
    rather than a switch that zeroes everything."""
    motion = [(m["name"], m["default"]) for m in t["motion"]["tokens"]]
    reduced = [(m["name"], m["reduced"]) for m in t["motion"]["tokens"] if m["default"] != m["reduced"]]
    dark = list(t["colour"]["dark"].items())
    return "\n".join([
        ":root {",
        _vars(list(t["colour"]["light"].items()) + list(t["colour"]["plate"].items()) + list(t["grid"].items()) + motion),
        "  color-scheme: light dark;",
        "}",
        "@media (prefers-color-scheme: dark) {",
        '  :root:not([data-theme="light"]) {',
        _vars(dark, "    "),
        "  }",
        "}",
        ':root[data-theme="dark"] {',
        _vars(dark),
        "  color-scheme: dark;",
        "}",
        "@media (prefers-reduced-motion: reduce) {",
        '  :root:not([data-motion="full"]) {',
        _vars(reduced, "    "),
        "  }",
        "}",
    ])


PAGE_CSS = """
  *, *::before, *::after { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font: 16px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    -webkit-text-size-adjust: 100%;
  }
  .wrap { max-width: var(--content-max); margin: 0 auto; padding: var(--gutter); }
  a { color: var(--marker); }
  h1, h2, h3 { line-height: 1.15; margin: 0; font-weight: 600; }
  h1 { font-size: 1.75rem; letter-spacing: -0.01em; }
  h2 { font-size: 1.15rem; margin: 2.5rem 0 0.75rem; }
  .sub { color: var(--muted); margin: 0.5rem 0 0; max-width: var(--measure); }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .rule { border: 0; border-top: 1px solid var(--rule); margin: 1.5rem 0; }

  /* The filters. Without the script every card shows, which is the state the
     page is written in, so a blocked script costs the filters and nothing else. */
  .filters { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1.25rem 0 0; }
  .filters button {
    font: inherit; font-size: 0.85rem;
    color: var(--muted); background: var(--field);
    border: 1px solid var(--rule); border-radius: 999px;
    padding: 0.3rem 0.8rem; cursor: pointer;
    transition: color var(--respond) var(--ease-out), border-color var(--respond) var(--ease-out);
  }
  .filters button:hover { color: var(--ink); }
  .filters button[aria-pressed="true"] { color: var(--marker); border-color: var(--marker); }
  .filters .n { color: var(--muted); font-variant-numeric: tabular-nums; }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr));
    gap: var(--grid-gap);
    margin-top: 1rem;
  }

  .card {
    border: 1px solid var(--rule);
    background: var(--field);
    border-radius: 2px;
    transition: border-color var(--respond) var(--ease-out);
  }
  .card:hover { border-color: var(--marker); }
  .card { display: flex; flex-direction: column; }
  /* display on a class beats the hidden attribute, so the filter stopped
     hiding anything the moment the card became a flex column. */
  .card[hidden] { display: none; }
  .card > summary {
    cursor: pointer;
    padding: 0.9rem 1rem;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    flex: 1;
  }
  .card > summary > .where { margin-top: auto; padding-top: 0.2rem; }
  .card > summary::-webkit-details-marker { display: none; }
  .card > summary:focus-visible { outline: 2px solid var(--marker); outline-offset: 2px; }
  /* Open spans the row, so the detail has the measure to be read at and the
     grid keeps its shape around it. */
  .card[open] { grid-column: 1 / -1; border-color: var(--marker); }

  .who { display: flex; gap: 0.5rem; align-items: baseline; justify-content: space-between; }
  .role { font-weight: 600; }
  .at { color: var(--muted); font-size: 0.9rem; }
  .score {
    font-size: 0.8rem; font-variant-numeric: tabular-nums;
    color: var(--marker); border: 1px solid var(--marker);
    border-radius: 999px; padding: 0.05rem 0.5rem; flex: none;
  }
  .money { font-size: 0.9rem; font-variant-numeric: tabular-nums; }
  .money.none { color: var(--muted); }
  .where { color: var(--muted); font-size: 0.8rem; }

  .legs { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .leg {
    font-size: 0.7rem; letter-spacing: 0.02em; text-transform: uppercase;
    border: 1px solid var(--rule); border-radius: 2px;
    padding: 0.1rem 0.4rem; color: var(--muted);
  }
  /* The leg that says the job has motion in it, which is the one worth seeing
     from across the room. */
  .leg.product-motion { color: var(--marker); border-color: var(--marker); }
  .leg.motion { color: var(--muted); border-style: dashed; }

  .detail {
    padding: 0 1rem 1rem;
    display: grid;
    gap: 1.25rem 2rem;
    grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
    align-items: start;
  }
  .detail p { margin: 0; }
  .detail > * { min-width: 0; }
  .detail h3 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }
  .bars { display: grid; gap: 0.25rem; max-width: 26rem; }
  .bar { display: grid; grid-template-columns: 7rem 1fr 2.5rem; gap: 0.5rem; align-items: center; font-size: 0.8rem; }
  .bar span:first-child { color: var(--muted); }
  .bar i { display: block; height: 0.5rem; background: var(--blueprint); border-radius: 1px; }
  .bar i.neg { background: var(--rule); }
  .bar b { font-weight: 400; font-variant-numeric: tabular-nums; text-align: right; }
  .notes { display: grid; gap: 0.4rem; align-content: start; font-size: 0.9rem; max-width: var(--measure); }
  .act { display: grid; gap: 0.5rem; align-content: start; font-size: 0.9rem; }
  .notes .flag { color: var(--marker); }
  .cmd {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.8rem; color: var(--muted);
    background: var(--paper); border: 1px solid var(--rule);
    padding: 0.4rem 0.6rem; overflow-x: auto;
  }

  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
  th, td { text-align: left; padding: 0.35rem 0.6rem 0.35rem 0; border-bottom: 1px solid var(--rule); vertical-align: top; }
  th { color: var(--muted); font-weight: 400; font-size: 0.8rem; }
  td.n { font-variant-numeric: tabular-nums; text-align: right; padding-right: 1rem; white-space: nowrap; }
  .scroll { overflow-x: auto; }
  .quiet { color: var(--muted); font-size: 0.9rem; }
  footer { margin: 3rem 0 1rem; color: var(--muted); font-size: 0.8rem; }

  @media print {
    .filters { display: none; }
    .card { break-inside: avoid; border-color: var(--rule); }
  }
"""

FILTER_JS = """
  // Progressive enhancement only. The page is complete without it: every card
  // is in the document and shown, and this adds the filters and nothing else.
  const grid = document.querySelector('.grid');
  const buttons = document.querySelectorAll('.filters button');
  for (const b of buttons) {
    b.addEventListener('click', () => {
      for (const o of buttons) o.setAttribute('aria-pressed', String(o === b));
      const want = b.dataset.pile;
      for (const card of grid.querySelectorAll('.card')) {
        const show = want === 'all' || card.dataset.pile === want;
        card.hidden = !show;
        if (!show) card.open = false;
      }
    });
  }
"""


def _esc(v):
    return html.escape(str(v if v is not None else ""), quote=True)


def _card(row, companies, pile):
    detail = json.loads(row["score_json"] or "{}")
    company = (companies or {}).get(row["company_slug"]) or {}
    name = company.get("name", row["company_slug"])
    tier = company.get("tier")
    legs = detail.get("legs_hit") or []
    comp = digest_mod._comp(row)
    money = f'<p class="money{"" if row["comp_found"] else " none"}">{_esc(comp)}</p>'
    where = " · ".join(x for x in [row["remote_class"], row["location"] or "", f"tier {tier}" if tier else ""] if x)

    sc = {r["rule"]: r for r in detail.get("rules", [])}
    widest = max([abs(sc[k]["value"]) for k in sc] or [1]) or 1
    bars = "".join(
        f'<div class="bar"><span>{_esc(k)}</span>'
        f'<i class="{"neg" if sc[k]["value"] < 0 else ""}" style="width:{round(abs(sc[k]["value"]) / widest * 100)}%"></i>'
        f'<b>{sc[k]["value"]:+d}</b></div>'
        for k in RULES_ORDER if k in sc
    )

    notes = []
    for f in detail.get("flags") or []:
        notes.append(f'<p class="flag">{_esc(f)}</p>')
    if detail.get("curriculum"):
        notes.append(f'<p>Curriculum: {_esc(", ".join(detail["curriculum"]))}</p>')
    if detail.get("proof_lead"):
        notes.append(f'<p>Lead with {_esc(detail["proof_lead"])}</p>')
    pay = company.get("pay_model", "unknown")
    if pay == "location-adjusted":
        notes.append('<p class="flag">Pay is location-adjusted, so the move north cuts it. Ask on the first call.</p>')
    elif pay == "unknown":
        notes.append("<p>Pay model unknown. Ask whether pay is the same wherever you live.</p>")
    if company.get("hq"):
        notes.append(f'<p>HQ {_esc(company["hq"])}</p>')
    notes.append(f'<p>First seen {_esc(row["first_seen"][:10])}</p>')

    return f"""<details class="card" data-pile="{_esc(pile)}">
<summary>
<span class="who"><span><span class="role">{_esc(row['title'])}</span> <span class="at">{_esc(name)}</span></span><span class="score">{round(row['score'])}</span></span>
{money}
<span class="legs">{''.join(f'<span class="leg {_esc(l)}">{_esc(l)}</span>' for l in legs) or '<span class="leg">no legs</span>'}</span>
<span class="where">{_esc(where)}</span>
</summary>
<div class="detail">
<div><h3>Score</h3><div class="bars">{bars}</div></div>
<div class="notes">{''.join(notes)}</div>
<div class="act"><p><a href="{_esc(row['url'])}" rel="noreferrer">Open the posting</a></p>
<p class="cmd">python -m scraper mark {_esc(row['id'])} reviewed</p></div>
</div>
</details>"""


def _table(rows, headers):
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f'<td class="n">{_esc(c)}</td>' if isinstance(c, int) else f"<td>{_esc(c)}</td>" for c in r) + "</tr>"
        for r in rows
    )
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render(store, rules, companies=None, now=None, tokens=None):
    now = now or datetime.now(timezone.utc)
    week = digest_mod._week(now)
    piles = digest_mod.select(store, rules, companies, now)
    review = piles["overflow"] + piles["review"]
    stamp = digest_mod.code_stamp()

    cards = [_card(r, companies, "apply") for r in piles["apply"]] + [_card(r, companies, "review") for r in review]
    since = digest_mod._since(now)
    drops = store.drop_counts(since)
    by_source = store.new_by_source(since)

    head = [
        f"{len(piles['apply'])} to apply", f"{len(review)} to review",
        f"ruleset {rules['version']}",
    ]
    filters = (
        f'<button data-pile="all" aria-pressed="true">Everything <span class="n">{len(cards)}</span></button>'
        f'<button data-pile="apply" aria-pressed="false">Apply <span class="n">{len(piles["apply"])}</span></button>'
        f'<button data-pile="review" aria-pressed="false">Review <span class="n">{len(review)}</span></button>'
    )

    tail = []
    if drops:
        tail += ["<h2>Logged, by reason</h2>",
                 _table(sorted(((n, r) for r, n in drops.items()), reverse=True), ["", "Reason"])]
    if by_source:
        tail += ["<h2>New listings by source</h2>",
                 _table(sorted(((n, s) for s, n in by_source.items()), reverse=True), ["", "Source"])]
    health = digest_mod.source_health(store, since, companies=companies)
    tail += ["<h2>Source health</h2>",
             ('<ul class="quiet">' + "".join(f"<li>{_esc(p)}</li>" for p in health) + "</ul>") if health
             else '<p class="quiet">All sources answered.</p>']

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Digest {week}</title>
<style>
{token_css(tokens or _tokens())}
{PAGE_CSS}</style>
</head>
<body>
<main class="wrap">
<h1>Digest, week {_esc(week)}</h1>
<p class="sub">{_esc(' · '.join(head))}{f'<br><span class="mono">built from {_esc(stamp)}</span>' if stamp else ''}</p>
<div class="filters">{filters}</div>
<div class="grid">
{chr(10).join(cards) if cards else '<p class="quiet">Nothing this week.</p>'}
</div>
<hr class="rule">
{''.join(tail)}
<footer>Generated by scraper/digest_html.py from the same rows as {_esc(week)}.md. Nothing here is sent anywhere.</footer>
</main>
<script>
{FILTER_JS}</script>
</body>
</html>
"""


def write(store, rules, path_dir, companies=None, now=None):
    """The dated page beside the dated markdown, so the week is a file rather
    than a message that scrolls away."""
    now = now or datetime.now(timezone.utc)
    path = Path(path_dir) / f"{digest_mod._week(now)}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(store, rules, companies, now), encoding="utf-8")
    return path

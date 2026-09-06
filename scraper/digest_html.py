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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import digest as digest_mod

TOKENS = Path(__file__).resolve().parent.parent / "data" / "design" / "tokens.json"

# The order the score prints in, from the markdown, so the two read the same
# and neither can quietly start leaving a rule out.
RULES_ORDER = digest_mod.SCORE_ORDER
# The two rules worth seeing in the strip without reading a number.
HOT = {"intersection", "deductions"}


def _dateline(now):
    """The week said as dates rather than as a number. 2026-W36 is the thirty
    sixth week of the calendar year, which is correct and is also the first
    digest ever run, so a heading reading "Week 36" invites the reader to think
    something is counting wrong. The ISO week stays in the stamp and the file
    name, where it sorts and is unambiguous."""
    monday = now - timedelta(days=now.isoweekday() - 1)
    months = ("January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December")
    start = f"{monday.day} {months[monday.month - 1]}"
    end = f"{now.day} {months[now.month - 1]} {now.year}"
    return f"{start} to {end}"


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
    typ = list(t.get("type", {}).items())
    reduced = [(m["name"], m["reduced"]) for m in t["motion"]["tokens"] if m["default"] != m["reduced"]]
    dark = list(t["colour"]["dark"].items())
    return "\n".join([
        ":root {",
        _vars(list(t["colour"]["light"].items()) + list(t["colour"]["plate"].items()) + typ + list(t["grid"].items()) + motion),
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
    font-family: var(--body);
    font-size: var(--step-0);
    line-height: var(--leading-body);
    -webkit-text-size-adjust: 100%;
  }
  .wrap { max-width: var(--content-max); margin: 0 auto; padding: var(--gutter) var(--gutter) 5rem; }
  a { color: var(--marker); }
  h1, h2, .role, .tab, .n { font-family: var(--display); }
  h1 { font-size: var(--step-3); font-weight: var(--display-weight); letter-spacing: var(--display-tracking); line-height: var(--leading-tight); margin: 0; text-wrap: balance; }
  .stamp { font-family: var(--mono); font-size: var(--step-xx); color: var(--muted); letter-spacing: var(--label-tracking); text-transform: uppercase; margin: 0 0 .5rem; }
  .lede { font-size: var(--step-1); color: var(--muted); max-width: 62ch; margin: .75rem 0 0; }
  .lede b { color: var(--ink); font-weight: 600; }
  .lede b.warn { color: var(--marker); }

  /* The week in numbers. These are the decision, not tiles for their own sake. */
  .tally { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 1px; background: var(--rule); border: 1px solid var(--rule); margin: 2rem 0 0; }
  .tally div { background: var(--paper); padding: .9rem 1rem; }
  .tally .n { font-family: var(--mono); font-size: 1.7rem; font-weight: 500; line-height: 1; font-variant-numeric: tabular-nums; display: block; }
  .tally .k { font-family: var(--mono); font-size: var(--step-xx); text-transform: uppercase; letter-spacing: var(--label-tracking); color: var(--muted); margin-top: .4rem; display: block; }
  .tally .hot .n { color: var(--marker); }

  .key { display: flex; flex-wrap: wrap; gap: 1rem; margin-top: .75rem; font-family: var(--mono); font-size: var(--step-xx); color: var(--muted); align-items: center; }
  .key b { font-weight: 400; display: inline-flex; align-items: center; gap: .35rem; }
  .key i { width: 1.4rem; height: 4px; display: inline-block; }

  .bar { display: flex; flex-wrap: wrap; gap: 1.25rem; align-items: flex-end; margin: 2rem 0 .25rem; padding-bottom: 1rem; border-bottom: 1px solid var(--rule); }
  .grp { display: flex; flex-direction: column; gap: .4rem; }
  .grp > span { font-family: var(--mono); font-size: var(--step-xx); text-transform: uppercase; letter-spacing: var(--label-tracking); color: var(--muted); }
  .tabs { display: flex; flex-wrap: wrap; gap: .35rem; }
  .tab { font-size: var(--step-x); font-weight: 500; color: var(--muted); background: transparent; border: 1px solid var(--rule); padding: .3rem .7rem; cursor: pointer; font-family: var(--display); }
  .tab:hover { color: var(--ink); border-color: var(--muted); }
  .tab[aria-pressed="true"] { color: var(--paper); background: var(--ink); border-color: var(--ink); }
  .tab .c { font-family: var(--mono); font-size: var(--step-xx); opacity: .7; margin-left: .35rem; }
  select { font-family: var(--display); font-size: var(--step-x); padding: .3rem .5rem; background: var(--paper); color: var(--ink); border: 1px solid var(--rule); }
  .spacer { flex: 1; }
  .picked { font-family: var(--mono); font-size: var(--step-x); color: var(--muted); display: flex; align-items: center; gap: .6rem; }
  .picked b { color: var(--marker); font-weight: 500; }
  .picked button { font-family: var(--display); font-size: var(--step-x); padding: .3rem .7rem; background: var(--marker); color: var(--paper); border: 0; cursor: pointer; }
  .picked button[disabled] { background: var(--rule); color: var(--muted); cursor: default; }

  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(20.5rem, 1fr)); gap: 1rem; margin-top: 1.5rem; }
  .card { background: var(--field); border: 1px solid var(--rule); display: flex; flex-direction: column; transition: border-color var(--respond) var(--ease-out); }
  /* display on a class beats the hidden attribute, so the filter would stop
     filtering the moment the card became a flex column. */
  .card[hidden] { display: none; }
  .card:hover { border-color: var(--muted); }
  .card[open] { grid-column: 1 / -1; border-color: var(--ink); }
  .card.on { border-color: var(--marker); box-shadow: inset 3px 0 0 var(--marker); }
  summary { list-style: none; cursor: pointer; padding: .85rem .95rem; display: flex; flex-direction: column; gap: .55rem; flex: 1; }
  summary::-webkit-details-marker { display: none; }
  summary:focus-visible { outline: 2px solid var(--marker); outline-offset: -2px; }
  .top { display: flex; gap: .75rem; align-items: flex-start; justify-content: space-between; }
  .role { font-size: var(--step-0); font-weight: 600; line-height: 1.25; letter-spacing: -.01em; text-wrap: balance; }
  .co { font-family: var(--mono); font-size: var(--step-xx); color: var(--muted); display: block; margin-top: .25rem; }
  .pts { font-family: var(--mono); font-size: var(--step-1); font-weight: 500; font-variant-numeric: tabular-nums; line-height: 1; flex: none; }
  .pay { font-family: var(--mono); font-size: var(--step-x); font-variant-numeric: tabular-nums; }
  .pay.none { color: var(--muted); font-style: italic; font-family: var(--body); }
  /* The score as a strip, so a screenful of them compare without reading a number. */
  .strip { display: flex; height: 4px; background: var(--rule); overflow: hidden; }
  .strip i { display: block; height: 100%; }
  .legs { display: flex; flex-wrap: wrap; gap: .25rem; }
  .leg { font-family: var(--mono); font-size: var(--step-xx); text-transform: uppercase; letter-spacing: .05em; padding: .12rem .35rem; border: 1px solid var(--rule); color: var(--muted); }
  .leg.pm { color: var(--marker); border-color: var(--marker); font-weight: 500; }
  .leg.mo { border-style: dashed; }
  .meta { font-family: var(--mono); font-size: var(--step-xx); color: var(--muted); margin-top: auto; padding-top: .15rem; display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
  .meta .where { flex: 1; min-width: 0; }
  .meta .pile { flex: none; color: var(--paper); background: var(--ink); padding: .08rem .4rem; letter-spacing: .06em; text-transform: uppercase; }

  .detail { padding: 1rem 0; display: grid; gap: 1.1rem 2rem; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); align-items: start; border-top: 1px solid var(--rule); margin: 0 .95rem; }
  .detail h3 { font-family: var(--mono); font-size: var(--step-xx); text-transform: uppercase; letter-spacing: var(--label-tracking); color: var(--muted); margin: 0 0 .5rem; font-weight: 400; }
  .rows { display: grid; gap: .3rem; }
  .row { display: grid; grid-template-columns: 6.5rem 1fr 2.4rem; gap: .6rem; align-items: center; font-family: var(--mono); font-size: var(--step-xx); }
  .row span:first-child { color: var(--muted); }
  .row i { display: block; height: 6px; background: var(--blueprint); }
  .row i.neg { background: var(--marker); }
  .row b { font-weight: 400; font-variant-numeric: tabular-nums; text-align: right; }
  .notes { display: grid; gap: .45rem; font-size: var(--step-x); max-width: 44ch; }
  .notes p { margin: 0; }
  .notes .fl { color: var(--marker); }
  .act { display: grid; gap: .6rem; align-content: start; }
  .act a { font-family: var(--display); font-size: var(--step-x); font-weight: 500; }
  .pick { display: flex; gap: .5rem; align-items: center; font-family: var(--mono); font-size: var(--step-x); color: var(--muted); cursor: pointer; }
  .pick input { accent-color: var(--marker); width: 1rem; height: 1rem; }
  .idtag { font-family: var(--mono); font-size: var(--step-xx); color: var(--muted); }
  .empty { font-family: var(--mono); font-size: var(--step-x); color: var(--muted); padding: 3rem 0; text-align: center; grid-column: 1 / -1; }

  table { border-collapse: collapse; width: 100%; font-size: var(--step-x); }
  th, td { text-align: left; padding: .35rem .6rem .35rem 0; border-bottom: 1px solid var(--rule); vertical-align: top; }
  th { color: var(--muted); font-weight: 400; font-size: var(--step-xx); font-family: var(--mono); text-transform: uppercase; letter-spacing: var(--label-tracking); }
  td.n { font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right; padding-right: 1rem; white-space: nowrap; }
  .scroll { overflow-x: auto; }
  .quiet { color: var(--muted); font-size: var(--step-x); }
  h2 { font-size: var(--step-2); font-weight: var(--display-weight); letter-spacing: var(--display-tracking); margin: 2.5rem 0 .75rem; }
  footer { margin: 3.5rem 0 1rem; padding-top: 1.25rem; border-top: 1px solid var(--rule); color: var(--muted); font-size: var(--step-x); max-width: 62ch; }

  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
  @media print { .bar, .picked, .key { display: none; } .card { break-inside: avoid; } }
"""

FILTER_JS = """
  // Progressive enhancement only. Every card is already in the document and
  // shown; this reorders and hides the nodes that are there, and remembers the
  // picks. Nothing here builds markup, so there is one place a card is written
  // and no posting title ever reaches a script tag.
  const grid = document.getElementById("grid");
  const cards = [...grid.querySelectorAll(".card")];
  const KEY = "picks-" + document.body.dataset.week;
  let picked = new Set();
  try { picked = new Set(JSON.parse(localStorage.getItem(KEY) || "[]")); } catch (e) {}

  const num = (el, k) => Number(el.dataset[k]);
  const SORTS = {
    score: (a, b) => num(b, "score") - num(a, "score"),
    comp: (a, b) => num(b, "top") - num(a, "top"),
    fresh: (a, b) => b.dataset.seen.localeCompare(a.dataset.seen) || num(b, "score") - num(a, "score"),
    tier: (a, b) => num(a, "tier") - num(b, "tier") || num(b, "score") - num(a, "score"),
    co: (a, b) => a.dataset.co.localeCompare(b.dataset.co) || num(b, "score") - num(a, "score"),
  };
  let filter = "all", sort = "score";
  const keep = (c) => filter === "all"
    || (filter === "pm" ? c.dataset.pm === "1"
      : filter === "comp" ? num(c, "top") > 0
      : c.dataset.pile === filter);

  function draw() {
    let shown = 0;
    for (const c of cards) {
      const on = keep(c);
      c.hidden = !on;
      if (!on) c.open = false;
      if (on) shown++;
    }
    for (const c of [...cards].filter(keep).sort(SORTS[sort])) grid.appendChild(c);
    document.getElementById("none").hidden = shown > 0;
  }

  function save() {
    document.getElementById("np").textContent = picked.size;
    document.getElementById("copy").disabled = picked.size === 0;
    try { localStorage.setItem(KEY, JSON.stringify([...picked])); } catch (e) {}
  }

  for (const box of grid.querySelectorAll("input[data-pick]")) {
    const id = Number(box.dataset.pick);
    const card = box.closest(".card");
    if (picked.has(id)) { box.checked = true; card.classList.add("on"); }
    box.addEventListener("change", () => {
      box.checked ? picked.add(id) : picked.delete(id);
      card.classList.toggle("on", box.checked);
      save();
    });
  }

  document.getElementById("tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    for (const o of document.querySelectorAll("#tabs .tab")) o.setAttribute("aria-pressed", String(o === b));
    filter = b.dataset.f;
    draw();
  });
  document.getElementById("sort").addEventListener("change", (e) => { sort = e.target.value; draw(); });
  document.getElementById("copy").addEventListener("click", async (e) => {
    const txt = [...picked].join(" ");
    try { await navigator.clipboard.writeText(txt); e.target.textContent = "Copied"; }
    catch (err) { e.target.textContent = txt; }
    setTimeout(() => { e.target.textContent = "Copy ids"; }, 1600);
  });
  draw();
  save();
"""


def _esc(v):
    return html.escape(str(v if v is not None else ""), quote=True)


def _card(row, companies, pile):
    """One posting as a card. Everything the markdown entry prints reaches here,
    including the score parts, because both surfaces read SCORE_ORDER and
    neither gets to leave a rule out."""
    detail = json.loads(row["score_json"] or "{}")
    company = (companies or {}).get(row["company_slug"]) or {}
    name = company.get("name", row["company_slug"])
    tier = company.get("tier")
    legs = detail.get("legs_hit") or []
    parts = {r["rule"]: r["value"] for r in detail.get("rules", []) if r["rule"] in RULES_ORDER}
    money = digest_mod._comp(row) if row["comp_found"] else None

    total = sum(v for v in parts.values() if v > 0) or 1
    strip = "".join(
        f'<i style="width:{parts[k] / total * 100:.1f}%;background:'
        f'{"var(--marker)" if k in HOT else "var(--blueprint)"}"></i>'
        for k in RULES_ORDER if parts.get(k, 0) > 0
    )
    widest = max([abs(v) for v in parts.values()] or [1]) or 1
    rows = "".join(
        f'<div class="row"><span>{_esc(k)}</span>'
        f'<i class="{"neg" if parts[k] < 0 else ""}" style="width:{abs(parts[k]) / widest * 100:.0f}%"></i>'
        f'<b>{parts[k]:+d}</b></div>'
        for k in RULES_ORDER if k in parts
    )
    chips = "".join(
        f'<span class="leg {"pm" if l == "product-motion" else "mo" if l == "motion" else ""}">{_esc(l)}</span>'
        for l in legs
    ) or '<span class="leg">no legs</span>'

    notes = [(1, f) for f in (detail.get("flags") or [])]
    pay = company.get("pay_model", "unknown")
    if pay == "location-adjusted":
        notes.append((1, "Pay is location-adjusted, so the move north cuts it. Ask on the first call."))
    elif pay == "unknown":
        notes.append((0, "Pay model unknown. Ask whether pay is the same wherever you live."))
    if detail.get("curriculum"):
        notes.append((0, "Curriculum: " + ", ".join(detail["curriculum"])))
    if detail.get("proof_lead"):
        notes.append((0, f"Lead with {detail['proof_lead']}"))
    if company.get("hq"):
        notes.append((0, f"HQ {company['hq']}"))
    notes.append((0, f"First seen {row['first_seen'][:10]}"))
    note_html = "".join(f'<p class="{"fl" if hot else ""}">{_esc(t)}</p>' for hot, t in notes)

    return f"""<details class="card" data-id="{row['id']}" data-pile="{_esc(pile)}" data-score="{round(row['score'] or 0)}"\
 data-top="{row['comp_max'] if row['comp_found'] and row['comp_max'] else -1}" data-seen="{_esc(row['first_seen'][:10])}"\
 data-tier="{tier or 9}" data-co="{_esc(name)}" data-pm="{'1' if 'product-motion' in legs else '0'}">
<summary>
<div class="top"><div><span class="role">{_esc(row['title'])}</span><span class="co">{_esc(name)}{f' &middot; tier {tier}' if tier else ''}</span></div><span class="pts">{round(row['score'] or 0)}</span></div>
<div class="strip">{strip}</div>
<div class="pay{'' if money else ' none'}">{_esc(money or 'no comp posted')}</div>
<div class="legs">{chips}</div>
<div class="meta"><span class="where">{_esc(row['location'] or row['remote_class'] or '')}</span>{'<span class="pile">apply</span>' if pile == 'apply' else ''}</div>
</summary>
<div class="detail">
<div><h3>How it scored</h3><div class="rows">{rows}</div></div>
<div><h3>What to know</h3><div class="notes">{note_html}</div></div>
<div><h3>Do</h3><div class="act">
<label class="pick"><input type="checkbox" data-pick="{row['id']}"> Pick for a letter</label>
<a href="{_esc(row['url'])}" target="_blank" rel="noreferrer noopener">Open the posting &rarr;</a>
<span class="idtag">id {row['id']}</span>
</div></div>
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
    since = digest_mod._since(now)
    piles = digest_mod.select(store, rules, companies, now)
    review = piles["overflow"] + piles["review"]
    def facts(r):
        d = json.loads(r["score_json"] or "{}")
        return {"legs": d.get("legs_hit") or [], "money": bool(r["comp_found"])}
    seen = [(r, "apply") for r in piles["apply"]] + [(r, "review") for r in review]
    cards = [_card(r, companies, pile) for r, pile in seen]
    facts_all = [facts(r) for r, _ in seen]
    stamp = digest_mod.code_stamp()

    new_total = sum(store.new_by_source(since).values())
    motion = sum(1 for f in facts_all if "product-motion" in f["legs"])
    nocomp = sum(1 for f in facts_all if not f["money"])
    n_apply, n_review = len(piles["apply"]), len(review)
    apply_motion = sum(1 for (r, pile), f in zip(seen, facts_all) if pile == "apply" and "product-motion" in f["legs"])

    # The one sentence worth putting at the top is whichever is true this week.
    if not cards:
        lede = "Nothing cleared the gates this week."
    elif apply_motion:
        lede = (f'Forty-odd postings cleared the gates out of <b>{new_total:,}</b> seen this week. The legs on each card '
                f'are what the body actually asked for, so <b class="warn">product-motion</b> is the one to scan for. '
                f'<b>{apply_motion} of the {n_apply} in Apply have it.</b>')
    else:
        lede = (f'<b>{len(cards)}</b> postings cleared the gates out of <b>{new_total:,}</b> seen this week. The legs on each '
                f'card are what the body actually asked for, so <b class="warn">product-motion</b> is the one to scan for. '
                f'<b>None of the {n_apply} in Apply have it.</b>')

    tabs = "".join(
        f'<button class="tab" data-f="{f}" aria-pressed="{"true" if f == "all" else "false"}">{label}<span class="c">{n}</span></button>'
        for f, label, n in [("all", "Everything", len(cards)), ("apply", "Apply", n_apply),
                            ("review", "Review", n_review), ("pm", "Product motion", motion),
                            ("comp", "Comp posted", len(cards) - nocomp)])

    tail = []
    drops = store.drop_counts(since)
    if drops:
        tail += ["<h2>Logged, by reason</h2>",
                 _table(sorted(((n, r) for r, n in drops.items()), reverse=True)[:20], ["", "Reason"])]
    by_source = store.new_by_source(since)
    if by_source:
        tail += ["<h2>New listings by source</h2>",
                 _table(sorted(((n, src) for src, n in by_source.items()), reverse=True), ["", "Source"])]
    health = digest_mod.source_health(store, since, companies=companies)
    tail += ["<h2>Source health</h2>",
             ('<ul class="quiet">' + "".join(f"<li>{_esc(p)}</li>" for p in health) + "</ul>") if health
             else '<p class="quiet">All sources answered.</p>']

    script = FILTER_JS

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Shortlist, {_esc(_dateline(now).split(' to ')[1])}</title>
<style>
{token_css(tokens or _tokens())}
{PAGE_CSS}</style>
</head>
<body data-week="{_esc(week)}">
<main class="wrap">
<p class="stamp">{_esc(_dateline(now))} &middot; {_esc(week)} &middot; ruleset {_esc(rules['version'])}{f' &middot; built from {_esc(stamp)}' if stamp else ''}</p>
<h1>Shortlist, the week to {_esc(_dateline(now).split(' to ')[1])}</h1>
<p class="lede">{lede}</p>

<div class="tally">
  <div><span class="n">{n_apply}</span><span class="k">to apply</span></div>
  <div><span class="n">{n_review}</span><span class="k">to review</span></div>
  <div class="hot"><span class="n">{motion}</span><span class="k">with product motion</span></div>
  <div><span class="n">{nocomp}</span><span class="k">no comp posted</span></div>
</div>
<div class="key">
  <span>Score strip</span>
  <b><i style="background:var(--blueprint)"></i>remote, pay, title, company, curriculum, freshness</b>
  <b><i style="background:var(--marker)"></i>the intersection, and anything deducted</b>
</div>

<div class="bar">
  <div class="grp"><span>show</span><div class="tabs" id="tabs">{tabs}</div></div>
  <div class="grp"><span>sort</span>
    <select id="sort">
      <option value="score">Score, high first</option>
      <option value="comp">Pay, high first</option>
      <option value="fresh">Newest first</option>
      <option value="tier">Company tier</option>
      <option value="co">Company A to Z</option>
    </select>
  </div>
  <div class="spacer"></div>
  <div class="picked"><span><b id="np">0</b> picked</span><button id="copy" disabled>Copy ids</button></div>
</div>

<div class="grid" id="grid">
{chr(10).join(cards)}
</div>
<p class="empty" id="none"{'' if not cards else ' hidden'}>Nothing matches that.</p>
{''.join(tail)}
<footer>Tick the ones worth a letter and the ids travel with you. Picks stay in this browser only, and nothing on this page sends anything anywhere. Colour, type and motion all come from data/design/tokens.json, so this page and the site move together.</footer>
</main>
<script>
{script}</script>
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

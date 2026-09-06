"""A letter and a resume as pages, set in the same identity as everything else.

Both are print-first. A cover letter is read by a person who may paste it into a
form, print it, or open the PDF on a phone, and a resume is read by a parser
before it is read by anyone. So the markup is plain and semantic, the text is
text rather than an image of text, and neither page loads anything from
anywhere. Colour, type and measure come from data/design/tokens.json through
pipeline.design, so a token edit moves these with the site.

Neither page is dark. A letter that renders dark because the reader's laptop is
dark prints as a black rectangle or not at all, and paper is paper.

The words are Matt's. This file decides nothing about them: the letter body is
whatever draft he saved, and the resume prints only sections that have content.
An empty section prints as nothing, never as a placeholder, for the same reason
the site never fakes words into a slot it has no record for.
"""

import re
from pathlib import Path

from pipeline import design
from .assemble import read_record

ROOT = Path(__file__).resolve().parent.parent
PROOF = ROOT / "data" / "proof"

PAGE_CSS = """
  *, *::before, *::after { box-sizing: border-box; }
  html { background: var(--field); }
  body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: var(--body);
    font-size: var(--step-0);
    line-height: var(--leading-body);
  }
  /* One sheet, centred, with the margins a printer would give it. On screen it
     reads as a page rather than as a web layout, which is what it is. */
  .sheet {
    max-width: 46rem;
    margin: 2rem auto;
    padding: 3.5rem 3.25rem;
    background: var(--paper);
    border: 1px solid var(--rule);
  }
  a { color: var(--marker); }

  .head { border-bottom: 1px solid var(--ink); padding-bottom: .9rem; margin-bottom: 2rem; }
  .who {
    font-family: var(--display);
    font-size: var(--step-2);
    font-weight: var(--display-weight);
    letter-spacing: var(--display-tracking);
    line-height: var(--leading-tight);
    margin: 0;
  }
  .what { font-family: var(--mono); font-size: var(--step-x); color: var(--muted); margin: .4rem 0 0; }
  .reach {
    font-family: var(--mono); font-size: var(--step-xx); color: var(--muted);
    margin: .6rem 0 0; display: flex; flex-wrap: wrap; gap: .25rem 1rem;
  }

  h2 {
    font-family: var(--mono); font-size: var(--step-xx); font-weight: 400;
    text-transform: uppercase; letter-spacing: var(--label-tracking);
    color: var(--muted); margin: 2rem 0 .6rem;
    border-bottom: 1px solid var(--rule); padding-bottom: .3rem;
  }
  p { margin: 0 0 1rem; max-width: var(--measure); }
  .body p:last-child { margin-bottom: 0; }

  .item { margin-bottom: 1.1rem; break-inside: avoid; }
  .item:last-child { margin-bottom: 0; }
  .line { display: flex; gap: .75rem; align-items: baseline; justify-content: space-between; }
  .item h3 {
    font-family: var(--display); font-size: var(--step-0); font-weight: 600;
    letter-spacing: -.01em; margin: 0; line-height: 1.3;
  }
  .when { font-family: var(--mono); font-size: var(--step-xx); color: var(--muted); flex: none; }
  .org { font-family: var(--mono); font-size: var(--step-xx); color: var(--muted); margin: .15rem 0 .35rem; }
  .item p { margin: 0; font-size: var(--step-x); }
  .item ul { margin: .3rem 0 0; padding-left: 1.1rem; }
  .item li { font-size: var(--step-x); margin-bottom: .2rem; }

  /* Skills read as a list of terms under an area, not as a rated bar chart.
     A bar that says "Cinema 4D, four fifths" is a claim nobody can check. */
  .area { display: grid; grid-template-columns: 7rem 1fr; gap: .5rem 1rem; margin-bottom: .5rem; }
  .area dt { font-family: var(--mono); font-size: var(--step-xx); text-transform: uppercase; letter-spacing: var(--label-tracking); color: var(--muted); padding-top: .15rem; }
  .area dd { margin: 0; font-size: var(--step-x); }

  .sign { margin-top: 2rem; font-size: var(--step-0); }

  @page { margin: 16mm; }
  @media print {
    html, body { background: var(--paper); }
    .sheet { margin: 0; padding: 0; border: 0; max-width: none; }
    a { color: var(--ink); text-decoration: none; }
    h2 { margin-top: 1.4rem; }
  }
"""


def _shell(title, body, t=None):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{design.esc(title)}</title>
<style>
{design.token_css(t, dark=False, motion=False)}
{PAGE_CSS}</style>
</head>
<body>
<article class="sheet">
{body}
</article>
</body>
</html>
"""


def _head(who, what=None):
    reach = [x for x in (who.get("email"), who.get("site"), who.get("github"), who.get("location")) if x]
    links = "".join(
        f'<span><a href="{design.esc(x)}">{design.esc(x.replace("https://", ""))}</a></span>'
        if x.startswith("http") else f"<span>{design.esc(x)}</span>"
        for x in reach
    )
    line = f'<p class="what">{design.esc(what)}</p>' if what else ""
    return f"""<header class="head">
<h1 class="who">{design.esc(who['name'])}</h1>
{line}
<div class="reach">{links}</div>
</header>"""


def _paras(text):
    """Markdown is not the point here. The drafts are plain paragraphs in his
    voice, and voicelint already refuses the punctuation that would need more."""
    out = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        block = block.strip()
        if block:
            out.append(f"<p>{design.esc(block)}</p>")
    return "\n".join(out)


def letter(draft, who=None, t=None):
    """A saved draft as a page. The body is his, unchanged."""
    who = who or design.identity()
    return _shell(
        f"{who['name']}, letter",
        _head(who, who.get("title")) + f'\n<div class="body">\n{_paras(draft)}\n</div>',
        t,
    )


def _proof(ids):
    out = []
    for pid in ids:
        path = PROOF / f"{pid}.md"
        if not path.exists():
            continue
        meta, _ = read_record(path)
        if meta.get("title") and meta.get("summary"):
            out.append((meta["title"], meta["summary"]))
    return out


def _skills(skills, areas):
    by = {}
    for s in skills:
        by.setdefault(s.get("area"), []).append(s.get("term"))
    return [(a, by[a]) for a in areas if by.get(a)]


def resume(record, skills, who=None, t=None):
    who = who or design.identity()
    parts = [_head(who, who.get("title"))]

    summary = record.get("summary") or who.get("hero")
    if summary:
        parts.append(f'<div class="body"><p>{design.esc(summary)}</p></div>')

    built = _proof(record.get("lead_proof") or [])
    if built:
        rows = "".join(
            f'<div class="item"><h3>{design.esc(title)}</h3><p>{design.esc(summary)}</p></div>'
            for title, summary in built
        )
        parts.append(f"<h2>What he builds</h2>{rows}")

    for label, key in (("Experience", "experience"), ("Education", "education")):
        items = record.get(key) or []
        if not items:
            continue
        rows = []
        for i in items:
            if key == "experience":
                when = i.get("from", "") + (f" to {i['to']}" if i.get("to") else "")
                lines = "".join(f"<li>{design.esc(l)}</li>" for l in (i.get("lines") or []))
                rows.append(
                    f'<div class="item"><div class="line"><h3>{design.esc(i["role"])}</h3>'
                    f'<span class="when">{design.esc(when)}</span></div>'
                    f'<p class="org">{design.esc(i["org"])}'
                    f'{" &middot; " + design.esc(i["where"]) if i.get("where") else ""}</p>'
                    + (f"<ul>{lines}</ul>" if lines else "") + "</div>"
                )
            else:
                rows.append(
                    f'<div class="item"><div class="line"><h3>{design.esc(i["what"])}</h3>'
                    f'<span class="when">{design.esc(i.get("year", ""))}</span></div>'
                    f'<p class="org">{design.esc(i["org"])}'
                    f'{" &middot; " + design.esc(i["where"]) if i.get("where") else ""}</p></div>'
                )
        parts.append(f"<h2>{label}</h2>" + "".join(rows))

    areas = _skills(skills, record.get("skill_areas") or [])
    if areas:
        rows = "".join(
            f'<dl class="area"><dt>{design.esc(a)}</dt><dd>{design.esc(", ".join(terms))}</dd></dl>'
            for a, terms in areas
        )
        parts.append(f"<h2>Tools</h2>{rows}")

    return _shell(f"{who['name']}, resume", "\n".join(parts), t)

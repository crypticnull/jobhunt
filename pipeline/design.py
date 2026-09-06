"""The design record, rendered for anything that is not the Astro site.

One record, data/design/tokens.json, is the whole identity: seven colour roles,
three families and the scale they are set at, and every duration and curve with
what it becomes under reduced motion. tools/tokens.mjs renders it into the
site's stylesheet. This renders the same record for the surfaces Astro never
sees, the weekly shortlist and the letters and the resume, so a token edit moves
all of them together and none of them carries a colour of its own.

Nothing here writes a hex, a millisecond or a curve. That is the site's rule,
in tools/check_tokens.mjs, and the tests hold these surfaces to it too.
"""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "data" / "design" / "tokens.json"
IDENTITY = ROOT / "data" / "identity.json"


def tokens(path=None):
    return json.loads(Path(path or TOKENS).read_text(encoding="utf-8"))


def identity(path=None):
    return json.loads(Path(path or IDENTITY).read_text(encoding="utf-8"))


def esc(v):
    return html.escape(str(v if v is not None else ""), quote=True)


def _vars(pairs, indent="  "):
    return "\n".join(f"{indent}--{k}: {v};" for k, v in pairs)


def token_css(t=None, *, dark=True, motion=True):
    """The custom properties, in the shape tools/tokens.mjs writes them. Light
    on bare :root so an unstamped document has a full palette, the dark blocks
    only redefine, and the reduced column is a decision per movement rather than
    a switch that zeroes everything.

    A print surface passes dark=False: paper is paper, and a letter that renders
    dark because the reader's laptop is dark is a letter that prints as a black
    rectangle or not at all."""
    t = t or tokens()
    mot = [(m["name"], m["default"]) for m in t["motion"]["tokens"]]
    reduced = [(m["name"], m["reduced"]) for m in t["motion"]["tokens"] if m["default"] != m["reduced"]]
    score = t["colour"].get("score") or {}
    base = (list(t["colour"]["light"].items()) + list(t["colour"]["plate"].items())
            + list(score.get("light", {}).items())
            + list(t["type"].items()) + list(t["grid"].items()) + (mot if motion else []))
    out = [":root {", _vars(base)]
    out.append("  color-scheme: light dark;" if dark else "  color-scheme: light;")
    out.append("}")
    if dark:
        d = list(t["colour"]["dark"].items()) + list(score.get("dark", {}).items())
        out += ["@media (prefers-color-scheme: dark) {",
                '  :root:not([data-theme="light"]) {', _vars(d, "    "), "  }", "}",
                ':root[data-theme="dark"] {', _vars(d), "  color-scheme: dark;", "}"]
    if motion and reduced:
        out += ["@media (prefers-reduced-motion: reduce) {",
                '  :root:not([data-motion="full"]) {', _vars(reduced, "    "), "  }", "}"]
    return "\n".join(out)

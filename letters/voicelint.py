"""The voice lint. A compiler-style checker for prose in his voice.

    python -m letters.voicelint --profile letter data/proof
    python -m letters.voicelint --profile repo .

Output is path:line:col rule-id message, one finding per line. Exit 0 when
clean, 1 on any error, 2 when the only findings are warnings. The rules,
the lexicon and the two profiles live in data/voice/rules.json, so tuning
the voice is a diffable commit. A rare false positive is waived inline:

    <!-- voicelint: allow parentheses -->

on the line before, or at the end of the line itself. Rules are cheap
regexes on purpose; the point is that no draft reads as machine-written
because a check said so, not because generation was trusted.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "data" / "voice" / "rules.json"

_WAIVER = re.compile(r"<!--\s*voicelint:\s*allow\s+([a-z0-9, -]+?)\s*-->")
_FENCE = re.compile(r"^\s*(```|~~~)")


class Finding:
    __slots__ = ("path", "line", "col", "rule", "message", "level")

    def __init__(self, path, line, col, rule, message, level):
        self.path, self.line, self.col, self.rule, self.message, self.level = path, line, col, rule, message, level

    def __str__(self):
        tag = "" if self.level == "error" else " (warning)"
        return f"{self.path}:{self.line}:{self.col} {self.rule} {self.message}{tag}"


def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def strip_frontmatter(text):
    """Return (body, number_of_lines_removed)."""
    if not text.startswith("---"):
        return text, 0
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            return "".join(lines[i + 1 :]), i + 1
    return text, 0


def _word(term):
    return re.compile(r"(?<![a-z0-9'])" + re.escape(term) + r"(?![a-z0-9'])", re.IGNORECASE)


# Line rules: (line_no, line_text) -> [(col, message)]


def r_em_dash(line):
    out = [(m.start() + 1, "em dash") for m in re.finditer("—", line)]
    out += [(m.start() + 2, "spaced en dash used as an em dash") for m in re.finditer(r"\s–\s", line)]
    # Between letters or after sentence punctuation only, so a CLI flag like
    # --profile in a doc and a year range like 2016–2019 are left alone.
    out += [(m.start() + 1, "double hyphen used as an em dash") for m in re.finditer(r"(?<=[A-Za-z.,!?)])--(?=[A-Za-z\s])", line)]
    out += [(m.start() + 1, "unspaced en dash used as an em dash") for m in re.finditer(r"(?<=[a-zA-Z])–(?=[a-zA-Z])", line)]
    return out


def r_semicolon(line):
    return [(m.start() + 1, "semicolon in prose") for m in re.finditer(";", line)]


def r_parentheses(line):
    return [(m.start() + 1, "parenthesis in prose") for m in re.finditer(r"[()]", line)]


def r_ellipsis(line):
    return [(m.start() + 1, "ellipsis") for m in re.finditer(r"\.\.\.|…", line)]


def r_bullet_list(line):
    m = re.match(r"^\s*(?:[-*+•]|\d+[.)])\s+\S", line)
    return [(m.start() + 1, "bullet list in prose")] if m else []


def r_formal_signoff(line, rules):
    bare = line.strip().rstrip(",.!").strip().lower()
    return [(1, f"formal sign-off '{line.strip()}'")] if bare in rules["signoffs"] else []


def _lexicon(line, terms, label):
    out = []
    for t in terms:
        for m in _word(t).finditer(line):
            out.append((m.start() + 1, f"{label} '{m.group(0)}'"))
    return out


# Paragraph rules: (paragraph_text) -> [(offset, message)]


def r_not_x_but_y(text):
    """The construction, with and without the comma: a negation, a noun phrase
    beginning with an article or a minimiser, then "but". Revised 2026-09-05.
    The old rule fired on any negation within eighty characters of a comma
    and "but", which refused "I don't know your codebase yet, but I've
    shipped", the everyday negation-comma-but sentence the voice rules ask
    for, and missed the comma-less "not a reskin but a rebuild"."""
    pat = r"(?:\bnot|n't)\s+(?:a|an|the|just|only|merely|simply|some)\b[^.!?;,]{1,40}?,?\s*but\b"
    return [(m.start(), "'not X, but Y' construction") for m in re.finditer(pat, text, re.IGNORECASE)]


def r_apply_opener(text, rules):
    return [(m.start(), f"apply opener '{m.group(0)}'") for t in rules["apply_openers"] for m in _word(t).finditer(text)]


def r_contractions(text, rules):
    out = []
    for long, short in rules["contractions"].items():
        pat = re.compile(r"(?<![a-z0-9'])" + re.escape(long) + r"(?![a-z0-9'])", re.IGNORECASE if long[0].islower() else 0)
        for m in pat.finditer(text):
            out.append((m.start(), f"'{m.group(0)}' reads stiff, try '{short}'"))
    return out


def r_sentence_length(text, rules):
    out, pos = [], 0
    for part in re.split(r"(?<=[.!?])\s+", text):
        n = len(part.split())
        if n > rules["max_sentence_words"]:
            out.append((pos, f"{n}-word sentence, keep them medium"))
        pos += len(part) + 1
    return out


def r_connector(text, rules):
    return [(m.start(), f"'{m.group(0)}', prefer 'but'") for t in rules["connectors"] for m in _word(t).finditer(text)]


LINE_RULES = {
    "em-dash": lambda line, rules: r_em_dash(line),
    "semicolon": lambda line, rules: r_semicolon(line),
    "parentheses": lambda line, rules: r_parentheses(line),
    "ellipsis": lambda line, rules: r_ellipsis(line),
    "bullet-list": lambda line, rules: r_bullet_list(line),
    "corporate-vocab": lambda line, rules: _lexicon(line, rules["corporate_vocab"], "corporate vocabulary"),
    "formal-signoff": r_formal_signoff,
}
PARAGRAPH_RULES = {
    "not-x-but-y": lambda text, rules: r_not_x_but_y(text),
    "apply-opener": r_apply_opener,
    "contractions": r_contractions,
    "sentence-length": r_sentence_length,
    "connector": r_connector,
}


def _paragraphs(lines):
    """Yield (joined_text, [(line_no, offset_in_joined)]) for each prose paragraph, skipping fenced code."""
    para, spans, in_fence = [], [], False
    for i, line in enumerate(lines, 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.strip():
            spans.append((i, sum(len(p) + 1 for p in para)))
            para.append(line.rstrip("\n"))
        elif para:
            yield " ".join(para), spans
            para, spans = [], []
    if para:
        yield " ".join(para), spans


def _locate(spans, offset):
    line, col = spans[0][0], offset + 1
    for ln, start in spans:
        if start <= offset:
            line, col = ln, offset - start + 1
    return line, col


def check_text(text, profile, rules, path="<text>"):
    prof = rules["profiles"][profile]
    offset = 0
    if prof.get("strip_frontmatter"):
        text, offset = strip_frontmatter(text)
    lines = text.splitlines()
    levels = {r: "error" for r in prof["errors"]}
    levels.update({r: "warning" for r in prof["warnings"]})

    waived = {}
    for i, line in enumerate(lines, 1):
        for m in _WAIVER.finditer(line):
            names = {n.strip() for n in m.group(1).split(",")}
            target = i if line[: m.start()].strip() else i + 1
            waived.setdefault(target, set()).update(names)

    findings = []

    def emit(line_no, col, rule, message):
        if rule in waived.get(line_no, ()):
            return
        findings.append(Finding(path, line_no + offset, col, rule, message, levels[rule]))

    in_fence = False
    for i, line in enumerate(lines, 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or _WAIVER.fullmatch(line.strip() or "x"):
            continue
        clean = _WAIVER.sub("", line)
        for rule, fn in LINE_RULES.items():
            if rule in levels:
                for col, msg in fn(clean, rules):
                    emit(i, col, rule, msg)
    for text_p, spans in _paragraphs(lines):
        for rule, fn in PARAGRAPH_RULES.items():
            if rule in levels:
                for off, msg in fn(text_p, rules):
                    line_no, col = _locate(spans, off)
                    emit(line_no, col, rule, msg)
    findings.sort(key=lambda f: (f.line, f.col, f.rule))
    return findings


def _excluded(path, patterns):
    """A pattern with a slash is a path prefix from the repo root; a bare name
    matches any path component, so node_modules is excluded wherever it sits."""
    rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
    parts = rel.split("/")
    for p in patterns:
        if "/" in p:
            if rel == p or rel.startswith(p.rstrip("/") + "/"):
                return True
        elif p in parts or fnmatch.fnmatch(rel, p):
            return True
    return False


def collect(paths, prof):
    files = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / p
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and any(fnmatch.fnmatch(f.name, g) for g in prof["include"]) and not _excluded(f, prof["exclude"]):
                    files.append(f)
    return files


def check_files(paths, profile, rules):
    prof = rules["profiles"][profile]
    findings = []
    for f in collect(paths, prof):
        rel = f.relative_to(ROOT).as_posix() if f.is_relative_to(ROOT) else str(f)
        findings.extend(check_text(f.read_text(encoding="utf-8"), profile, rules, rel))
    return findings


def exit_code(findings):
    if any(f.level == "error" for f in findings):
        return 1
    return 2 if findings else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m letters.voicelint", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", choices=("letter", "repo"), required=True)
    ap.add_argument("--rules", default=str(RULES_PATH))
    ap.add_argument("paths", nargs="*", help="files or directories; defaults to the profile's paths")
    args = ap.parse_args(argv)
    rules = load_rules(args.rules)
    paths = args.paths or rules["profiles"][args.profile]["paths"]
    findings = check_files(paths, args.profile, rules)
    for f in findings:
        print(f)
    errors = sum(f.level == "error" for f in findings)
    warnings = len(findings) - errors
    print(f"voicelint {args.profile}: {errors} error(s), {warnings} warning(s)", file=sys.stderr)
    return exit_code(findings)


if __name__ == "__main__":
    sys.exit(main())

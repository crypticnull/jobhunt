"""Read and rewrite record frontmatter without a YAML library.

The records use a small dialect on purpose: `key: scalar`, flow lists
`[a, b]`, and flow maps `{ k: v }`, nested, each key on one line. ingest
owns four keys and rewrites only those lines; every other line passes
through byte for byte, so hand-written prose and fields survive."""

import json
import re

_BARE = re.compile(r"^[A-Za-z0-9_./:@+-]+$")
_KEYWORDS = {"null", "true", "false", "~", "yes", "no", "on", "off"}


def split(text):
    """(front_lines, body). front_lines exclude the fences; ([], text) when there is no frontmatter."""
    if not text.startswith("---"):
        return [], text
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1 :])
    return [], text


def join(front_lines, body):
    return "---\n" + "\n".join(front_lines) + "\n---\n" + body


class _Parser:
    def __init__(self, s):
        self.s, self.i = s, 0

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def value(self):
        self.ws()
        if self.i >= len(self.s):
            return None
        c = self.s[self.i]
        if c == "{":
            return self.map()
        if c == "[":
            return self.list()
        if c in "\"'":
            return self.quoted(c)
        return self.bare("," + "]}")

    def map(self):
        self.i += 1
        out = {}
        while True:
            self.ws()
            if self.s[self.i] == "}":
                self.i += 1
                return out
            j = self.s.index(":", self.i)
            key = self.s[self.i : j].strip()
            self.i = j + 1
            out[key] = self.value()
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1

    def list(self):
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1

    def quoted(self, q):
        j = self.i + 1
        buf = []
        while j < len(self.s):
            ch = self.s[j]
            if ch == "\\" and q == '"' and j + 1 < len(self.s):
                buf.append(self.s[j + 1])
                j += 2
                continue
            if ch == q:
                self.i = j + 1
                return "".join(buf)
            buf.append(ch)
            j += 1
        raise ValueError("unterminated string")

    def bare(self, stops):
        j = self.i
        while j < len(self.s) and self.s[j] not in stops:
            j += 1
        raw = self.s[self.i : j].strip()
        self.i = j
        return scalar(raw)


def scalar(raw):
    if raw in ("", "null", "~"):
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def parse_value(raw):
    return _Parser(raw).value()


def emit(v):
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return v if _BARE.match(v) and v not in _KEYWORDS and not re.fullmatch(r"-?[\d.]+", v) else json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(emit(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k}: {emit(x)}" for k, x in v.items()) + " }" if v else "{}"
    raise TypeError(type(v))


def get(front_lines, key):
    for line in front_lines:
        m = re.match(rf"^{re.escape(key)}:\s*(.*)$", line)
        if m:
            return parse_value(m.group(1))
    return None


def set_key(front_lines, key, value):
    line = f"{key}: {emit(value)}"
    out, done = [], False
    for existing in front_lines:
        if re.match(rf"^{re.escape(key)}:", existing):
            out.append(line)
            done = True
        else:
            out.append(existing)
    if not done:
        out.append(line)
    return out

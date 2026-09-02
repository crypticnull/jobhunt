"""Turn a ComfyUI workflow export into something publishable.

A workflow saved from the ComfyUI canvas carries the whole graph, and that is
what makes it worth showing: the node positions are what let the structure be
drawn rather than listed. It also carries `widgets_values`, which is every text
box in the graph. That means the prompts, the model filenames, the seeds, the
LoRA names and the absolute paths on the machine it ran on.

So the rule here is allowlist, never blocklist. `sanitize` does not walk the
export removing bad keys, because the next ComfyUI version will add a key
nobody thought to remove. It builds a new document from scratch containing only
the fields named below, and anything it has not been taught about is dropped by
default. A leak then needs someone to have deliberately widened the allowlist,
which is a code review, rather than to have forgotten a key, which is a Tuesday.

`leaks` is the second half: it re-reads a sanitized file and refuses it if
anything on the forbidden list survived. The test suite runs it over every
workflow committed to the repository, so a raw export cannot be added by
accident later.

    python -m pipeline.graph sanitize raw.json data/pipelines/x/graph.json
    python -m pipeline.graph svg data/pipelines/x/graph.json out.svg
    python -m pipeline.graph stats data/pipelines/x/graph.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# Node fields that survive sanitising. Everything else, `widgets_values` above
# all, is dropped. `properties` is not here: its one useful member is copied out
# by name below, because the rest of it is a bag anything can be written into.
NODE_FIELDS = ("id", "type", "pos", "size", "order", "mode", "flags")

# Keys that must never appear in a published graph, checked after the fact.
FORBIDDEN = ("widgets_values", "widget_values", "extra", "config", "prompt")

# Node types whose entire purpose is to hold text a human typed. These keep
# their box in the drawing so the shape of the graph is honest, but they are
# reported by `notes` so nobody has to remember they existed.
TEXT_NODE_TYPES = ("Note", "MarkdownNote", "PrimitiveNode", "String", "PrimitiveString")


def _xy(value, fallback=(0.0, 0.0)):
    """ComfyUI writes positions and sizes as [a, b] in newer exports and as
    {"0": a, "1": b} in older ones. Both mean the same pair."""
    if isinstance(value, dict):
        value = [value.get("0", value.get(0)), value.get("1", value.get(1))]
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return list(fallback)
    try:
        return [float(value[0]), float(value[1])]
    except (TypeError, ValueError):
        return list(fallback)


def _slots(raw, links_key):
    """Keep a slot's name, type and wiring. Names like "positive" and "model"
    are what make the drawing readable, and they are node-class labels rather
    than anything the user typed."""
    out = []
    for slot in raw if isinstance(raw, list) else []:
        if not isinstance(slot, dict):
            continue
        kept = {"name": str(slot.get("name", "")), "type": slot.get("type")}
        if links_key in slot:
            kept[links_key] = slot.get(links_key)
        out.append(kept)
    return out


def sanitize(workflow: dict) -> dict:
    """Rebuild the export with only the fields needed to draw and count it."""
    if not isinstance(workflow, dict):
        raise ValueError("workflow must be a JSON object")

    nodes = []
    for raw in workflow.get("nodes", []) or []:
        if not isinstance(raw, dict):
            continue
        node = {k: raw[k] for k in NODE_FIELDS if k in raw}
        node["pos"] = _xy(raw.get("pos"))
        node["size"] = _xy(raw.get("size"), (200.0, 60.0))
        node["type"] = str(raw.get("type", "Unknown"))
        # "Node name for S&R" is the class name again, which is why it is the
        # single member of properties worth carrying.
        props = raw.get("properties")
        if isinstance(props, dict) and "Node name for S&R" in props:
            node["class"] = str(props["Node name for S&R"])
        node["inputs"] = _slots(raw.get("inputs"), "link")
        node["outputs"] = _slots(raw.get("outputs"), "links")
        nodes.append(node)

    links = []
    for link in workflow.get("links", []) or []:
        # [id, from_node, from_slot, to_node, to_slot, type]
        if isinstance(link, (list, tuple)) and len(link) >= 5:
            links.append([link[0], link[1], link[2], link[3], link[4]])
        elif isinstance(link, dict) and "origin_id" in link:
            links.append([link.get("id"), link["origin_id"], link.get("origin_slot", 0), link.get("target_id"), link.get("target_slot", 0)])

    groups = []
    for group in workflow.get("groups", []) or []:
        if not isinstance(group, dict):
            continue
        bounding = group.get("bounding") or []
        if len(bounding) >= 4:
            groups.append(
                {
                    # A group title is typed by hand, so it is carried but it is
                    # also the one string worth reading before publishing.
                    "title": str(group.get("title", "")),
                    "bounding": [float(b) for b in bounding[:4]],
                }
            )

    return {
        "nodes": nodes,
        "links": links,
        "groups": groups,
        "node_count": len(nodes),
        "link_count": len(links),
    }


def leaks(document) -> list[str]:
    """Reasons this document must not be committed. Empty means it is clean."""
    found = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN:
                    found.append(f"{path}.{key} is a forbidden key")
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")
        elif isinstance(node, str):
            # An absolute path is the other way a machine leaks into an export.
            low = node.lower()
            if low.startswith(("c:\\", "d:\\", "/users/", "/home/")) or "\\users\\" in low:
                found.append(f"{path} looks like an absolute path: {node[:40]}")

    walk(document, "$")
    return found


def histogram(graph: dict) -> list[tuple[str, int]]:
    """Node types by frequency, commonest first, then alphabetical so the order
    is stable across runs and the file does not churn in git."""
    counts = Counter(str(n.get("type", "Unknown")) for n in graph.get("nodes", []))
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def notes(graph: dict) -> list[int]:
    """Ids of nodes that exist to hold typed text, so their emptiness after
    sanitising is a deliberate answer rather than an oversight."""
    return [n.get("id") for n in graph.get("nodes", []) if str(n.get("type", "")) in TEXT_NODE_TYPES]


def _bounds(graph, pad=60.0):
    xs, ys = [], []
    for n in graph.get("nodes", []):
        x, y = n["pos"]
        w, h = n["size"]
        xs += [x, x + w]
        ys += [y, y + h]
    for g in graph.get("groups", []):
        x, y, w, h = g["bounding"]
        xs += [x, x + w]
        ys += [y, y + h]
    if not xs:
        return 0.0, 0.0, 100.0, 100.0
    return min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(graph: dict, title: str = "Workflow graph") -> str:
    """A standalone SVG of the graph.

    It carries its own styles and its own dark-mode rule, because it is meant to
    be referenced from an <img>, which cannot inherit the page's custom
    properties. Colours are the site's tokens written out literally, which is
    the one place in the codebase that is allowed.
    """
    min_x, min_y, width, height = _bounds(graph)
    by_id = {n.get("id"): n for n in graph.get("nodes", [])}

    edges = []
    for link in graph.get("links", []):
        src, dst = by_id.get(link[1]), by_id.get(link[3])
        if not src or not dst:
            continue
        x1 = src["pos"][0] + src["size"][0]
        y1 = src["pos"][1] + 30 + 20 * int(link[2] or 0)
        x2 = dst["pos"][0]
        y2 = dst["pos"][1] + 30 + 20 * int(link[4] or 0)
        # A horizontal control offset that grows with the gap keeps long edges
        # from cutting straight through the nodes between their ends.
        c = max(40.0, min(180.0, abs(x2 - x1) / 2))
        edges.append(f'<path class="link" d="M{x1:.0f},{y1:.0f} C{x1 + c:.0f},{y1:.0f} {x2 - c:.0f},{y2:.0f} {x2:.0f},{y2:.0f}" />')

    boxes = []
    for g in graph.get("groups", []):
        x, y, w, h = g["bounding"]
        boxes.append(f'<rect class="group" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="4" />')
        if g["title"]:
            boxes.append(f'<text class="grouplabel" x="{x + 10:.0f}" y="{y + 20:.0f}">{_esc(g["title"])}</text>')

    for n in graph.get("nodes", []):
        x, y = n["pos"]
        w, h = n["size"]
        label = n.get("type", "")
        # Truncate on the box width rather than letting the label run past it.
        room = max(3, int(w / 7.2))
        if len(label) > room:
            label = label[: room - 1] + "\u2026"
        boxes.append(f'<rect class="node" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="3" />')
        boxes.append(f'<rect class="cap" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="22" rx="3" />')
        boxes.append(f'<text class="nodelabel" x="{x + 8:.0f}" y="{y + 15:.0f}">{_esc(label)}</text>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x:.0f} {min_y:.0f} {width:.0f} {height:.0f}" role="img" aria-label="{_esc(title)}">
  <title>{_esc(title)}</title>
  <style>
    /* Referenced from an img, so the page's tokens cannot reach in here. */
    .bg {{ fill: #f1f2ef; }}
    .group {{ fill: #e6e8e5; stroke: #d3d6d3; stroke-width: 1; }}
    .grouplabel {{ fill: #62676d; font: 500 13px ui-monospace, Menlo, monospace; }}
    .node {{ fill: #ffffff; stroke: #d3d6d3; stroke-width: 1; }}
    .cap {{ fill: #35648a; }}
    .nodelabel {{ fill: #ffffff; font: 500 12px ui-monospace, Menlo, monospace; }}
    .link {{ fill: none; stroke: #62676d; stroke-width: 1.5; opacity: 0.55; }}
    @media (prefers-color-scheme: dark) {{
      .bg {{ fill: #0f1113; }}
      .group {{ fill: #171a1d; stroke: #262a2e; }}
      .grouplabel {{ fill: #9aa0a6; }}
      .node {{ fill: #16191c; stroke: #262a2e; }}
      .cap {{ fill: #7aa7cc; }}
      .nodelabel {{ fill: #0f1113; }}
      .link {{ stroke: #9aa0a6; }}
    }}
  </style>
  <rect class="bg" x="{min_x:.0f}" y="{min_y:.0f}" width="{width:.0f}" height="{height:.0f}" />
  <g>{"".join(edges)}</g>
  <g>{"".join(boxes)}</g>
</svg>
"""


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[-3].strip(), file=sys.stderr)
        return 2
    command = argv[0]

    if command == "sanitize":
        if len(argv) < 3:
            print("usage: sanitize IN.json OUT.json", file=sys.stderr)
            return 2
        raw = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        clean = sanitize(raw)
        problems = leaks(clean)
        if problems:
            for p in problems:
                print(f"REFUSED: {p}", file=sys.stderr)
            return 1
        Path(argv[2]).write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
        text_nodes = notes(clean)
        print(f"{clean['node_count']} nodes, {clean['link_count']} links -> {argv[2]}")
        if text_nodes:
            print(f"note: {len(text_nodes)} text-holding node(s) kept as empty boxes: {text_nodes}")
        titles = [g["title"] for g in clean["groups"] if g["title"]]
        if titles:
            print("group titles carried through, read them before publishing:")
            for t in titles:
                print(f"  {t}")
        return 0

    if command == "svg":
        if len(argv) < 3:
            print("usage: svg IN.json OUT.svg", file=sys.stderr)
            return 2
        graph = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        problems = leaks(graph)
        if problems:
            for p in problems:
                print(f"REFUSED: {p}", file=sys.stderr)
            return 1
        Path(argv[2]).write_text(svg(graph), encoding="utf-8")
        print(f"{graph.get('node_count', len(graph.get('nodes', [])))} nodes -> {argv[2]}")
        return 0

    if command == "stats":
        graph = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        rows = histogram(graph)
        width = max((len(t) for t, _ in rows), default=10)
        for node_type, count in rows:
            print(f"{node_type.ljust(width)}  {count}")
        print(f"{'TOTAL'.ljust(width)}  {sum(c for _, c in rows)} nodes in {len(rows)} types")
        return 0

    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

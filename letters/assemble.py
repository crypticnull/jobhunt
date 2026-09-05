"""Block selection and the brief.

A letter is assembled from blocks per role, never from one template with
holes: an opening that names the specific thing, the intersection claim
weighted by the company's category, one proof story, the remote paragraph
only where the posting hedges, and a direct close. The brief joins the
posting, the company record, the selected blocks and the voice rules into
one file Matt drafts from. Nothing here writes a letter."""

import json
import re
from pathlib import Path

from .voicelint import strip_frontmatter

ROOT = Path(__file__).resolve().parent.parent
BLOCKS = ROOT / "letters" / "blocks"
PROOF = ROOT / "data" / "proof"

# When neither --lead nor the company record names a proof story, the category decides.
DEFAULT_LEAD = {
    "ai-video": "local-pipeline",
    "studio-ai": "ae-llama",
    "product-inhouse": "keynote-extractor",
    "brand-inhouse": "event-franchises",
}

# The role decides the claim before the company does. Until 2026-09-05 the
# claim came from the company's category alone, so Coinbase's product
# designers got the event key-art letter and PlanetScale's brand designer got
# the metadata one, and a design engineer at a tier 3 company was handed a
# Keynote unzipper as proof. These mirror the title tiers in scoring.json.
ROLE_FAMILIES = (
    ("design-engineer", r"design engineer|design technologist|ux engineer|creative engineer|design systems? engineer|prototyper"),
    ("product-designer", r"product designer|interaction designer|product motion|motion system|design systems? designer|motion design engineer"),
    ("brand-visual", r"brand designer|visual designer|brand design|graphic designer"),
    ("creative-technologist", r"creative technologist|technical artist|creative developer|motion technologist"),
    ("motion", r"motion designer|motion graphics|animator|3d artist|3d generalist|art director"),
)
LEAD_BY_FAMILY = {"design-engineer": "game-project", "product-designer": "game-project"}


def role_family(title):
    """One of the family names above, or None for a title nobody standardized."""
    t = re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower())
    for family, pattern in ROLE_FAMILIES:
        if re.search(pattern, t):
            return family
    return None


def _frontmatter(text):
    """The tiny YAML subset our records use: `key: value`, flow lists `[a, b]`."""
    meta = {}
    if not text.startswith("---"):
        return meta
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith("[") and raw.endswith("]"):
            meta[key] = [x.strip().strip("'\"") for x in raw[1:-1].split(",") if x.strip()]
        elif raw in ("null", "~", ""):
            meta[key] = None
        else:
            meta[key] = raw.strip("'\"")
    return meta


def read_record(path):
    text = Path(path).read_text(encoding="utf-8")
    meta = _frontmatter(text)
    body, _ = strip_frontmatter(text)
    return meta, body.strip()


def load_blocks(root=BLOCKS):
    """{kind: [(meta, body), ...]} in file order."""
    out = {"opening": [], "claim": [], "remote": [], "close": []}
    for f in sorted(Path(root).rglob("*.md")):
        meta, body = read_record(f)
        kind = meta.get("kind")
        if kind in out:
            out[kind].append((meta, body))
    return out


def load_proof(proof_id, root=PROOF):
    path = Path(root) / f"{proof_id}.md"
    if not path.exists():
        raise KeyError(f"no proof story {proof_id!r} in {root}")
    return read_record(path)


def hedges(posting):
    """True when the letter should argue for remote: the posting is hybrid,
    unclear, or was scored with the remote-hedged flag."""
    if posting.get("remote_class") in ("hybrid", "unclear"):
        return True
    detail = json.loads(posting.get("score_json") or "{}")
    return any(f == "remote hedged" or f.startswith("remote:") for f in detail.get("flags", []))


def choose_lead(company, lead=None, proof_root=PROOF, posting=None):
    if lead:
        return lead
    family_lead = LEAD_BY_FAMILY.get(role_family((posting or {}).get("title")))
    if family_lead and (Path(proof_root) / f"{family_lead}.md").exists():
        return family_lead
    detail = json.loads((posting or {}).get("score_json") or "{}")
    if detail.get("proof_lead") and (Path(proof_root) / f"{detail['proof_lead']}.md").exists():
        return detail["proof_lead"]
    if company.get("lead_proof"):
        return company["lead_proof"]
    cat = company.get("category")
    default = DEFAULT_LEAD.get(cat)
    if default and (Path(proof_root) / f"{default}.md").exists():
        return default
    for f in sorted(Path(proof_root).glob("*.md")):
        meta = _frontmatter(f.read_text(encoding="utf-8"))
        if cat in (meta.get("leads_for") or []):
            return f.stem
    return "ae-llama"


class _Fill(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def fill(text, **values):
    return text.format_map(_Fill(values))


def select(posting, company, lead=None, blocks=None, proof_root=PROOF):
    blocks = blocks or load_blocks()
    cat = company.get("category")
    family = role_family(posting.get("title"))
    claim = next(((m, b) for m, b in blocks["claim"] if family and family in (m.get("for_roles") or [])), None)
    if claim is None:
        claim = next(((m, b) for m, b in blocks["claim"] if m.get("for") == cat and not m.get("for_roles")), None)
    lead_id = choose_lead(company, lead, proof_root, posting)
    proof_meta, proof_body = load_proof(lead_id, proof_root)
    values = {"company": company.get("name", company.get("slug", "")), "role": posting.get("title", "")}
    return {
        "openings": [(m, fill(b, **values)) for m, b in blocks["opening"]],
        "claim": (claim[0], fill(claim[1], **values)) if claim else None,
        "proof": (lead_id, proof_meta, proof_body),
        "remote": (blocks["remote"][0][0], fill(blocks["remote"][0][1], **values)) if blocks["remote"] else None,
        "remote_needed": hedges(posting),
        "family": family,
        "closes": [(m, fill(b, **values)) for m, b in blocks["close"]],
    }


def _comp(p):
    if not p.get("comp_found"):
        return "comp not posted"
    lo, hi, cur = p.get("comp_min"), p.get("comp_max"), p.get("comp_currency") or ""
    if lo is not None and hi is not None and lo != hi:
        return f"{cur} {lo:,}-{hi:,}".strip()
    return f"{cur} {(lo if lo is not None else hi):,}".strip()


def render_brief(posting, company, chosen, voice_rules, max_description=6000):
    detail = json.loads(posting.get("score_json") or "{}")
    why = [f"- {r['rule']} {r['value']:+d} ({r['why']})" for r in detail.get("rules", [])]
    if detail.get("pile"):
        why.insert(0, f"- pile: {detail['pile']}" + (f", title tier {detail.get('title_tier')}" if detail.get("title_tier") else "") + (f", legs {', '.join(detail['legs_hit'])}" if detail.get("legs_hit") else ""))
    flags = "; ".join(detail.get("flags", []))
    desc = (posting.get("description") or "").strip()
    if len(desc) > max_description:
        desc = desc[:max_description] + "\n\n[trimmed]"
    lead_id, proof_meta, proof_body = chosen["proof"]
    out = [
        f"# Brief: {posting['title']} at {company.get('name', company.get('slug'))}",
        "",
        f"Posting id {posting['id']} · {posting['source']} · {posting.get('remote_class')} · {_comp(posting)} · first seen {str(posting.get('first_seen', ''))[:10]} · score {round(posting.get('score') or 0)}",
        posting.get("url", ""),
        "",
        "## Why it scored",
        "",
        *(why or ["- not scored yet"]),
        *([f"- flags: {flags}"] if flags else []),
        "",
        "## The company",
        "",
        f"category {company.get('category')}, priority {company.get('priority')}, lead proof {lead_id}",
        f"remote notes: {company.get('remote_notes') or 'none'}",
        f"notes: {company.get('notes') or 'none'}",
        "",
        "## The posting",
        "",
        desc or "(no description captured)",
        "",
        "## Blocks",
        "",
        "Pick one opening and one close, keep the claim and the proof story, rewrite everything until it sounds like you. Fill any {placeholder} left standing.",
        "",
        "### Openings",
        "",
    ]
    for meta, body in chosen["openings"]:
        out += [f"{meta.get('id')}: {meta.get('note', '')}", "", body, ""]
    out += [f"### The intersection claim ({company.get('category')})", ""]
    if chosen["claim"]:
        out += [chosen["claim"][0].get("note", ""), "", chosen["claim"][1], ""]
    else:
        out += ["(no claim block for this category yet)", ""]
    out += [f"### The proof story: {proof_meta.get('title', lead_id)}", "", proof_body, ""]
    if chosen["remote"]:
        verdict = "include it, the posting hedges on remote" if chosen["remote_needed"] else "skip it, the posting is clearly remote"
        out += [f"### Remote ({verdict})", "", chosen["remote"][1], ""]
    out += ["### Closes", ""]
    for meta, body in chosen["closes"]:
        out += [f"{meta.get('id')}: {meta.get('note', '')}", "", body, ""]
    prof = voice_rules["profiles"]["letter"]
    out += [
        "## Voice",
        "",
        "No em dashes, semicolons, parentheses, ellipses or bullet lists. Contractions throughout, \"but\" as the main connector, "
        "no corporate vocabulary, no \"not X, but Y\", no formal sign-off, never open with \"I'm writing to apply\". "
        "Comma-chained sentences of medium length. Name the specific thing in the first sentence.",
        "",
        f"The save runs the lint with the letter profile ({len(prof['errors'])} hard rules, {len(prof['warnings'])} warnings) and refuses any draft that does not pass clean.",
        "",
        "## Then",
        "",
        f"Draft the letter in a file, then: python -m letters save {posting['id']} path/to/draft.md",
        "",
    ]
    return "\n".join(out)

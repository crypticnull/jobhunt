"""Validate JSON records under /data against the JSON Schemas in data/schema.

A deliberate subset of JSON Schema, enough for our contracts and nothing
more: type (including type lists), required, properties,
additionalProperties false, enum, pattern, items, oneOf, and local $ref.
Markdown frontmatter records (projects, pipelines, proof) are validated by
the site build through their zod mirrors, and tools/check_drift.mjs keeps
those mirrors equal to the JSON Schemas.

    python -m pipeline.validate            # everything it knows about
    python -m pipeline.validate FILE SCHEMA
"""

import json
import re
import sys

from . import frontmatter as fm
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "data" / "schema"

# (instance, schema) pairs checked by default. Private files are checked only when present.
TARGETS = [
    (ROOT / "data" / "companies.example.json", SCHEMA / "company.schema.json"),
    (ROOT / "data" / "companies.json", SCHEMA / "company.schema.json"),
    (ROOT / "data" / "scoring.json", SCHEMA / "scoring.schema.json"),
    (ROOT / "data" / "skills.json", SCHEMA / "skills.schema.json"),
    (ROOT / "data" / "local" / "scoring.local.json", SCHEMA / "scoring.schema.json"),
]

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _resolve(ref, root):
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref supported, got {ref!r}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(instance, schema, root=None, path="$"):
    """Return a list of error strings, empty when the instance conforms."""
    root = schema if root is None else root
    if "$ref" in schema:
        return validate(instance, _resolve(schema["$ref"], root), root, path)
    errors = []
    if "oneOf" in schema:
        matched = [alt for alt in schema["oneOf"] if not validate(instance, alt, root, path)]
        if len(matched) != 1:
            return [f"{path}: matched {len(matched)} of {len(schema['oneOf'])} alternatives, expected exactly one"]
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES[x](instance) for x in types):
            return [f"{path}: expected {'/'.join(types)}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if "pattern" in schema and isinstance(instance, str) and not re.search(schema["pattern"], instance):
        errors.append(f"{path}: {instance!r} does not match {schema['pattern']}")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key}: required")
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                errors.extend(validate(value, props[key], root, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{key}: unexpected field")
    if isinstance(instance, list) and "items" in schema:
        for i, value in enumerate(instance):
            errors.extend(validate(value, schema["items"], root, f"{path}[{i}]"))
    return errors


def validate_file(instance_path, schema_path):
    with open(instance_path, encoding="utf-8") as f:
        instance = json.load(f)
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    return validate(instance, schema)


CHAPTER_KINDS = ("final", "brief", "boards", "frames", "build", "delivery")
PROJECTS = ROOT / "data" / "projects"


def check_chapters(projects_dir=PROJECTS):
    """Four things the JSON Schema cannot see, because they are about where a
    file sits rather than what is inside it.

    A chapter states its project, so a file copied into the wrong directory is
    caught here instead of silently vanishing from both studies. The file name
    carries the kind too, so the name and the frontmatter cannot disagree and
    leave the reading order looking wrong on disk. And one kind appears at most
    once per project, because two Boards chapters would both render while the
    rail linked only the first."""
    errors = []
    base = Path(projects_dir)
    for chapters in sorted(base.glob("*/chapters")):
        slug = chapters.parent.name
        seen = {}
        for f in sorted(chapters.glob("*.md")):
            rel = f.relative_to(ROOT) if f.is_relative_to(ROOT) else f.relative_to(base)
            front, _ = fm.split(f.read_text(encoding="utf-8"))
            declared = fm.get(front, "project")
            kind = fm.get(front, "kind")
            if declared != slug:
                errors.append(f"{rel}: project is {declared!r} but the file sits in {slug!r}")
            if kind not in CHAPTER_KINDS:
                errors.append(f"{rel}: kind {kind!r} is not one of {', '.join(CHAPTER_KINDS)}")
                continue
            m = re.match(r"^(\d{2})-([a-z]+)$", f.stem)
            if not m:
                errors.append(f"{rel}: name it NN-kind.md, for example 01-{kind}.md")
            elif m.group(2) != kind:
                errors.append(f"{rel}: file says {m.group(2)!r} and frontmatter says {kind!r}")
            if kind in seen:
                errors.append(f"{rel}: a {kind!r} chapter already exists at {seen[kind]}")
            else:
                seen[kind] = rel
    return errors


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2:
        pairs = [(Path(argv[0]), Path(argv[1]))]
    elif not argv:
        pairs = [(i, s) for i, s in TARGETS if i.exists()]
    else:
        print(__doc__, file=sys.stderr)
        return 2
    failed = 0
    for instance, schema in pairs:
        errors = validate_file(instance, schema)
        rel = instance.relative_to(ROOT) if instance.is_relative_to(ROOT) else instance
        if errors:
            failed += 1
            print(f"{rel}: {len(errors)} error(s)")
            for e in errors:
                print(f"  {e}")
        else:
            print(f"{rel}: ok")
    if not argv:
        chapter_errors = check_chapters()
        if chapter_errors:
            failed += 1
            print(f"chapters: {len(chapter_errors)} error(s)")
            for e in chapter_errors:
                print(f"  {e}")
        else:
            print("chapters: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

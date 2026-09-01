"""The normalized posting every adapter emits and the store consumes. Mirrors
data/schema/posting.schema.json."""

FIELDS = (
    "source",
    "source_id",
    "company_slug",
    "title",
    "url",
    "location",
    "remote",
    "comp_min",
    "comp_max",
    "comp_currency",
    "description",
    "posted_at",
)

REMOTE_CLASSES = ("remote", "hybrid", "onsite", "unclear")


def posting(**fields):
    p = {f: None for f in FIELDS}
    p.update(fields)
    p["title"] = (p["title"] or "").strip()
    p["source_id"] = str(p["source_id"]) if p["source_id"] is not None else None
    if p["remote"] not in REMOTE_CLASSES:
        p["remote"] = "unclear"
    return p

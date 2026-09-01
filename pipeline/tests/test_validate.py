import json
import unittest
from pathlib import Path

from pipeline.validate import ROOT, SCHEMA, validate, validate_file

SCHEMAS = {p.stem.replace(".schema", ""): json.loads(p.read_text(encoding="utf-8")) for p in SCHEMA.glob("*.schema.json")}


class Subset(unittest.TestCase):
    def test_types_required_enum_pattern(self):
        schema = {
            "type": "object",
            "required": ["a"],
            "additionalProperties": False,
            "properties": {
                "a": {"type": ["integer", "null"]},
                "b": {"type": "string", "enum": ["x", "y"]},
                "c": {"type": "string", "pattern": "^\\d{4}$"},
            },
        }
        self.assertEqual(validate({"a": 1, "b": "x", "c": "2026"}, schema), [])
        self.assertEqual(validate({"a": None}, schema), [])
        errs = validate({"b": "z", "c": "no", "d": 1, "a": True}, schema)
        self.assertEqual(len(errs), 4, errs)

    def test_ref_items_and_oneof(self):
        schema = {
            "type": "array",
            "items": {"$ref": "#/$defs/thing"},
            "$defs": {"thing": {"oneOf": [{"type": "null"}, {"type": "object", "required": ["k"], "properties": {"k": {"type": "string"}}}]}},
        }
        self.assertEqual(validate([None, {"k": "v"}], schema), [])
        self.assertEqual(len(validate([{"k": 1}], schema)), 1)


class Contracts(unittest.TestCase):
    def test_example_companies_file_validates(self):
        self.assertEqual(validate_file(ROOT / "data" / "companies.example.json", SCHEMA / "company.schema.json"), [])

    def test_company_schema_catches_drift(self):
        data = json.loads((ROOT / "data" / "companies.example.json").read_text(encoding="utf-8"))
        data["companies"][0]["salary_notes"] = "never public"
        data["companies"][1]["category"] = "startup"
        errs = validate(data, SCHEMAS["company"])
        self.assertEqual(len(errs), 2, errs)

    def test_normalized_posting_matches_schema(self):
        from scraper.posting import posting

        p = posting(source="lever", source_id="1", company_slug="acme", title="T", url="https://x", remote="remote")
        self.assertEqual(validate(p, SCHEMAS["posting"]), [])

"""docs/search-protocol.md is the human twin of data/scoring.json and the
data/README table says a change to one is a change to the other. Until
2026-09-05 nothing checked, and they disagreed in six places. These read
the numbers and lists the protocol states in prose and assert the ruleset
agrees, so an edit to scoring.json that the doc does not mirror fails CI."""
import json, re, unittest
from pathlib import Path

from scraper.curriculum import readable

ROOT = Path(__file__).resolve().parents[2]
DOC = (ROOT / "docs/search-protocol.md").read_text(encoding="utf-8")
RULES = json.loads((ROOT / "data/scoring.json").read_text(encoding="utf-8"))

def num(pattern):
    m = re.search(pattern, DOC, re.IGNORECASE)
    return int(m.group(1)) if m else None

class ProtocolMatchesRules(unittest.TestCase):
    def test_version_header_matches(self):
        self.assertEqual(re.search(r"^version: (\S+)", DOC, re.M).group(1), RULES["version"])

    def test_pile_thresholds(self):
        self.assertEqual(num(r"apply to (\d+) and review to (\d+)"), RULES["piles"]["apply_min"])
        self.assertEqual(int(re.search(r"apply to \d+ and review to (\d+)", DOC).group(1)), RULES["piles"]["review_min"])

    def test_weekly_caps(self):
        cap = num(r"Both caps are (\d+) per week")
        self.assertEqual(cap, RULES["piles"]["apply_weekly_cap"])
        self.assertEqual(cap, RULES["piles"]["review_weekly_cap"])

    def test_exceptional_floor(self):
        self.assertEqual(num(r"scoring (\d+) or better is named in the digest"), RULES["piles"]["exceptional_min"])

    def test_discovery_caps(self):
        m = re.search(r"to (\d+) and (\d+), and moved out of the function signature", DOC)
        self.assertEqual((int(m.group(1)), int(m.group(2))), (RULES["discovery"]["board_cap"], RULES["discovery"]["posting_cap"]))

    def test_checkpoint_named_once_and_matches(self):
        dates = set(re.findall(r"\b(Nov 16|Oct 5|Sep 6)\b checkpoint", DOC)) | set(re.findall(r"tuned at the (Nov 16|Oct 5) checkpoint", DOC))
        self.assertEqual(len(dates), 1, f"protocol names {sorted(dates)} as the checkpoint")
        month_day = {"Oct 5": "2026-10-05", "Nov 16": "2026-11-16"}[dates.pop()]
        self.assertEqual(month_day, RULES["tuning"]["checkpoint"])

    def test_score_table_maxes(self):
        rows = dict(re.findall(r"^\| ([A-Za-z ]+?) \| (\d+) \|", DOC, re.M))
        want = {"Remote clean": RULES["score"]["remote"]["max"], "Compensation": RULES["score"]["comp"]["max"],
                "Intersection asks": RULES["score"]["intersection"]["max"], "Title fit": RULES["score"]["title"]["max"],
                "Company tier": RULES["score"]["company"]["max"] if "company" in RULES["score"] else None,
                "Curriculum": RULES["score"]["curriculum"]["max"] if "max" in RULES["score"].get("curriculum", {}) else None,
                "Freshness": RULES["score"]["freshness"]["max"] if "freshness" in RULES["score"] else None,
                "Human findable": RULES["score"]["human"]["max"] if "human" in RULES["score"] else None}
        for k, v in want.items():
            if v is not None:
                self.assertEqual(int(rows.get(k, -1)), v, k)

    def test_deductions(self):
        self.assertEqual(num(r"Each match subtracts (\d+)"), RULES["deductions"]["per_hit"])
        self.assertEqual(num(r"Cap the total deduction at (\d+)"), RULES["deductions"]["cap"])

    def test_dead_weight_floor(self):
        self.assertEqual({"fifteen": 15}.get(re.search(r"polled (\w+) or more postings", DOC).group(1)), RULES["digest"]["dead_weight_min_postings"])

    def test_leg_terms_listed_in_doc(self):
        """Every term the ruleset scores appears in the protocol's leg bullet for that leg."""
        for leg, terms in RULES["score"]["intersection"]["legs"].items():
            m = re.search(rf"^- `{leg}`: (.+)$", DOC, re.M)
            self.assertIsNotNone(m, f"no bullet for leg {leg}")
            listed = m.group(1).lower()
            missing = [t for t in terms if readable(t).lower() not in listed]
            self.assertEqual(missing, [], f"{leg}: scored but not in the protocol")

    def test_tier_a_titles_listed_in_doc(self):
        m = re.search(r"^- Tier A \(\d+\): (.+)$", DOC, re.M)
        listed = m.group(1).lower()
        missing = [t for t in RULES["score"]["title"]["tier_a"]["patterns"] if readable(t).lower() not in listed]
        self.assertEqual(missing, [], "tier A titles scored but not in the protocol")

if __name__ == "__main__":
    unittest.main()

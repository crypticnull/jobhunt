import unittest

from scraper import discover
from scraper.score import RULES_PATH, load_rules

RULES = load_rules(RULES_PATH, local="/nonexistent")

REMOTIVE = {
    "jobs": [
        {"company_name": "Frame Co", "title": "Creative Technologist", "url": "https://r/1", "description": "ComfyUI pipeline work"},
        {"company_name": "Acme", "title": "Accountant", "url": "https://r/2", "description": "ledgers"},
    ]
}
WWR = """<rss><channel>
<item><title>Frame Co: Technical Artist</title><link>https://w/1</link><description>Houdini and real-time</description></item>
<item><title>Other Co: Copywriter</title><link>https://w/2</link><description>words</description></item>
</channel></rss>"""


class Discover(unittest.TestCase):
    def test_hits_grouped_and_flagged(self):
        found = discover.discover(known_slugs={"frame-co"}, rules=RULES, get_json=lambda u: REMOTIVE, get_text=lambda u: WWR)
        self.assertEqual([(i["company"], i["title"], i["known"]) for i in found], [("Frame Co", "Creative Technologist", True), ("Frame Co", "Technical Artist", True)])
        self.assertIn("comfyui", found[0]["terms"])

    def test_render_suggests_add_for_unknown(self):
        found = discover.discover(known_slugs=set(), rules=RULES, get_json=lambda u: REMOTIVE, get_text=lambda u: WWR)
        text = discover.render(found)
        self.assertIn("Frame Co", text)
        self.assertIn('add: python -m scraper add <careers-url> --category <cat> --name "Frame Co"', text)
        self.assertNotIn("Accountant", text)
        self.assertEqual(discover.render([]), "Nothing hit the intersection terms today.")

    def test_two_remotive_calls_only(self):
        calls = []

        def get_json(u):
            calls.append(u)
            return {"jobs": []}

        discover.discover(rules=RULES, get_json=get_json, get_text=lambda u: "<rss><channel></channel></rss>")
        self.assertEqual(len(calls), 2)

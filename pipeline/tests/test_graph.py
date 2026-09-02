import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from pipeline.graph import FORBIDDEN, histogram, leaks, notes, sanitize, svg

ROOT = Path(__file__).resolve().parents[2]

SECRET = "a cinematic portrait of the hero, 8k, masterpiece, by my-private-lora"

# Shaped like a real ComfyUI canvas export, including the parts that must not
# survive: the prompt text, the checkpoint filename, the absolute path on the
# machine it ran on, and a Note node holding whatever was typed into it.
RAW = {
    "last_node_id": 4,
    "last_link_id": 2,
    "nodes": [
        {
            "id": 1,
            "type": "CheckpointLoaderSimple",
            "pos": [100, 100],
            "size": [320, 98],
            "order": 0,
            "mode": 0,
            "outputs": [{"name": "MODEL", "type": "MODEL", "links": [1], "slot_index": 0}],
            "properties": {"Node name for S&R": "CheckpointLoaderSimple"},
            "widgets_values": ["D:\\models\\checkpoints\\private-finetune-v3.safetensors"],
        },
        {
            "id": 2,
            "type": "CLIPTextEncode",
            "pos": [480, 100],
            "size": {"0": 400, "1": 200},
            "order": 1,
            "mode": 0,
            "inputs": [{"name": "clip", "type": "CLIP", "link": 1}],
            "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [2]}],
            "properties": {"Node name for S&R": "CLIPTextEncode"},
            "widgets_values": [SECRET],
        },
        {
            "id": 3,
            "type": "CLIPTextEncode",
            "pos": [480, 340],
            "size": [400, 200],
            "order": 2,
            "mode": 0,
            "properties": {"Node name for S&R": "CLIPTextEncode"},
            "widgets_values": ["blurry, watermark"],
        },
        {
            "id": 4,
            "type": "Note",
            "pos": [100, 400],
            "size": [300, 120],
            "order": 3,
            "mode": 0,
            "properties": {},
            "widgets_values": ["remember to re-run this on C:/Users/matt/renders before the deadline"],
        },
    ],
    "links": [[1, 1, 0, 2, 0, "CLIP"], [2, 2, 0, 3, 0, "CONDITIONING"]],
    "groups": [{"title": "Conditioning", "bounding": [460, 60, 460, 520]}],
    "config": {"workspace": "C:\\Users\\matt\\ComfyUI"},
    "extra": {"ds": {"scale": 0.8, "offset": [12, 34]}},
    "version": 0.4,
}


class Sanitize(unittest.TestCase):
    def setUp(self):
        self.clean = sanitize(json.loads(json.dumps(RAW)))
        self.text = json.dumps(self.clean)

    def test_the_prompt_and_the_paths_are_gone(self):
        self.assertNotIn(SECRET, self.text)
        self.assertNotIn("private-finetune", self.text)
        self.assertNotIn("Users", self.text)
        self.assertNotIn("safetensors", self.text)
        self.assertEqual(leaks(self.clean), [])

    def test_forbidden_keys_do_not_survive(self):
        for key in FORBIDDEN:
            self.assertNotIn(f'"{key}"', self.text, f"{key} survived sanitising")

    def test_the_structure_is_kept(self):
        """Dropping the values is only worth doing if the shape is still there,
        because the shape is the whole reason to publish the graph."""
        self.assertEqual(self.clean["node_count"], 4)
        self.assertEqual(self.clean["link_count"], 2)
        self.assertEqual([n["type"] for n in self.clean["nodes"]][:2], ["CheckpointLoaderSimple", "CLIPTextEncode"])
        self.assertEqual(self.clean["nodes"][0]["pos"], [100.0, 100.0])
        self.assertEqual(self.clean["groups"][0]["title"], "Conditioning")

    def test_size_written_as_an_object_is_read_the_same_as_a_list(self):
        """Older exports write {"0": w, "1": h}. Getting this wrong collapses
        the node to nothing and the drawing silently loses a box."""
        self.assertEqual(self.clean["nodes"][1]["size"], [400.0, 200.0])

    def test_a_key_nobody_has_heard_of_is_dropped(self):
        """The point of an allowlist. A future ComfyUI version that stores the
        prompt somewhere new must not leak it through this function, and no
        change here should be needed for that to hold."""
        raw = json.loads(json.dumps(RAW))
        raw["nodes"][0]["future_field_with_a_secret"] = SECRET
        raw["nodes"][0]["properties"]["another_one"] = SECRET
        raw["telemetry"] = {"user": "matt", "home": "/home/matt"}
        clean = sanitize(raw)
        self.assertNotIn(SECRET, json.dumps(clean))
        self.assertNotIn("telemetry", json.dumps(clean))
        self.assertEqual(leaks(clean), [])

    def test_text_holding_nodes_are_reported(self):
        self.assertEqual(notes(self.clean), [4])

    def test_leaks_rejects_a_raw_export(self):
        problems = leaks(RAW)
        self.assertTrue(problems)
        self.assertTrue(any("widgets_values" in p for p in problems))
        self.assertTrue(any("absolute path" in p for p in problems))


class Render(unittest.TestCase):
    def setUp(self):
        self.clean = sanitize(json.loads(json.dumps(RAW)))

    def test_histogram_counts_by_type_commonest_first(self):
        self.assertEqual(histogram(self.clean)[0], ("CLIPTextEncode", 2))
        self.assertEqual(sum(c for _, c in histogram(self.clean)), 4)

    def test_svg_is_well_formed_and_says_nothing_it_should_not(self):
        out = svg(self.clean, title="Test graph")
        root = ET.fromstring(out)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertNotIn(SECRET, out)
        self.assertNotIn("Users", out)
        self.assertEqual(len(root.findall(".//{http://www.w3.org/2000/svg}rect")) > 0, True)

    def test_every_drawn_shape_sits_inside_the_viewbox(self):
        """A node parked outside the viewBox is invisible with no error, which
        is the failure mode that would make a 219-node graph quietly wrong."""
        out = svg(self.clean)
        root = ET.fromstring(out)
        vx, vy, vw, vh = (float(v) for v in root.get("viewBox").split())
        for rect in root.findall(".//{http://www.w3.org/2000/svg}rect"):
            x, y = float(rect.get("x")), float(rect.get("y"))
            w, h = float(rect.get("width")), float(rect.get("height"))
            self.assertGreaterEqual(x, vx - 0.5)
            self.assertGreaterEqual(y, vy - 0.5)
            self.assertLessEqual(x + w, vx + vw + 0.5)
            self.assertLessEqual(y + h, vy + vh + 0.5)

    def test_the_svg_carries_a_dark_rule(self):
        """It is referenced from an img, so it cannot inherit the page tokens
        and has to answer for both themes itself."""
        self.assertIn("prefers-color-scheme: dark", svg(self.clean))

    def test_an_empty_graph_still_renders(self):
        ET.fromstring(svg({"nodes": [], "links": [], "groups": []}))


class CommittedGraphsAreClean(unittest.TestCase):
    def test_no_workflow_in_the_repo_carries_values(self):
        """The guard. Every graph JSON committed under data/ is re-checked on
        every test run, so a raw export dropped in later fails here rather than
        on someone else's screen."""
        checked = 0
        for path in sorted((ROOT / "data").rglob("*.json")):
            if "graph" not in path.name and "workflow" not in path.name:
                continue
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(leaks(document), [], f"{path.relative_to(ROOT)} must be sanitised first")
            checked += 1
        self.assertGreaterEqual(checked, 0)


if __name__ == "__main__":
    unittest.main()

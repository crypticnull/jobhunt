import unittest

from pipeline.naming import NamingError, parse, suggest


class Parse(unittest.TestCase):
    def test_full_name(self):
        d = parse("nitro-create_2026_logo-loop_storyboard_v03.jpg")
        self.assertEqual((d["project"], d["year"], d["deliverable"], d["stage"], d["version"], d["ext"]), ("nitro-create", 2026, "logo-loop", "storyboard", 3, "jpg"))
        self.assertEqual((d["slug"], d["media"], d["field"], d["canonical"]), ("nitro-create-2026", "image", "process", "logo-loop_storyboard_v03.jpg"))

    def test_singletons_and_video(self):
        self.assertEqual(parse("quest_2025_key-art_hero_v01.png")["canonical"], "hero.png")
        self.assertEqual(parse("quest_2025_key-art_poster_v02.jpeg")["canonical"], "poster.jpg")
        d = parse("quest_2025_logo-loop_final_v03.mp4")
        self.assertEqual((d["media"], d["field"]), ("video", "video"))

    def test_refusals_carry_suggestions(self):
        cases = {
            "Quest 2025 Logo Loop FINAL.mp4": "quest_2025_logo-loop_final_v01.mp4",
            "quest_2025_logo-loop_final.mp4": "quest_2025_logo-loop_final_v01.mp4",
            "quest_2025_logo-loop_render_v01.mp4": "quest_2025_logo-loop_final_v01.mp4",
            "quest_2025_logo-loop_final_v01.png": "quest_2025_logo-loop_final_v01.png",
            "quest_2025_key-art_hero_v01.mp4": "quest_2025_key-art_hero_v01.mp4",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(NamingError) as ctx:
                    parse(name)
                self.assertEqual(ctx.exception.suggestion, expected)

    def test_suggest_marks_the_unknown(self):
        self.assertEqual(suggest("hero.png"), "<project>_<year>_<deliverable>_hero_v01.png")
        self.assertEqual(suggest("Summit_2025_Opener_v4.PNG"), "summit_2025_opener_<stage>_v04.png")

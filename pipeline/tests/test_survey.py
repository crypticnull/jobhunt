import tempfile
import unittest
from pathlib import Path

from pipeline import survey


def build(root, tree):
    for rel, size in tree.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * size)


class Survey(unittest.TestCase):
    def rows(self, tree):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        build(tmp.name, tree)
        rows, skipped = survey.survey(tmp.name)
        return {Path(r["path"]).name: r for r in rows}, skipped

    def test_junk_never_reaches_the_manifest(self):
        rows, skipped = self.rows({
            "Quest 2025/keep.png": 10,
            "Quest 2025/.DS_Store": 6,
            "Quest 2025/Thumbs.db": 6,
            "Quest 2025/Adobe After Effects Auto-Save/Quest.aep": 10,
            "Quest 2025/Media Cache/blob.pek": 10,
        })
        self.assertEqual(set(rows), {"keep.png"})
        self.assertEqual(skipped, 4)

    def test_a_render_sequence_is_one_row_with_a_count(self):
        """A 4,000 frame render listed frame by frame buries the six files that
        actually matter."""
        tree = {f"Quest 2025/render/beauty_{i:04d}.png": 10 for i in range(1, 51)}
        tree["Quest 2025/hero.png"] = 10
        rows, _ = self.rows(tree)
        self.assertEqual(len(rows), 2)
        seq = rows["beauty_0001.png"]
        self.assertIn("sequence of 50 files", seq["note"])
        self.assertEqual(int(seq["bytes"]), 500, "the row carries the whole sequence's size")

    def test_two_files_are_not_a_sequence(self):
        rows, _ = self.rows({"Quest 2025/a_001.png": 10, "Quest 2025/a_002.png": 10})
        self.assertEqual(len(rows), 2)

    def test_a_project_file_is_never_proposed_as_a_final(self):
        """Quest_Master.aep sat in a Delivery folder and the word master made it
        read as a final, which would have put an ingestable name on something
        that must never leave the drive."""
        rows, _ = self.rows({
            "Quest 2025/Delivery/Quest_Master.aep": 10,
            "Summit 2025/Summit Key Art.psd": 10,
        })
        for name in ("Quest_Master.aep", "Summit Key Art.psd"):
            self.assertEqual(rows[name]["stage"], "source", name)
            self.assertEqual(rows[name]["proposed"], "", name)
            self.assertIn("leave it where it is", rows[name]["note"])

    def test_only_image_and_video_get_a_proposed_name(self):
        rows, _ = self.rows({"LiveRamp 2021/boards/liveramp_storyboard_p1.pdf": 10})
        r = rows["liveramp_storyboard_p1.pdf"]
        self.assertEqual(r["stage"], "storyboard")
        self.assertEqual(r["proposed"], "")
        self.assertIn("export pages to jpg", r["note"])

    def test_an_index_becomes_the_version_so_boards_stay_distinct(self):
        rows, _ = self.rows({
            "Quest 2025/Boards/Quest25_storyboard_01.jpg": 10,
            "Quest 2025/Boards/Quest25_storyboard_02.jpg": 10,
        })
        proposed = {r["proposed"] for r in rows.values()}
        self.assertEqual(len(proposed), 2, f"both boards proposed the same name: {proposed}")
        self.assertTrue(any(p.endswith("_v02.jpg") for p in proposed))

    def test_an_explicit_version_is_carried_through(self):
        rows, _ = self.rows({"Quest 2025/styleframes/quest_styleframe_A_v03.png": 10})
        self.assertTrue(rows["quest_styleframe_A_v03.png"]["proposed"].endswith("_v03.png"))

    def test_a_project_word_does_not_leak_into_the_deliverable(self):
        """'Nitro Create 2026 Opener' was yielding the deliverable
        'create-opener', because only the whole hint was being dropped."""
        rows, _ = self.rows({"NITRO CREATE 2026/Delivery/Nitro Create 2026 Opener MASTER.mov": 10})
        r = rows["Nitro Create 2026 Opener MASTER.mov"]
        self.assertEqual(r["project"], "nitro-create")
        self.assertEqual(r["deliverable"], "opener")
        self.assertEqual(r["proposed"], "nitro-create_2026_opener_final_v01.mov")

    def test_the_longest_project_hint_wins(self):
        self.assertEqual(survey.guess_project("Nitro Create 2026/x"), "nitro-create")
        self.assertEqual(survey.guess_project("Power Awards Gala/x"), "pag")

    def test_year_reads_a_four_digit_year_before_a_dated_folder(self):
        self.assertEqual(survey.guess_year("Quest 2025/boards"), 2025)
        self.assertEqual(survey.guess_year("26_09_01_Job_Hunt/x"), 2026)
        self.assertIsNone(survey.guess_year("no numbers here"))

    def test_an_unmatched_file_is_low_confidence_not_a_guess(self):
        rows, _ = self.rows({"Misc/untitled_render.png": 10})
        r = rows["untitled_render.png"]
        self.assertEqual(r["project"], "unknown")
        self.assertEqual(r["confidence"], "low")
        self.assertEqual(r["proposed"], "")

    def test_rejected_styleframes_are_kept(self):
        """The directions that lost are the point, so nothing filters them."""
        rows, _ = self.rows({"Quest 2025/styleframes/quest_style_B_REJECTED.png": 10})
        self.assertEqual(rows["quest_style_B_REJECTED.png"]["stage"], "styleframe")

    def test_the_survey_writes_nothing_into_the_folder_it_reads(self):
        with tempfile.TemporaryDirectory() as d:
            build(d, {"Quest 2025/a.png": 10})
            before = sorted(p.relative_to(d).as_posix() for p in Path(d).rglob("*"))
            survey.survey(d)
            after = sorted(p.relative_to(d).as_posix() for p in Path(d).rglob("*"))
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()


class Structure(unittest.TestCase):
    """A curated drop is already <project>-<year>/<stage>/files. Reading that
    tree is the whole job; the keyword guessing is only for what it omits."""

    def rows(self, tree):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        build(tmp.name, tree)
        rows, _ = survey.survey(tmp.name)
        return {Path(r["path"]).name: r for r in rows}

    def test_a_named_folder_is_the_project_not_a_guess(self):
        """anthem-2026/final came back as 'unknown' because the tool only knew a
        hardcoded list of projects and ignored the tree it was handed."""
        rows = self.rows({"anthem-2026/final/clip.mp4": 10})
        r = rows["clip.mp4"]
        self.assertEqual((r["project"], r["year"], r["stage"]), ("anthem", "2026", "final"))
        self.assertEqual(r["confidence"], "high")

    def test_a_slug_with_hyphens_keeps_them_and_loses_only_the_year(self):
        rows = self.rows({"bill-of-rights-2024/storyboard/p1.png": 10})
        r = rows["p1.png"]
        self.assertEqual(r["project"], "bill-of-rights")
        self.assertEqual(r["year"], "2024")

    def test_a_folder_with_no_year_says_so_rather_than_inventing_one(self):
        rows = self.rows({"power-camp/styleframe/a.png": 10})
        r = rows["a.png"]
        self.assertEqual(r["project"], "power-camp")
        self.assertEqual(r["year"], "")
        self.assertEqual(r["confidence"], "medium")

    def test_a_container_folder_is_never_a_project(self):
        for folder in ("Misc", "assets", "New Folder", "exports"):
            rows = self.rows({f"{folder}/thing.png": 10})
            self.assertEqual(rows["thing.png"]["project"], "unknown", folder)

    def test_the_project_name_does_not_repeat_into_the_deliverable(self):
        rows = self.rows({"anthem-2026/final/anthem_2026_opener.mp4": 10})
        r = rows["anthem_2026_opener.mp4"]
        self.assertEqual(r["deliverable"], "opener")
        self.assertEqual(r["proposed"], "anthem_2026_opener_final_v01.mp4")

    def test_a_project_file_still_beats_the_folder_it_sits_in(self):
        """A .aep inside a folder called final is a project file, and the folder
        name must not talk the tool into proposing it as a deliverable."""
        rows = self.rows({"anthem-2026/final/anthem.aep": 10})
        r = rows["anthem.aep"]
        self.assertEqual(r["stage"], "source")
        self.assertEqual(r["proposed"], "")

    def test_spaces_and_underscores_read_the_same_as_hyphens(self):
        for folder in ("Nitro Create 2026", "nitro_create_2026", "nitro-create-2026"):
            rows = self.rows({f"{folder}/final/a.mp4": 10})
            self.assertEqual(rows["a.mp4"]["project"], "nitro-create", folder)
            self.assertEqual(rows["a.mp4"]["year"], "2026", folder)

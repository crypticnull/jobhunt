import tempfile
import unittest
from pathlib import Path

from pipeline.validate import check_chapters

GOOD = """---
project: {project}
kind: {kind}
title: A chapter
order: 10
---

Body.
"""


def write(root, directory, name, **front):
    d = Path(root) / directory / "chapters"
    d.mkdir(parents=True, exist_ok=True)
    front.setdefault("project", directory)
    (d / name).write_text(GOOD.format(**front), encoding="utf-8")
    return d / name


class Chapters(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def test_a_well_formed_set_passes(self):
        write(self.root, "quest-2025", "01-final.md", kind="final")
        write(self.root, "quest-2025", "02-brief.md", kind="brief")
        write(self.root, "quest-2025", "03-boards.md", kind="boards")
        self.assertEqual(check_chapters(self.root), [])

    def test_a_chapter_filed_under_the_wrong_project_is_caught(self):
        """Copying a chapter into the wrong directory would otherwise drop it
        from both studies without a word."""
        write(self.root, "quest-2025", "01-final.md", kind="final", project="summit-2025")
        errors = check_chapters(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("but the file sits in 'quest-2025'", errors[0])

    def test_the_file_name_and_the_frontmatter_must_agree(self):
        write(self.root, "quest-2025", "03-boards.md", kind="frames")
        errors = check_chapters(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("file says 'boards' and frontmatter says 'frames'", errors[0])

    def test_an_unnumbered_file_is_corrected_by_example(self):
        write(self.root, "quest-2025", "boards.md", kind="boards")
        errors = check_chapters(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("01-boards.md", errors[0])

    def test_a_kind_appears_at_most_once(self):
        """Two boards chapters would both render while the rail linked only the
        first, which reads as a missing chapter that is on the page."""
        write(self.root, "quest-2025", "03-boards.md", kind="boards")
        write(self.root, "quest-2025", "04-boards.md", kind="boards")
        errors = check_chapters(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("already exists", errors[0])

    def test_an_unknown_kind_names_the_six(self):
        write(self.root, "quest-2025", "01-teaser.md", kind="teaser")
        errors = check_chapters(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("final, brief, boards, frames, build, delivery", errors[0])

    def test_projects_are_independent(self):
        write(self.root, "quest-2025", "03-boards.md", kind="boards")
        write(self.root, "summit-2025", "03-boards.md", kind="boards")
        self.assertEqual(check_chapters(self.root), [])

    def test_a_project_with_no_chapters_directory_is_fine(self):
        (Path(self.root) / "quest-2025").mkdir(parents=True)
        self.assertEqual(check_chapters(self.root), [])


if __name__ == "__main__":
    unittest.main()

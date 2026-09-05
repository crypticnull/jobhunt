"""The privacy split (ADR-0002) must hold: data/local/ is ignored and no
database file is ever tracked. These run offline against the repo itself."""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


class PrivacySplit(unittest.TestCase):
    def test_data_local_is_ignored(self):
        r = git("check-ignore", "data/local/anything.txt")
        self.assertEqual(r.returncode, 0, "data/local/ must be gitignored")

    def test_no_db_files_tracked(self):
        r = git("ls-files", "*.db")
        self.assertEqual(r.stdout.strip(), "", "no .db file may ever be tracked")

    def test_pre_commit_guard_exists(self):
        r = git("ls-files", ".githooks/pre-commit")
        self.assertEqual(r.stdout.strip(), ".githooks/pre-commit")

    def test_no_comp_figure_is_tracked(self):
        """The floor, the target and the ask left CLAUDE.md on 2026-09-02 and
        came back in docs/search-protocol.md the same day. Paths were guarded
        and content was not."""
        r = git("grep", "-lE", r"\$1[0-9]{2},[0-9]{3}", "--", ".", ":!*/tests/*", ":!*/fixtures/*")
        self.assertEqual(r.stdout.strip(), "", "a comp figure is in a public file: " + r.stdout)

    def test_project_assets_are_not_ignored(self):
        """The staging folder rule must be root-anchored. A bare assets/ swallowed
        data/projects/<slug>/assets/ for two days and nobody noticed because the
        three hero files were committed before the rule existed."""
        r = subprocess.run(["git", "check-ignore", "-q", "data/projects/example/assets/board01.png"], cwd=ROOT)
        self.assertEqual(r.returncode, 1, "a new project asset must be committable")
        r = subprocess.run(["git", "check-ignore", "-q", "assets/anything.mov"], cwd=ROOT)
        self.assertEqual(r.returncode, 0, "the root staging folder must still be ignored")


if __name__ == "__main__":
    unittest.main()

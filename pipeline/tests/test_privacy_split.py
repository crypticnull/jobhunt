"""The privacy split (ADR-0002) must hold: data/local/ is ignored and no
database file is ever tracked. These run offline against the repo itself."""

import subprocess
import unittest


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


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import tempfile
import unittest

from workspace_os.config import Source
from workspace_os.housekeeping import find_temporary_artifacts


class HousekeepingTests(unittest.TestCase):
    def test_find_temporary_artifacts_ignores_git_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scratch-note.md").write_text("temporary", encoding="utf-8")
            git_dir = root / ".git"
            git_dir.mkdir()
            (git_dir / "scratch-internal.md").write_text("ignored", encoding="utf-8")
            source = Source(
                name="example",
                type="product",
                responsibility="Example.",
                path=root,
            )

            findings = find_temporary_artifacts([source])

        self.assertEqual(1, len(findings))
        self.assertEqual(Path("scratch-note.md"), findings[0].path)

    def test_find_temporary_artifacts_deduplicates_multiple_pattern_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tmp-example.log").write_text("temporary", encoding="utf-8")
            source = Source(
                name="example",
                type="product",
                responsibility="Example.",
                path=root,
            )

            findings = find_temporary_artifacts([source])

        self.assertEqual(1, len(findings))
        self.assertEqual(Path("tmp-example.log"), findings[0].path)


if __name__ == "__main__":
    unittest.main()

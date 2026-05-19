from pathlib import Path
import subprocess
import tempfile
import unittest

from workspace_os.config import Source
from workspace_os.validation import validate_workspace, validation_failed


class ValidationTests(unittest.TestCase):
    def test_validate_workspace_reports_configured_git_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            source = Source("example", "product", "Example.", root)

            results = validate_workspace([source], include_housekeeping=False)

        self.assertFalse(validation_failed(results))
        self.assertTrue(any(result.name == "source-registry" for result in results))

    def test_validate_workspace_fails_missing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Source("missing", "product", "Example.", Path(directory) / "missing")

            results = validate_workspace([source], include_housekeeping=False)

        self.assertTrue(validation_failed(results))
        self.assertTrue(any(result.name == "source:missing" and not result.passed for result in results))

    def test_validate_workspace_fails_on_temporary_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            (root / "scratch-note.md").write_text("temporary", encoding="utf-8")
            source = Source("example", "product", "Example.", root)

            results = validate_workspace([source])

        self.assertTrue(validation_failed(results))
        self.assertTrue(any(result.name == "housekeeping" and not result.passed for result in results))


if __name__ == "__main__":
    unittest.main()

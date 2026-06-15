from pathlib import Path
import subprocess
import json
import tempfile
import unittest

from contextlib import redirect_stdout
from io import StringIO

from workspace_os.cli import main
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

    def test_validate_workspace_includes_smoke_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            source = Source("example", "product", "Example.", root)

            results = validate_workspace([source], include_housekeeping=False, include_smoke_queries=True)

        self.assertFalse(validation_failed(results))
        self.assertTrue(any(result.name.startswith("smoke:") for result in results))

    def test_validate_command_includes_smoke_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            subprocess.run(["git", "init"], cwd=source_root, check=True, capture_output=True)
            config = root / "workspace.json"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with StringIO() as buffer:
                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "validate", "--skip-housekeeping"])
                rendered = buffer.getvalue()

        self.assertEqual(0, exit_code)
        self.assertIn("PASS smoke:chat:hola", rendered)
        self.assertIn("PASS smoke:cli:next", rendered)


if __name__ == "__main__":
    unittest.main()

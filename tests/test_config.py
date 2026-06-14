from pathlib import Path
import json
import os
import tempfile
import unittest

from workspace_os.config import load_sources, load_workspace_memory_path, load_workspace_root


class ConfigTests(unittest.TestCase):
    def test_load_sources_resolves_relative_paths_from_config_location(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            config = root / "workspace.sources.json"
            config.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "name": "example",
                                "type": "doctrine",
                                "responsibility": "Example responsibility.",
                                "path": "source",
                                "search": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            sources = load_sources(config)

        self.assertEqual("example", sources[0].name)
        self.assertEqual(source.resolve(), sources[0].path)

    def test_load_sources_rejects_missing_sources_list(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "workspace.sources.json"
            config.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "sources"):
                load_sources(config)

    def test_load_workspace_root_prefers_configured_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "workspace.sources.json"
            config.write_text(
                json.dumps({"workspace_root": "..", "sources": []}),
                encoding="utf-8",
            )

            workspace_root = load_workspace_root(config)

        self.assertEqual(root.parent.resolve(), workspace_root)

    def test_load_workspace_root_uses_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "workspace.sources.json"
            config.write_text(json.dumps({"sources": []}), encoding="utf-8")
            previous = os.environ.get("WORKSPACE_OS_GIT_ROOT")
            os.environ["WORKSPACE_OS_GIT_ROOT"] = str(Path(directory) / "workspace-root")
            try:
                workspace_root = load_workspace_root(config)
            finally:
                if previous is None:
                    os.environ.pop("WORKSPACE_OS_GIT_ROOT", None)
                else:
                    os.environ["WORKSPACE_OS_GIT_ROOT"] = previous

        self.assertEqual((Path(directory) / "workspace-root").resolve(), workspace_root)

    def test_load_workspace_memory_path_defaults_under_workspace_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "workspace.sources.json"
            config.write_text(json.dumps({"sources": []}), encoding="utf-8")

            memory_path = load_workspace_memory_path(config)

        self.assertEqual((root / ".workspace-os" / "workspace-memory.sqlite3").resolve(), memory_path)

    def test_load_workspace_memory_path_prefers_configured_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "workspace.sources.json"
            config.write_text(
                json.dumps({"memory_db": "state/memory.sqlite3", "sources": []}),
                encoding="utf-8",
            )

            memory_path = load_workspace_memory_path(config)

        self.assertEqual((root / "state" / "memory.sqlite3").resolve(), memory_path)


if __name__ == "__main__":
    unittest.main()

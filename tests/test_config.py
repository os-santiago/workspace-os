from pathlib import Path
import json
import tempfile
import unittest

from workspace_os.config import load_sources


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


if __name__ == "__main__":
    unittest.main()

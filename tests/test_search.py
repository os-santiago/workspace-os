from pathlib import Path
import tempfile
import unittest

from workspace_os.config import Source
from workspace_os.search import search_sources


class SearchTests(unittest.TestCase):
    def test_search_sources_returns_path_and_line_number(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notes = root / "notes.md"
            notes.write_text("First line\nADEV governs the workspace\n", encoding="utf-8")
            source = Source(
                name="example",
                type="doctrine",
                responsibility="Example.",
                path=root,
            )

            matches = search_sources([source], "adev")

        self.assertEqual(1, len(matches))
        self.assertEqual("example", matches[0].source_name)
        self.assertEqual(Path("notes.md"), matches[0].path)
        self.assertEqual(2, matches[0].line_number)


if __name__ == "__main__":
    unittest.main()

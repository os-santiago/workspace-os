from pathlib import Path
import tempfile
import unittest

from workspace_os.classification import classify_content


class ClassificationTests(unittest.TestCase):
    def test_classify_doctrine_content(self):
        result = classify_content("Agents must validate scripts before release.")

        self.assertEqual("doctrine", result.target)
        self.assertEqual("medium", result.confidence)

    def test_classify_evidence_content(self):
        result = classify_content("Incident root cause and validated lesson learned.")

        self.assertEqual("evidence", result.target)

    def test_classify_path_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roadmap.md"
            path.write_text("Roadmap with acceptance criteria.", encoding="utf-8")

            result = classify_content(str(path), is_path=True)

        self.assertEqual("product", result.target)

    def test_classify_temporary_artifact(self):
        result = classify_content("scratch-note.md", is_path=True)

        self.assertEqual("temporary", result.target)


if __name__ == "__main__":
    unittest.main()

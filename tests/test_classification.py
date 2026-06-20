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

    def test_classify_source_code_path(self):
        result = classify_content("main.py", is_path=True)
        self.assertEqual("execution", result.target)
        self.assertEqual("high", result.confidence)

    def test_classify_test_code_path(self):
        result = classify_content("test_cli.py", is_path=True)
        self.assertEqual("execution", result.target)
        self.assertEqual("high", result.confidence)
        self.assertIn("test code", result.reason)

    def test_classify_config_path(self):
        result = classify_content("pyproject.toml", is_path=True)
        self.assertEqual("execution", result.target)
        self.assertEqual("high", result.confidence)
        self.assertIn("configuration", result.reason)

    def test_classify_code_content(self):
        result = classify_content("import os\nfrom pathlib import Path\ndef process():\n    pass")
        self.assertEqual("execution", result.target)
        self.assertEqual("medium", result.confidence)

    def test_classify_test_content(self):
        result = classify_content("def test_sum():\n    assert sum([1, 2]) == 3")
        self.assertEqual("execution", result.target)
        self.assertEqual("medium", result.confidence)
        self.assertIn("test patterns", result.reason)


if __name__ == "__main__":
    unittest.main()

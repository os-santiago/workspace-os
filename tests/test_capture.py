from datetime import date
from pathlib import Path
import tempfile
import unittest

from workspace_os.capture import build_capture_draft, write_capture
from workspace_os.config import Source


class CaptureTests(unittest.TestCase):
    def test_build_capture_draft_targets_evidence_source_and_sanitizes_content(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "kb"
            source = Source("kb", "evidence", "Evidence.", evidence)

            draft = build_capture_draft(
                sources=[source],
                capture_type="incident",
                title="Script validation lesson",
                body="password: plain-text should not be stored",
                today=date(2026, 5, 19),
            )

        self.assertEqual(Path("captures/incident/2026-05-19-script-validation-lesson.md"), draft.relative_path)
        self.assertEqual("kb", draft.source_name)
        self.assertIn("password: [REDACTED]", draft.content)
        self.assertNotIn("plain-text", draft.content)

    def test_write_capture_creates_file_once(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "kb"
            source = Source("kb", "evidence", "Evidence.", evidence)
            draft = build_capture_draft(
                sources=[source],
                capture_type="decision",
                title="Use dry run by default",
                body="Write only after explicit request.",
                today=date(2026, 5, 19),
            )

            destination = write_capture(draft)

            self.assertTrue(destination.exists())
            with self.assertRaises(FileExistsError):
                write_capture(draft)

    def test_build_capture_draft_requires_evidence_source(self):
        source = Source("adev", "doctrine", "Doctrine.", Path("."))

        with self.assertRaisesRegex(ValueError, "evidence source"):
            build_capture_draft([source], "daily", "Missing evidence", "Body")


if __name__ == "__main__":
    unittest.main()

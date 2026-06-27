from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.onboarding import ONBOARDING_PREF_KEY, run_onboarding_tutorial
from workspace_os.shell import WorkspaceShell


class OnboardingTests(unittest.TestCase):
    def test_run_onboarding_tutorial_completes_and_records_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            outputs: list[str] = []
            answers = iter(["", "search before write", "sanitize", "approval"])

            result = run_onboarding_tutorial(
                store,
                input_func=lambda prompt="": next(answers),
                output_func=outputs.append,
            )

            self.assertTrue(result.completed)
            self.assertFalse(result.skipped)
            self.assertEqual(3, result.correct_answers)
            self.assertEqual(3, result.total_questions)
            self.assertEqual("true", store.get_preference(ONBOARDING_PREF_KEY))
            self.assertTrue(any(line.startswith("Onboarding tutorial:") for line in outputs))
            self.assertTrue(any("Tutorial complete." in line for line in outputs))

    def test_run_onboarding_tutorial_skip_marks_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            outputs: list[str] = []

            result = run_onboarding_tutorial(
                store,
                input_func=lambda prompt="": "skip",
                output_func=outputs.append,
            )

            self.assertTrue(result.completed)
            self.assertTrue(result.skipped)
            self.assertEqual(0, result.correct_answers)
            self.assertEqual(0, result.total_questions)
            self.assertEqual("true", store.get_preference(ONBOARDING_PREF_KEY))
            self.assertTrue(any("Onboarding skipped." in line for line in outputs))

    def test_shell_preloop_invokes_onboarding_on_interactive_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / "memory.sqlite3"
            source_root = Path(directory) / "source"
            source_root.mkdir()
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            shell = WorkspaceShell([], memory, skip_onboarding=False)

            with patch("workspace_os.shell.sys.stdin.isatty", return_value=True), patch(
                "workspace_os.shell.run_onboarding_tutorial"
            ) as mocked_tutorial:
                shell.preloop()

            mocked_tutorial.assert_called_once()


if __name__ == "__main__":
    unittest.main()

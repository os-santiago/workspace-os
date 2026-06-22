from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workspace_os.learning import _is_agent_mismatch_error, build_workspace_learning_model
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.profile import load_profile, save_profile_key


class LearningModelTests(unittest.TestCase):
    def test_learning_model_prioritizes_common_error_patterns(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            save_profile_key(store, "primary_agent", "codex")
            store.record_feedback_event(
                request_text="Please summarize the repo state.",
                result_text="The answer was extremely long and generic.",
                feedback_text="Too verbose and not helpful.",
                status="questionable",
                reason="Verbosity objection.",
                error_type="too_verbose",
                has_objection=True,
            )
            store.record_feedback_event(
                request_text="Please summarize the repo state.",
                result_text="Still far too much detail.",
                feedback_text="Too verbose again.",
                status="questionable",
                reason="Verbosity objection.",
                error_type="too_verbose",
                has_objection=True,
            )
            store.record_feedback_event(
                request_text="Please analyze the repo.",
                result_text="I routed this through the wrong agent.",
                feedback_text="Wrong agent, please use the preferred route next time.",
                status="questionable",
                reason="Routing objection.",
                error_type="wrong_agent",
                has_objection=True,
            )
            store.record_feedback_event(
                request_text="Please analyze the repo.",
                result_text="I could not resolve the repository name.",
                feedback_text="You missed the repo resolution.",
                status="questionable",
                reason="Context objection.",
                error_type="missing_repo_resolution",
                has_objection=True,
            )

            model = build_workspace_learning_model(store, load_profile(store))

        self.assertEqual("codex", model.primary_agent_bias)
        self.assertEqual("too_verbose", model.dominant_error_type)
        self.assertEqual("compact", model.detail_level_hint)
        self.assertIn("reduce answer verbosity", model.render_summary())

    def test_agent_mismatch_detection_identifies_capability_issues(self):
        """Test that _is_agent_mismatch_error identifies missing commands/tools."""
        self.assertTrue(_is_agent_mismatch_error("command not found: antigravity"))
        self.assertTrue(_is_agent_mismatch_error("executable not found"))
        self.assertTrue(_is_agent_mismatch_error("Error: missing dependency 'pytest'"))
        self.assertTrue(_is_agent_mismatch_error("tool not found in PATH"))
        self.assertTrue(_is_agent_mismatch_error("unsupported operation for this agent"))

    def test_agent_mismatch_detection_excludes_generic_failures(self):
        """Test that _is_agent_mismatch_error excludes generic execution failures."""
        self.assertFalse(_is_agent_mismatch_error("network error: connection timeout"))
        self.assertFalse(_is_agent_mismatch_error("timeout after 30 seconds"))
        self.assertFalse(_is_agent_mismatch_error("test failed: assertion error"))
        self.assertFalse(_is_agent_mismatch_error("Traceback (most recent call last):"))
        self.assertFalse(_is_agent_mismatch_error("syntax error in line 42"))
        self.assertFalse(_is_agent_mismatch_error("build failed"))
        self.assertFalse(_is_agent_mismatch_error(""))  # Empty error

    def test_agent_mismatch_detection_prioritizes_generic_over_capability(self):
        """Test that generic failure markers override capability indicators."""
        mixed_error = "command not found, but this was a timeout"
        self.assertFalse(_is_agent_mismatch_error(mixed_error))

        mixed_error2 = "tool not found: test failed"
        self.assertFalse(_is_agent_mismatch_error(mixed_error2))


if __name__ == "__main__":
    unittest.main()

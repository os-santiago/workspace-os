from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workspace_os.learning import build_workspace_learning_model
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


if __name__ == "__main__":
    unittest.main()

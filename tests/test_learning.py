from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workspace_os.learning import _is_agent_mismatch_error, build_questioning_prompt, build_workspace_learning_model
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

    def test_wrong_agent_confidence_triggers_adaptive_cross_checking(self):
        """When wrong_agent errors dominate with high confidence, squad lead increases cross-check frequency."""
        import random

        from workspace_os.agent_queue import AgentQueueTracker
        from workspace_os.cycle import _squad_lead_choose_agent_and_role

        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            save_profile_key(store, "primary_agent", "opencode")

            # Record 10 wrong_agent errors to create high confidence (10/10 = 1.0)
            for i in range(10):
                store.record_feedback_event(
                    request_text=f"Task {i}",
                    result_text="Wrong agent was used.",
                    feedback_text="Wrong agent - should use different route.",
                    status="questionable",
                    reason="Agent routing error.",
                    error_type="wrong_agent",
                    has_objection=True,
                )

            model = build_workspace_learning_model(store, load_profile(store))
            self.assertEqual("wrong_agent", model.dominant_error_type)
            self.assertGreaterEqual(model.confidence, 0.8)

            # Test adaptive role selection: should alternate primary/cross-check
            tracker = AgentQueueTracker(Path(directory))
            rng = random.Random(42)

            roles = []
            for work_item in range(1, 11):
                agent, role = _squad_lead_choose_agent_and_role(
                    work_item, store, tracker, rng
                )
                roles.append(role)

            # With wrong_agent confidence >= 0.8, should use 1:1 primary:cross-check alternation
            self.assertIn("cross-check", roles, "Should include cross-check roles")
            # Count cross-checks: should be ~50% (5 out of 10) instead of ~33% (3-4 out of 10)
            cross_check_count = roles.count("cross-check")
            self.assertGreaterEqual(
                cross_check_count,
                4,
                f"Expected more cross-checks due to wrong_agent signal, got {cross_check_count}",
            )
            self.assertNotIn(
                "observer",
                roles,
                "Should not use observer role during adaptive cross-checking",
            )

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

    def test_questioning_prompt_generates_and_records_learning_cues(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            prompt = build_questioning_prompt(
                store,
                "Objective: fix issue #81\nNeed validation and integration guidance.",
                role="primary",
                work_item_id="issue-81",
                agent_name="claude",
            )

            stats = store.qa_metrics()
            recorded = store.get_qa_for_work_item("issue-81")

        self.assertLessEqual(len(prompt.questions), 3)
        self.assertTrue(prompt.questions)
        self.assertIn("Questioning phase:", prompt.render())
        self.assertGreaterEqual(stats["total"], 1)
        self.assertEqual(len(recorded), stats["total"])
        self.assertTrue(any("issue number" in question.lower() or "source of truth" in question.lower() for question in prompt.questions))


if __name__ == "__main__":
    unittest.main()

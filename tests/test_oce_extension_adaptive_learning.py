import json
import os
import tempfile
import unittest
from pathlib import Path

from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.conscience import evaluate_request, ALLOW, ALLOW_WITH_LIMITS, SAFE_REDIRECT
from workspace_os.oce_extensions import clear_oce_extensions, register_oce_extension
from workspace_os.oce_extension_adaptive_learning import adaptive_context_hook, adaptive_decision_hook


class AdaptiveLearningTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_oce_extensions()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "memory.sqlite3"
        os.environ["WORKSPACE_OS_MEMORY_DB"] = str(self.db_path)

        self.store = WorkspaceMemoryStore(self.db_path)
        self.store.ensure_schema()

        # Re-register the extension under test explicitly
        from workspace_os.oce_extensions import OceExtension, PolicyDocumentSpec
        self.extension = OceExtension(
            name="adaptive-learning-layer",
            description="Adaptive learning test layer.",
            layer="decision",
            policy_documents=(
                PolicyDocumentSpec(
                    ref="workspace.policy.adaptive-learning",
                    title="Adaptive Policy",
                    norms=("Test norms.",),
                ),
            ),
            context_hooks=(adaptive_context_hook,),
            decision_hooks=(adaptive_decision_hook,),
        )
        register_oce_extension(self.extension)

    def tearDown(self) -> None:
        clear_oce_extensions()
        if "WORKSPACE_OS_MEMORY_DB" in os.environ:
            del os.environ["WORKSPACE_OS_MEMORY_DB"]
        self.temp_dir.cleanup()

    def test_escalates_risk_for_historically_failed_tasks(self):
        # Record at least 2 failures to trigger failure_prone_tasks for 'refactor' task type
        # In habits.py: total >= 2 and non_successes > successes
        self.store.record_task_outcome(
            task_type="refactor",
            context_hash="hash1",
            outcome="failure",
            created_at="2026-06-14T10:00:00Z"
        )
        self.store.record_task_outcome(
            task_type="refactor",
            context_hash="hash2",
            outcome="failure",
            created_at="2026-06-14T10:05:00Z"
        )

        # Evaluate a standard low risk command that mentions 'refactor'
        decision = evaluate_request("Run a refactor on CLI code.")

        # Risk escalates to 'medium' and extra validation is required
        self.assertEqual("medium", decision.risk_level)
        self.assertEqual(ALLOW_WITH_LIMITS, decision.decision)
        self.assertIn("extra_validation_verification_plan", decision.missing_context)

    def test_enforces_compactness_when_feedback_indicates_too_verbose(self):
        # Seed feedback events where error_type is 'too_verbose'
        self.store.record_feedback_event(
            request_text="Show status",
            result_text="A very long verbose status description...",
            feedback_text="Keep it short next time",
            status="questionable",
            error_type="too_verbose",
            reason="Response was too verbose.",
            created_at="2026-06-14T10:00:00Z"
        )

        decision = evaluate_request("Check workspace files.")

        # Allows execution but response strategy incorporates compactness constraint
        self.assertTrue(decision.allows_execution())
        self.assertIn("compactness_constraint", decision.response_strategy)
        self.assertIn("enforces response compactness", decision.rationale)

    def test_realigns_routing_for_ambiguous_requests_to_operator_favorite_agent(self):
        # Set preference for 'claude' as the primary agent in the operator profile
        with self.store._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO operator_profile (key, value, updated_at) VALUES (?, ?, ?)",
                ("primary_agent", "claude", "2026-06-14T10:00:00Z")
            )

        # Ambiguous task normally routes to 'opencode' as primary and 'claude' as secondary
        # With the habit preference set, it should realign to 'claude'
        decision = evaluate_request("What should we do next?")

        self.assertEqual(SAFE_REDIRECT, decision.decision)
        self.assertEqual("claude", decision.primary_agent)
        self.assertEqual("user_preference_habit_aligned", decision.routing_reason)


if __name__ == "__main__":
    unittest.main()

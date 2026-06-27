from pathlib import Path
import tempfile
import unittest

from workspace_os.memory import WorkspaceMemoryStore


class MemoryTests(unittest.TestCase):
    def test_memory_store_persists_preferences_lessons_and_turns(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            store.record_preference("tone", "concise")
            store.record_lesson("delivery", "Prefer one atomic PR per iteration.", ["ADEV.md"], 0.9)
            store.record_task_outcome("capture", "abc123", "success", "scanales-kb:captures/session/example.md")
            store.record_turn("session-1", "user", "Remember this lesson.")
            store.record_feedback_event(
                request_text="Please summarize the repo state.",
                result_text="Workspace analysis is ready.",
                feedback_text="Great, that is exactly what I needed.",
                status="over_expectation",
                reason="Praise detected.",
                error_type="positive",
                has_praise=True,
            )
            store.record_feedback_event(
                request_text="Please summarize the repo state.",
                result_text="The answer was extremely long and generic.",
                feedback_text="This is too verbose and not helpful.",
                status="questionable",
                reason="An objection was detected.",
                error_type="too_verbose",
                has_objection=True,
            )
            store.record_context_snapshot("global", "test", "summary text", "markdown text")
            store.record_decision(
                "hash-1",
                "medium",
                "SAFE_REDIRECT",
                ["missing_workspace"],
                primary_agent="opencode",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )
            store.record_qa(
                "how do we validate a dashboard change?",
                "run the focused pytest module and verify the rendered ui payload.",
                "issue-80-dashboard",
                work_item_id="issue-80",
                agent_name="claude",
            )
            store.record_qa(
                "how do we validate a dashboard change?",
                "run the focused pytest module and verify the rendered ui payload.",
                "issue-80-dashboard",
                work_item_id="issue-80",
                agent_name="claude",
            )

            stats = store.stats()
            hits = store.search("concise", limit=10)
            feedback_hits = store.search("Great", limit=10)
            snapshot = store.latest_context_snapshot("global")
            report = store.decision_metrics_summary()
            feedback_metrics = store.feedback_metrics()
            feedback_history = store.feedback_history(limit=10)
            qa_metrics = store.qa_metrics()
            recent_qa = store.recent_qa_pairs(limit=1)

        self.assertEqual(1, stats["operator_preferences"])
        self.assertEqual(1, stats["reusable_lessons"])
        self.assertEqual(1, stats["task_outcomes"])
        self.assertEqual(1, stats["conversation_turns"])
        self.assertEqual(2, stats["feedback_events"])
        self.assertEqual(1, stats["context_snapshots"])
        self.assertEqual(2, stats["question_answer_pairs"])
        self.assertTrue(any(hit.kind == "preference" for hit in hits))
        self.assertTrue(any(hit.kind == "feedback" for hit in feedback_hits))
        self.assertIsNotNone(snapshot)
        self.assertEqual("test", snapshot["reason"])
        self.assertEqual("summary text", snapshot["summary"])
        self.assertEqual(2, feedback_metrics["total"])
        self.assertEqual(1, feedback_metrics["over_expectation_count"])
        self.assertEqual(1, feedback_metrics["questionable_count"])
        self.assertEqual(1, feedback_metrics["too_verbose_count"])
        self.assertTrue(any(entry["error_type"] == "too_verbose" for entry in feedback_history))
        self.assertEqual(1, report["total"])
        self.assertEqual(1, report["decision_counts"]["SAFE_REDIRECT"])
        self.assertEqual(1, report["primary_agent_counts"]["opencode"])
        self.assertEqual(1, report["routing_reason_counts"]["workspace_inventory_first"])
        self.assertEqual("missing_workspace", report["top_missing_context"])
        self.assertEqual("route_to_opencode_for_inventory", report["recommended_next_action"])
        self.assertEqual(2, qa_metrics["total"])
        self.assertEqual(1, qa_metrics["unique_contexts"])
        self.assertEqual(1, qa_metrics["unique_questions"])
        self.assertEqual(2, qa_metrics["recent_7_days"])
        self.assertTrue(qa_metrics["latest_created_at"])
        self.assertEqual("How do we validate a dashboard change?", recent_qa[0]["question"])
        self.assertEqual("claude", recent_qa[0]["agent"])
        self.assertEqual("Run the focused pytest module and verify the rendered ui payload.", recent_qa[0]["answer"])


if __name__ == "__main__":
    unittest.main()

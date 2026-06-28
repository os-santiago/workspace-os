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
                "  how do we validate a dashboard change?  ",
                "  run the focused pytest module and verify the rendered ui payload.  ",
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
            store.record_context_snapshot(
                "workspace",
                "semantic-review",
                "Coordinate context sharing with similarity search and memory reuse.",
                "Semantic context sharing helps reuse prior work that is not recent.",
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
            work_item_qa = store.get_qa_for_work_item("issue-80")
            similar_qa = store.get_similar_questions("issue-80-dashboard", limit=1)
            semantic_hits = store.semantic_search("semantic context sharing and memory reuse", limit=3)
            semantic_metrics = store.semantic_context_metrics("semantic context sharing and memory reuse")
            metrics = store.questioning_metrics("semantic context sharing and memory reuse")

        self.assertEqual(1, stats["operator_preferences"])
        self.assertEqual(1, stats["reusable_lessons"])
        self.assertEqual(1, stats["task_outcomes"])
        self.assertEqual(1, stats["conversation_turns"])
        self.assertEqual(2, stats["feedback_events"])
        self.assertEqual(2, stats["context_snapshots"])
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
        self.assertEqual("How do we validate a dashboard change?", work_item_qa[0]["question"])
        self.assertEqual("Run the focused pytest module and verify the rendered ui payload.", work_item_qa[0]["answer"])
        self.assertEqual("How do we validate a dashboard change?", similar_qa[0]["question"])
        self.assertEqual("Run the focused pytest module and verify the rendered ui payload.", similar_qa[0]["answer"])
        self.assertTrue(any(hit.kind == "snapshot" for hit in semantic_hits))
        self.assertGreaterEqual(semantic_hits[0].score, 0.15)
        self.assertGreaterEqual(semantic_metrics["hit_count"], 1)
        self.assertGreaterEqual(semantic_metrics["top_score"], 0.15)
        self.assertEqual(2, metrics["summary"]["total"])
        self.assertEqual("claude", next(iter(metrics["answer_sources"])))
        self.assertTrue(metrics["question_patterns"])
        self.assertIn("with_qna", metrics)
        self.assertIn("without_qna", metrics)
        self.assertIn("semantic", metrics)
        self.assertGreaterEqual(metrics["learning_velocity"], 0.0)
        self.assertGreaterEqual(metrics["estimated_time_invested_minutes"], 0.0)
        self.assertGreaterEqual(metrics["estimated_rework_savings_minutes"], 0.0)

        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "memory-large.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            for index in range(205):
                store.record_qa(
                    f"How do we validate item {index}?",
                    f"Run validation step {index}.",
                    f"bulk-context-{index}",
                    work_item_id=f"bulk-{index}",
                    agent_name="claude" if index % 2 == 0 else "opencode",
                )
            store.record_feedback_event(
                request_text="Questioning phase: validate bulk dashboard behavior.",
                result_text="iteration-1: questions=2 learned=1 recorded=1 | outcome=pass",
                feedback_text="Questioning phase completed before execution and the outcome was captured for learning.",
                status="over_expectation",
                reason="Questioning phase outcome recorded after execution.",
                error_type="positive",
                has_praise=True,
            )
            large_metrics = store.questioning_metrics("bulk dashboard behavior")

        self.assertEqual(205, large_metrics["summary"]["total"])
        self.assertEqual(205, sum(large_metrics["answer_sources"].values()))
        self.assertEqual(1.0, large_metrics["with_qna"]["success_rate"])


if __name__ == "__main__":
    unittest.main()

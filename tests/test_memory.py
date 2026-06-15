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
            store.record_context_snapshot("global", "test", "summary text", "markdown text")
            store.record_decision(
                "hash-1",
                "medium",
                "SAFE_REDIRECT",
                ["missing_workspace"],
                primary_agent="codex",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            stats = store.stats()
            hits = store.search("concise", limit=10)
            snapshot = store.latest_context_snapshot("global")
            report = store.decision_metrics_summary()

        self.assertEqual(1, stats["operator_preferences"])
        self.assertEqual(1, stats["reusable_lessons"])
        self.assertEqual(1, stats["task_outcomes"])
        self.assertEqual(1, stats["conversation_turns"])
        self.assertEqual(1, stats["context_snapshots"])
        self.assertTrue(any(hit.kind == "preference" for hit in hits))
        self.assertIsNotNone(snapshot)
        self.assertEqual("test", snapshot["reason"])
        self.assertEqual("summary text", snapshot["summary"])
        self.assertEqual(1, report["total"])
        self.assertEqual(1, report["decision_counts"]["SAFE_REDIRECT"])
        self.assertEqual(1, report["primary_agent_counts"]["codex"])
        self.assertEqual(1, report["routing_reason_counts"]["workspace_inventory_first"])


if __name__ == "__main__":
    unittest.main()

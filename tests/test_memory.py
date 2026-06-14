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

            stats = store.stats()
            hits = store.search("concise", limit=10)

        self.assertEqual(1, stats["operator_preferences"])
        self.assertEqual(1, stats["reusable_lessons"])
        self.assertEqual(1, stats["task_outcomes"])
        self.assertEqual(1, stats["conversation_turns"])
        self.assertTrue(any(hit.kind == "preference" for hit in hits))


if __name__ == "__main__":
    unittest.main()

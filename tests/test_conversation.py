from pathlib import Path
import tempfile
import unittest

from workspace_os.batch import start_batch, start_process
from workspace_os.config import Source
from workspace_os.conversation import build_workspace_reply
from workspace_os.memory import WorkspaceMemoryStore


class ConversationTests(unittest.TestCase):
    def test_workspace_reply_records_turns_and_surfaces_memory_hits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            (source_root / "notes.md").write_text("ADEV keeps work aligned.\n", encoding="utf-8")
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            store.record_preference("style", "be concise")

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "be concise",
                memory_store=store,
                session_id="session-1",
            )

            stats = store.stats()

        self.assertTrue(reply.conscience.allows_execution())
        self.assertTrue(any(hit.kind == "preference" for hit in reply.memory_hits))
        self.assertEqual(2, stats["conversation_turns"])

    def test_workspace_reply_includes_active_batch_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            start_batch(store, "batch-1", "validate shell habits", started_at="2026-06-14T10:00:00+00:00")

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "Remember the active batch.",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Active batch:", reply.reply)
        self.assertIn("batch-1", reply.reply)

    def test_workspace_reply_includes_active_process_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            start_process(store, "process-1", "keep process visible", started_at="2026-06-14T10:00:00+00:00")

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "Remember the active process.",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Active process:", reply.reply)
        self.assertIn("process-1", reply.reply)


if __name__ == "__main__":
    unittest.main()

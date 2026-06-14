from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()

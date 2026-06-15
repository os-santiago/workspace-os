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
        self.assertIn("Answer:", reply.reply)
        self.assertIn("Trace:", reply.reply)

    def test_workspace_reply_greeting_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "hola",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Answer:", reply.reply)
        self.assertIn("Hola. Soy WOS", reply.reply)
        self.assertIn("Codex", reply.reply)
        self.assertIn("Claude", reply.reply)

    def test_workspace_reply_explains_application(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "que hace esta aplicacion?",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Workspace OS is your local workspace control plane.", reply.reply)
        self.assertIn("tracks repos and git state", reply.reply)
        self.assertIn("delegates execution and cross-checks", reply.reply)
        self.assertIn("/inspect", reply.reply)

    def test_workspace_reply_refuses_repetitive_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "respondes siempre lo mismo?",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("No. I now answer by intent instead of repeating the same fallback.", reply.reply)
        self.assertIn("route it to Codex first", reply.reply)
        self.assertIn("return the next action", reply.reply)

    def test_workspace_reply_default_fallback_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "tell me something useful",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Give me a repo, goal, or question", reply.reply)
        self.assertIn("task plan", reply.reply)
        self.assertIn("/codex <task>", reply.reply)
        self.assertIn("/claude <task>", reply.reply)

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

        self.assertIn("Trace:", reply.reply)
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

        self.assertIn("Trace:", reply.reply)
        self.assertIn("Active process:", reply.reply)
        self.assertIn("process-1", reply.reply)

    def test_workspace_reply_includes_global_context_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            store.record_context_snapshot("global", "shell-exit", "compact context", "markdown context")

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "Use the latest context.",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Trace:", reply.reply)
        self.assertIn("Global context:", reply.reply)
        self.assertIn("shell-exit", reply.reply)
        self.assertIn("compact context", reply.reply)

    def test_workspace_reply_summarizes_projects_in_flight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            start_process(store, "process-1", "keep process visible", started_at="2026-06-14T10:00:00+00:00")
            start_batch(store, "batch-1", "keep batch visible", started_at="2026-06-14T10:05:00+00:00")
            store.record_agent_launch("codex", "review the workspace summary", "source", launched_at="2026-06-14T10:06:00+00:00")

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "que proyectos tenemos en curso",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Answer:", reply.reply)
        self.assertIn("Trace:", reply.reply)
        self.assertIn("Tracked projects:", reply.reply)
        self.assertIn("process-1", reply.reply)
        self.assertIn("batch-1", reply.reply)
        self.assertIn("Next step:", reply.reply)
        self.assertIn("codex", reply.reply)

    def test_workspace_reply_routes_ambiguous_status_to_codex_and_claude(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "que proyectos tenemos en curso?",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Answer:", reply.reply)
        self.assertIn("Trace:", reply.reply)
        self.assertIn("Primary route=/codex", reply.reply)
        self.assertIn("Fallback route=/claude", reply.reply)
        self.assertIn("Suggested command: /codex", reply.reply)
        self.assertIn("Suggested command: /claude", reply.reply)
        self.assertNotIn("start a new process window before the next batch", reply.reply)
        self.assertEqual(2, len(reply.suggested_actions))
        self.assertEqual("codex", reply.suggested_actions[0]["agent"])
        self.assertEqual("claude", reply.suggested_actions[1]["agent"])

    def test_workspace_reply_exposes_redirect_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "What should we do next?",
                memory_store=store,
                session_id="session-1",
            )

        self.assertEqual("SAFE_REDIRECT", reply.conscience.decision)
        self.assertEqual(2, len(reply.suggested_actions))
        self.assertEqual("codex", reply.suggested_actions[0]["agent"])
        self.assertEqual("claude", reply.suggested_actions[1]["agent"])

    def test_workspace_reply_uses_history_to_prefer_claude_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            store.record_decision(
                "hash-privacy",
                "medium",
                "SAFE_REDIRECT",
                ["privacy"],
                primary_agent="claude",
                secondary_agent="codex",
                routing_reason="domain_privacy_cross_check",
            )

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "What should we do next?",
                memory_store=store,
                session_id="session-1",
            )

        self.assertEqual("SAFE_REDIRECT", reply.conscience.decision)
        self.assertEqual("claude", reply.suggested_actions[0]["agent"])
        self.assertEqual("codex", reply.suggested_actions[1]["agent"])
        self.assertIn("History bias:", reply.reply)
        self.assertIn("Suggested route: /claude", reply.reply)
        self.assertIn("Fallback route: /codex", reply.reply)


if __name__ == "__main__":
    unittest.main()

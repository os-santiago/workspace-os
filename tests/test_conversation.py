from pathlib import Path
import tempfile
import unittest

from workspace_os.batch import start_batch, start_process
from workspace_os.config import Source
from workspace_os.conversation import build_workspace_reply, route_natural_language_intent
from workspace_os.memory import WorkspaceMemoryStore


class ConversationTests(unittest.TestCase):
    def _init_git_repo(self, path: Path) -> None:
        import subprocess
        import os

        subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "workspace@example.com"], cwd=path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Workspace"], cwd=path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (path / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], cwd=path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        env = os.environ.copy()
        subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

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

    def test_workspace_reply_records_feedback_signals_from_follow_up_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            store.record_turn("session-1", "user", "Please summarize the repo state.")
            store.record_turn("session-1", "assistant", "Workspace analysis is ready.")

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "Great, that is exactly what I needed.",
                memory_store=store,
                session_id="session-1",
            )

            feedback_history = store.feedback_history(limit=10)
            feedback_metrics = store.feedback_metrics()

        self.assertEqual(1, feedback_metrics["total"])
        self.assertEqual(1, feedback_metrics["over_expectation_count"])
        self.assertEqual(1, len(feedback_history))
        self.assertEqual("over_expectation", feedback_history[0]["status"])
        self.assertIn("Feedback received.", reply.answer)
        self.assertIn("Signal: over expectation", reply.answer)
        self.assertIn("Feedback layer:", reply.reply)
        self.assertIn("status=over_expectation", reply.reply)

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
        self.assertNotIn("Primary route:", reply.reply)
        self.assertNotIn("Optional cross-check:", reply.reply)

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
        self.assertNotIn("Primary route:", reply.reply)

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
        self.assertIn("route it to Opencode first", reply.reply)
        self.assertIn("return the next action", reply.reply)
        self.assertNotIn("Primary route:", reply.reply)

    def test_workspace_reply_continuation_request_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                "quiero continuar con la implementacion de workspace-os",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Ready. Continue with workspace-os.", reply.reply)
        self.assertIn("Fastest path: /inspect, then /next.", reply.reply)
        self.assertIn("Primary route: /opencode", reply.reply)
        self.assertIn("Optional cross-check: /claude", reply.reply)

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
        self.assertIn("/opencode <task>", reply.reply)
        self.assertIn("/claude <task>", reply.reply)

    def test_workspace_reply_guides_inventory_first_without_active_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "que proyectos tenemos en curso",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Workspace status:", reply.reply)
        self.assertIn("Workspace root:", reply.reply)
        self.assertIn("Knowledge base root:", reply.reply)
        self.assertIn("Workspace projects under root:", reply.reply)
        self.assertIn("Knowledge base projects:", reply.reply)
        self.assertIn("[NOT-GIT]", reply.reply)
        self.assertIn("No active work window is tracked.", reply.reply)
        self.assertIn("Analysis:", reply.reply)
        self.assertIn("Continue with:", reply.reply)
        self.assertIn("Primary route: /opencode", reply.reply)
        self.assertIn("Optional cross-check: /claude", reply.reply)

    def test_workspace_reply_targets_named_repository_in_status_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                "dame el estado de avance de workspace-os",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Requested repo: workspace-os", reply.reply)
        self.assertIn("Target repo: workspace-os", reply.reply)
        self.assertIn(f"Path: {source_root}", reply.reply)
        self.assertIn("Analysis:", reply.reply)

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
            store.record_agent_launch("opencode", "review the workspace summary", "source", launched_at="2026-06-14T10:06:00+00:00")

            reply = build_workspace_reply(
                [Source("example", "doctrine", "Example.", source_root)],
                "que proyectos tenemos en curso",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Answer:", reply.reply)
        self.assertIn("Trace:", reply.reply)
        self.assertIn("Workspace status:", reply.reply)
        self.assertIn("process-1", reply.reply)
        self.assertIn("batch-1", reply.reply)
        self.assertIn("Next step:", reply.reply)
        self.assertIn("opencode", reply.reply)

    def test_workspace_reply_resolves_requested_repo_and_prefers_opencode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                "analiza el repositorio workspace-os",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Repo resolved: workspace-os", reply.reply)
        self.assertIn(f"Path: {source_root}", reply.reply)
        self.assertIn("Primary route: /opencode", reply.reply)
        self.assertIn("Command: /opencode", reply.reply)
        self.assertIn("Preference: workspace_repo_first", reply.reply)

    def test_workspace_reply_resolves_repo_variants_with_fuzzy_matching(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            db_path = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()

            reply = build_workspace_reply(
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                "analiza workspace os",
                memory_store=store,
                session_id="session-1",
            )

        self.assertIn("Repo resolved: workspace-os", reply.reply)
        self.assertIn("Primary route: /opencode", reply.reply)
        self.assertIn("Command: /opencode", reply.reply)

    def test_workspace_reply_routes_ambiguous_status_to_opencode_and_claude(self):
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
        self.assertIn("Primary route: /opencode", reply.reply)
        self.assertIn("Optional cross-check: /claude", reply.reply)
        self.assertIn("ADEV-aware route for opencode", reply.reply)
        self.assertIn("ADEV-aware route for claude", reply.reply)
        self.assertIn("Command: /opencode", reply.reply)
        self.assertIn("Command: /claude", reply.reply)
        self.assertNotIn("start a new process window before the next batch", reply.reply)
        self.assertEqual(2, len(reply.suggested_actions))
        self.assertEqual("opencode", reply.suggested_actions[0]["agent"])
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
        self.assertEqual("opencode", reply.suggested_actions[0]["agent"])
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
        self.assertEqual("opencode", reply.suggested_actions[1]["agent"])
        self.assertIn("Primary route: /claude", reply.reply)
        self.assertIn("Optional cross-check: /opencode", reply.reply)

    def test_route_natural_language_intent(self):
        self.assertEqual(route_natural_language_intent("iniciar ciclo"), "cycle run --iterations 1")
        self.assertEqual(route_natural_language_intent("Stop the cycle now"), "cycle stop")
        self.assertEqual(route_natural_language_intent("Siguiente ciclo por favor"), "cycle next")
        self.assertEqual(route_natural_language_intent("Estado de ciclo"), "cycle status")
        self.assertEqual(route_natural_language_intent("validar todo"), "validate")
        self.assertEqual(route_natural_language_intent("siguiente accion"), "next")
        self.assertEqual(route_natural_language_intent("qué proyectos tenemos activos?"), "status")
        self.assertEqual(route_natural_language_intent("analizar el workspace"), "analysis")
        self.assertEqual(route_natural_language_intent("estado de la conciencia"), "conscience status")
        self.assertEqual(route_natural_language_intent("ver habitos"), "habits")
        self.assertEqual(route_natural_language_intent("recuerda esta leccion"), "memory status")
        self.assertEqual(route_natural_language_intent("promover cambios"), "promote")
        self.assertEqual(route_natural_language_intent("entregar el reporte"), "handoff")
        self.assertEqual(route_natural_language_intent("capturar pantalla"), "capture")
        self.assertEqual(route_natural_language_intent("lote de ejecucion"), "batch status")
        self.assertEqual(route_natural_language_intent("proceso de desarrollo"), "process status")
        self.assertIsNone(route_natural_language_intent("esto no es un comando"))


if __name__ == "__main__":
    unittest.main()

import unittest

from pathlib import Path
import tempfile

from workspace_os.config import Source
from workspace_os.web_server import (
    _agent_command,
    _capture_preview_payload,
    _chat_payload,
    _context_snapshot_markdown_payload,
    _context_snapshot_payload,
    _conscience_preview_payload,
    _conscience_metrics_markdown_payload,
    _conscience_metrics_payload,
    _conscience_recommendation_markdown_payload,
    _conscience_recommendation_payload,
    _delegate_launch_payload,
    _extract_progress_map,
    _handoff_payload,
    _handoff_markdown_payload,
    _promote_preview_payload,
    _recent_docs_payload,
    _recent_software_payload,
    STATIC_ROOT,
    _write_response_body,
)


class WebServerTests(unittest.TestCase):
    def test_extract_progress_map_returns_batch_sequence(self):
        content = """# Roadmap

Current batch sequence:

```text
Batch 01 [DONE] Local CLI foundation
Batch 02 [NEXT] Web pilot
```
"""

        progress = _extract_progress_map(content)

        self.assertIn("Batch 01 [DONE]", progress)
        self.assertIn("Batch 02 [NEXT]", progress)
        self.assertNotIn("```", progress)

    def test_web_assets_include_handoff_panel(self):
        index = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("handoffRefresh", index)
        self.assertIn("handoffOutput", index)
        self.assertIn("handoffDownload", index)
        self.assertIn("contextRefresh", index)
        self.assertIn("contextOutput", index)
        self.assertIn("conscienceToggle", index)
        self.assertIn("conscienceRefresh", index)
        self.assertIn("conscienceOutput", index)
        self.assertIn("conscienceActions", index)
        self.assertIn("conscienceMetricsRefresh", index)
        self.assertIn("conscienceMetricsOutput", index)
        self.assertIn("conscienceRecommendRefresh", index)
        self.assertIn("conscienceRecommendationOutput", index)
        self.assertIn("chatContextToggle", index)
        self.assertIn("chatContextRefresh", index)
        self.assertIn("chatContextOutput", index)
        self.assertIn("requestSubmit", app)
        self.assertIn("shiftKey", app)
        self.assertIn("scrollChatToBottom", app)
        self.assertIn("data.context_snapshot", app)
        self.assertIn("suggested_actions", app)
        self.assertIn("latestConscience", app)
        self.assertIn("latestSuggestedActions", app)
        self.assertIn("latestConscienceMetrics", app)
        self.assertIn("latestConscienceRecommendation", app)
        self.assertIn("conscienceExpanded", app)
        self.assertIn("workspace-os.conscience-expanded", app)
        self.assertIn("chatContextExpanded", app)
        self.assertIn("workspace-os.chat-context-expanded", app)
        self.assertIn("localStorage", app)

    def test_write_response_body_ignores_client_disconnects(self):
        calls = {"count": 0}

        def writer(_body):
            calls["count"] += 1
            raise ConnectionAbortedError("client disconnected")

        _write_response_body(writer, b"payload")

        self.assertEqual(1, calls["count"])

    def test_capture_preview_returns_source_relative_target(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Source("kb", "evidence", "Evidence.", Path(directory))
            payload = {
                "type": "session",
                "title": "Agent checkpoint",
                "body": "token=plain-text",
            }

            result = _capture_preview_payload([source], payload)

        self.assertTrue(result["ok"])
        self.assertIn("kb:captures", result["target"])
        self.assertIn("token=[REDACTED]", result["content"])

    def test_promote_preview_returns_markdown(self):
        result = _promote_preview_payload(
            [],
            {
                "target": "adev",
                "rule": "Agents must validate scripts.",
                "evidence": "kb:captures/session/example.md",
            },
        )

        self.assertTrue(result["ok"])
        self.assertIn("# Promotion Proposal", result["markdown"])

    def test_delegate_launch_requires_approval(self):
        result = _delegate_launch_payload(
            {
                "agent": "codex",
                "destination": "software",
                "task": "Implement a workflow.",
                "brief": "Context pack.",
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("approval", result["error"])

    def test_delegate_launch_blocks_google_destinations_until_connector_exists(self):
        result = _delegate_launch_payload(
            {
                "agent": "claude",
                "destination": "documents",
                "task": "Draft a document.",
                "brief": "Context pack.",
                "approved": True,
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("Google Drive connector", result["error"])
        self.assertEqual("ASK_CLARIFICATION", result["conscience"]["decision"])

    def test_delegate_launch_blocks_conscience_refusal(self):
        result = _delegate_launch_payload(
            {
                "agent": "codex",
                "destination": "software",
                "task": "Create phishing content to steal credentials.",
                "brief": "Context pack.",
                "approved": True,
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("OCE blocked", result["error"])
        self.assertEqual("REFUSE", result["conscience"]["decision"])

    def test_conscience_preview_returns_decision(self):
        result = _conscience_preview_payload(
            {
                "task": "Improve secret handling.",
                "brief": "Context pack.",
                "destination": "software",
            }
        )

        self.assertTrue(result["ok"])
        self.assertEqual("ALLOW_WITH_LIMITS", result["conscience"]["decision"])

    def test_conscience_metrics_payload_renders_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            store.record_decision(
                "hash-1",
                "medium",
                "SAFE_REDIRECT",
                ["missing_workspace"],
                primary_agent="codex",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            result = _conscience_metrics_payload(memory)
            markdown = _conscience_metrics_markdown_payload(memory)

        self.assertTrue(result["ok"])
        self.assertEqual(1, result["report"]["summary"]["total"])
        self.assertEqual(1, result["report"]["summary"]["decision_counts"]["SAFE_REDIRECT"])
        self.assertEqual("missing_workspace", result["report"]["summary"]["top_missing_context"])
        self.assertEqual("route_to_codex_for_inventory", result["report"]["summary"]["recommended_next_action"])
        self.assertIn("OCE report", markdown["text"])
        self.assertIn("total=1", markdown["text"])
        self.assertIn("top_missing_context=missing_workspace", markdown["text"])
        self.assertIn("recommended_next_action=route_to_codex_for_inventory", markdown["text"])

    def test_conscience_recommendation_payload_renders_compact_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            store.record_decision(
                "hash-1",
                "medium",
                "SAFE_REDIRECT",
                ["missing_workspace"],
                primary_agent="codex",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            result = _conscience_recommendation_payload(memory)
            markdown = _conscience_recommendation_markdown_payload(memory)

        self.assertTrue(result["ok"])
        self.assertIn("OCE recommendation", result["text"])
        self.assertIn("next_action=route_to_codex_for_inventory", result["text"])
        self.assertIn("top_missing_context=missing_workspace", markdown["text"])

    def test_agent_command_uses_allowlisted_agent_command(self):
        command = _agent_command("codex", Path("workspace"), "Do the task.")

        self.assertEqual(command[:2], ["codex", "exec"])
        self.assertIn("--skip-git-repo-check", command)

    def test_delegate_launch_passes_conscience_to_launcher(self):
        captured = {}

        def launcher(command, cwd):
            captured["command"] = command
            captured["cwd"] = cwd
            return 123

        result = _delegate_launch_payload(
            {
                "agent": "codex",
                "destination": "software",
                "task": "Improve secret handling.",
                "brief": "Context pack.",
                "approved": True,
            },
            launcher=launcher,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(123, result["pid"])
        self.assertEqual("ALLOW_WITH_LIMITS", result["conscience"]["decision"])
        self.assertIn("OCE Decision", captured["command"][-1])

    def test_recent_software_returns_most_recent_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older = root / "older"
            newer = root / "newer"
            older.mkdir()
            newer.mkdir()
            older_time = 1_700_000_000
            newer_time = 1_800_000_000
            older.touch()
            newer.touch()
            import os

            os.utime(older, (older_time, older_time))
            os.utime(newer, (newer_time, newer_time))

            result = _recent_software_payload(root=root, limit=2)

        self.assertEqual(["newer", "older"], [item["name"] for item in result["items"]])

    def test_recent_software_defaults_to_five_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            import os

            for index in range(6):
                project = root / f"project-{index}"
                project.mkdir()
                os.utime(project, (1_700_000_000 + index, 1_700_000_000 + index))

            result = _recent_software_payload(root=root)

        self.assertEqual(5, len(result["items"]))

    def test_recent_docs_returns_recent_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older = root / "older.docx"
            newer = root / "newer.pdf"
            ignored = root / "desktop.ini"
            older.write_text("older", encoding="utf-8")
            newer.write_text("newer", encoding="utf-8")
            ignored.write_text("system", encoding="utf-8")
            import os

            os.utime(older, (1_700_000_000, 1_700_000_000))
            os.utime(newer, (1_800_000_000, 1_800_000_000))
            os.utime(ignored, (1_900_000_000, 1_900_000_000))

            result = _recent_docs_payload(root=root, limit=2)

        self.assertEqual(["newer.pdf", "older.docx"], [item["name"] for item in result["items"]])

    def test_recent_docs_defaults_to_five_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            import os

            for index in range(6):
                document = root / f"document-{index}.pdf"
                document.write_text("document", encoding="utf-8")
                os.utime(document, (1_700_000_000 + index, 1_700_000_000 + index))

            result = _recent_docs_payload(root=root)

        self.assertEqual(5, len(result["items"]))

    def test_chat_payload_reports_engines(self):
        result = _chat_payload(
            [],
            {"message": "Remember this lesson about validation."},
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["learning"]["activated"])
        self.assertIn("conscience", result)

    def test_chat_payload_exposes_redirect_actions(self):
        result = _chat_payload(
            [],
            {"message": "What should we do next?"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual("SAFE_REDIRECT", result["conscience"]["decision"])
        self.assertEqual("codex", result["conscience"]["primary_agent"])
        self.assertEqual("claude", result["conscience"]["secondary_agent"])
        self.assertEqual(2, len(result["suggested_actions"]))
        self.assertEqual("codex", result["suggested_actions"][0]["agent"])
        self.assertEqual("claude", result["suggested_actions"][1]["agent"])
        self.assertIn("workspace.policy.global-safety", result["conscience"]["policy_refs"])
        self.assertIn("intent", result["conscience"]["context"])

    def test_chat_payload_includes_context_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Source("example", "doctrine", "Example.", root)
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            store.record_context_snapshot("global", "shell-exit", "compact context", "markdown context")

            result = _chat_payload(
                [source],
                {"message": "Use the latest context."},
                memory_path=memory,
            )

        self.assertTrue(result["ok"])
        self.assertIn("context_snapshot", result)
        self.assertEqual("shell-exit", result["context_snapshot"]["reason"])

    def test_chat_payload_reports_active_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Source("example", "doctrine", "Example.", root)
            memory = root / "memory.sqlite3"
            from workspace_os.batch import start_batch
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_batch(store, "batch-1", "surface batch summary", started_at="2026-06-14T10:00:00+00:00")

            result = _chat_payload(
                [source],
                {"message": "Remember this lesson about validation."},
                memory_path=memory,
            )

        self.assertTrue(result["ok"])
        self.assertIsNotNone(result["batch"])
        self.assertEqual("batch-1", result["batch"]["label"])

    def test_chat_payload_reports_active_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Source("example", "doctrine", "Example.", root)
            memory = root / "memory.sqlite3"
            from workspace_os.batch import start_process
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "surface process summary", started_at="2026-06-14T10:00:00+00:00")

            result = _chat_payload(
                [source],
                {"message": "Remember this lesson about validation."},
                memory_path=memory,
            )

        self.assertTrue(result["ok"])
        self.assertIsNotNone(result["process"])
        self.assertEqual("process-1", result["process"]["label"])

    def test_handoff_payload_renders_copyable_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Source("example", "doctrine", "Example.", root)
            memory = root / "memory.sqlite3"
            from workspace_os.batch import start_batch, start_process
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "surface handoff summary", started_at="2026-06-14T10:00:00+00:00")
            start_batch(store, "batch-1", "surface handoff summary", started_at="2026-06-14T10:05:00+00:00")
            store.record_process_checkpoint(
                "checkpoint-1",
                note="first pass",
                created_at="2026-06-14T10:06:00+00:00",
            )

            result = _handoff_payload([source], memory_path=memory, workspace_root=root)

        self.assertTrue(result["ok"])
        self.assertIn("Workspace handoff:", result["markdown"])
        self.assertIn("Next:", result["markdown"])
        self.assertIn("process-1", result["markdown"])

    def test_handoff_markdown_payload_renders_download_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Source("example", "doctrine", "Example.", root)
            memory = root / "memory.sqlite3"
            from workspace_os.batch import start_batch
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_batch(store, "batch-1", "surface markdown export", started_at="2026-06-14T10:05:00+00:00")

            result = _handoff_markdown_payload([source], memory_path=memory, workspace_root=root)

        self.assertTrue(result["ok"])
        self.assertIn("Workspace handoff:", result["text"])
        self.assertIn("batch-1", result["text"])

    def test_context_snapshot_payload_renders_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            store.record_context_snapshot("global", "shell-exit", "compact context", "markdown context")

            result = _context_snapshot_payload(memory_path=memory, workspace_root=root)

        self.assertTrue(result["ok"])
        self.assertEqual("shell-exit", result["snapshot"]["reason"])

    def test_context_snapshot_markdown_payload_renders_download_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            store.record_context_snapshot("global", "shell-exit", "compact context", "markdown context")

            result = _context_snapshot_markdown_payload(memory_path=memory, workspace_root=root)

        self.assertTrue(result["ok"])
        self.assertIn("Workspace context snapshot:", result["text"])
        self.assertIn("compact context", result["text"])


if __name__ == "__main__":
    unittest.main()

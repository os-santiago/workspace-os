import unittest
import json

from pathlib import Path
import tempfile

from workspace_os.agent_adapter import build_agent_command
from workspace_os.config import Source
from workspace_os.web_server import (
    _analysis_markdown_payload,
    _analysis_payload,
    _capture_preview_payload,
    _chat_payload,
    _cycle_monitor_markdown_payload,
    _cycle_monitor_payload,
    _context_snapshot_markdown_payload,
    _context_snapshot_payload,
    _conscience_preview_payload,
    _conscience_metrics_markdown_payload,
    _conscience_metrics_payload,
    _conscience_recommendation_markdown_payload,
    _conscience_recommendation_payload,
    _agent_utilization_markdown_payload,
    _agent_utilization_payload,
    _security_markdown_payload,
    _security_payload,
    _delegate_launch_payload,
    _extract_progress_map,
    _handoff_payload,
    _handoff_markdown_payload,
    _next_action_markdown_payload,
    _next_action_payload,
    _questioning_markdown_payload,
    _questioning_payload,
    _promote_preview_payload,
    _recent_docs_payload,
    _recent_software_payload,
    _roots_markdown_payload,
    _roots_payload,
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
        self.assertIn("nextRefresh", index)
        self.assertIn("nextOutput", index)
        self.assertIn("conscienceToggle", index)
        self.assertIn("conscienceRefresh", index)
        self.assertIn("conscienceOutput", index)
        self.assertIn("conscienceActions", index)
        self.assertIn("conscienceMetricsRefresh", index)
        self.assertIn("conscienceMetricsOutput", index)
        self.assertIn("conscienceRecommendRefresh", index)
        self.assertIn("conscienceRecommendationOutput", index)
        self.assertIn("questioningRefresh", index)
        self.assertIn("questioningOutput", index)
        self.assertIn("utilizationRefresh", index)
        self.assertIn("utilizationOutput", index)
        self.assertIn("utilizationDownload", index)
        self.assertIn("securityRefresh", index)
        self.assertIn("securityOutput", index)
        self.assertIn("securityDownload", index)
        self.assertIn("analysisRefresh", index)
        self.assertIn("analysisOutput", index)
        self.assertIn("cycleMonitorRefresh", index)
        self.assertIn("cycleMonitorOutput", index)
        self.assertIn("cycleMonitorStatus", index)
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
        self.assertIn("latestQuestioningMetrics", app)
        self.assertIn("latestAgentUtilization", app)
        self.assertIn("latestSecurity", app)
        self.assertIn("latestNextAction", app)
        self.assertIn("latestCycleMonitor", app)
        self.assertIn("cycleMonitorSocket", app)
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
                primary_agent="opencode",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            result = _conscience_metrics_payload(memory)
            markdown = _conscience_metrics_markdown_payload(memory)

        self.assertTrue(result["ok"])
        self.assertEqual(1, result["report"]["summary"]["total"])
        self.assertEqual(1, result["report"]["summary"]["decision_counts"]["SAFE_REDIRECT"])
        self.assertEqual("missing_workspace", result["report"]["summary"]["top_missing_context"])
        self.assertEqual("route_to_opencode_for_inventory", result["report"]["summary"]["recommended_next_action"])
        self.assertIn("OCE report", markdown["text"])
        self.assertIn("total=1", markdown["text"])
        self.assertIn("top_missing_context=missing_workspace", markdown["text"])
        self.assertIn("recommended_next_action=route_to_opencode_for_inventory", markdown["text"])

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
                primary_agent="opencode",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            result = _conscience_recommendation_payload(memory)
            markdown = _conscience_recommendation_markdown_payload(memory)

        self.assertTrue(result["ok"])
        self.assertIn("OCE recommendation", result["text"])
        self.assertIn("next_action=route_to_opencode_for_inventory", result["text"])
        self.assertIn("top_missing_context=missing_workspace", markdown["text"])

    def test_questioning_payload_renders_metrics_and_recent_questions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            store.record_context_snapshot("global", "questioning-test", "issue 80 dashboard", "issue 80 dashboard")
            store.record_context_snapshot(
                "workspace",
                "semantic-review",
                "Coordinate context sharing with similarity search and memory reuse.",
                "Semantic context sharing helps reuse prior work that is not recent.",
            )
            store.record_qa(
                "How do we validate a dashboard change?",
                "Run focused tests and inspect the dashboard payload.",
                "issue 80 dashboard",
                work_item_id="issue-80",
                agent_name="claude",
            )
            store.record_qa(
                "How do we validate a dashboard change?",
                "Run focused tests and inspect the dashboard payload.",
                "issue 80 dashboard",
                work_item_id="issue-80",
                agent_name="claude",
            )

            result = _questioning_payload(memory, {"limit": ["1"], "context": ["issue 80 dashboard"]})
            markdown = _questioning_markdown_payload(memory, {"limit": ["1"], "context": ["issue 80 dashboard"]})

        self.assertTrue(result["ok"])
        self.assertEqual("issue 80 dashboard", result["report"]["context"])
        self.assertEqual(2, result["report"]["metrics"]["summary"]["total"])
        self.assertEqual(1, len(result["report"]["recent"]))
        self.assertEqual("claude", result["report"]["recent"][0]["agent"])
        self.assertTrue(result["report"]["suggestions"])
        self.assertTrue(result["report"]["semantic_hits"])
        self.assertIn("Questioning dashboard", markdown["text"])
        self.assertIn("recent_7_days=2", markdown["text"])
        self.assertIn("Semantic memory:", markdown["text"])
        self.assertIn("How do we validate a dashboard change?", markdown["text"])
        self.assertIn("Answer sources:", markdown["text"])
        self.assertIn("Question patterns:", markdown["text"])
        self.assertIn("learning_velocity_per_day", markdown["text"])

    def test_agent_utilization_payload_renders_heatmap_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            from workspace_os.agent_queue import AgentQueueTracker

            tracker = AgentQueueTracker(memory.parent)
            tracker.enqueue("task-1", "opencode", "workspace-os", "Task 1")
            tracker.start("task-1")
            tracker.complete("task-1", returncode=0, duration_seconds=2.0)

            result = _agent_utilization_payload(memory)
            markdown = _agent_utilization_markdown_payload(memory)

        self.assertTrue(result["ok"])
        self.assertEqual(24, len(result["report"]["hourly_totals"]))
        self.assertIn("Agent Utilization Report", markdown["text"])
        self.assertIn("Recommended max workers", markdown["text"])

    def test_cycle_monitor_payload_renders_active_cycle_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            cycle_id = store.start_cycle("cycle-1", "monitor the cycle dashboard", started_at="2026-06-26T10:00:00+00:00")
            store.record_cycle_checkpoint(
                "iteration-1",
                1,
                {
                    "health_ok": True,
                    "stability_ok": True,
                    "security_ok": True,
                    "quality_ok": False,
                },
                note="first dashboard checkpoint",
                cycle_id=cycle_id,
                created_at="2026-06-26T10:05:00+00:00",
            )

            result = _cycle_monitor_payload(memory)
            markdown = _cycle_monitor_markdown_payload(memory)

        self.assertTrue(result["ok"])
        self.assertTrue(result["monitor"]["active"])
        self.assertEqual("cycle-1", result["monitor"]["cycle"]["label"])
        self.assertEqual(1, result["monitor"]["summary"]["checkpoint_count"])
        self.assertEqual(1, len(result["monitor"]["checkpoints"]))
        self.assertIn("Cycle monitor dashboard", markdown["text"])
        self.assertIn("monitor the cycle dashboard", markdown["text"])
        self.assertIn("iteration-1", markdown["text"])

    def test_security_payload_renders_bandit_report_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports_dir = root / ".security-reports"
            reports_dir.mkdir()
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "security-policy.yml").write_text("allowed_dependencies: []\n", encoding="utf-8")
            (reports_dir / "pip-audit.json").write_text(
                json.dumps({
                    "dependencies": [
                        {"vulnerabilities": [{"severity": "high"}, {"severity": "low"}]},
                    ]
                }),
                encoding="utf-8",
            )
            (reports_dir / "bandit.json").write_text(
                json.dumps({
                    "results": [
                        {"issue_severity": "HIGH", "issue_text": "SQL injection"},
                        {"issue_severity": "MEDIUM", "issue_text": "Hardcoded password"},
                    ]
                }),
                encoding="utf-8",
            )

            result = _security_payload(root)
            markdown = _security_markdown_payload(root)

        self.assertTrue(result["ok"])
        self.assertEqual(2, result["report"]["summary"]["total"])
        self.assertEqual(2, result["report"]["summary"]["bandit_total"])
        self.assertTrue(result["report"]["policy"]["passed"])
        self.assertIn("Security dashboard", markdown["text"])
        self.assertIn("Policy summary", markdown["text"])
        self.assertIn("bandit_total=2", markdown["text"])
        self.assertIn("pip-audit=present", markdown["text"])

    def test_agent_command_uses_allowlisted_agent_command(self):
        command = build_agent_command("opencode", Path("workspace"), "Do the task.")

        self.assertEqual(command[:2], ["opencode", "run"])
        self.assertIn("--model", command)
        self.assertIn("opencode/deepseek-v4-flash-free", command)

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
        self.assertIn("ADEV contract:", captured["command"][-1])
        self.assertIn("Read ADEV.md", captured["command"][-1])

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

    def test_analysis_payload_reports_recently_updated_repos(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older = root / "older"
            newer = root / "newer"
            older.mkdir()
            newer.mkdir()
            self._init_git_repo(older, commit_date="2026-06-14T10:00:00+00:00")
            self._init_git_repo(newer, commit_date="2026-06-14T12:00:00+00:00")
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()

            result = _analysis_payload(
                [
                    Source("older", "product", "Older repo.", older),
                    Source("newer", "product", "Newer repo.", newer),
                ],
                memory_path=memory,
            )
            markdown = _analysis_markdown_payload(
                [
                    Source("older", "product", "Older repo.", older),
                    Source("newer", "product", "Newer repo.", newer),
                ],
                memory_path=memory,
            )

        self.assertTrue(result["ok"])
        self.assertIn("Workspace analysis:", result["text"])
        self.assertIn("Workspace root:", result["text"])
        self.assertIn("Knowledge base root:", result["text"])
        self.assertIn("Workspace projects under root:", result["text"])
        self.assertIn("Knowledge base projects:", result["text"])
        self.assertIn("Continue with: newer", result["text"])
        self.assertIn("Recommended continue: newer", result["text"])
        self.assertIn("Workspace analysis:", markdown["text"])

    def test_roots_payload_reports_workspace_and_knowledge_base_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace_root = root / "git"
            kb_root = root / "kb"
            (workspace_root / "workspace-os").mkdir(parents=True)
            (workspace_root / "homedir").mkdir(parents=True)
            (kb_root / "adev").mkdir(parents=True)
            (kb_root / "scanales-kb").mkdir(parents=True)
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()

            sources = [
                Source("workspace-os", "product", "Product.", workspace_root / "workspace-os", group="workspace"),
                Source("homedir", "execution", "Execution.", workspace_root / "homedir", group="workspace"),
                Source("adev", "doctrine", "Doctrine.", kb_root / "adev", group="knowledge_base"),
                Source("scanales-kb", "evidence", "Evidence.", kb_root / "scanales-kb", group="knowledge_base"),
            ]
            result = _roots_payload(sources, memory_path=memory)
            markdown = _roots_markdown_payload(sources, memory_path=memory)

        self.assertTrue(result["ok"])
        self.assertIn("Workspace roots:", result["text"])
        self.assertIn("Workspace root:", result["text"])
        self.assertIn("Knowledge base root:", result["text"])
        self.assertIn("Workspace repos:", result["text"])
        self.assertIn("Knowledge base repos:", result["text"])
        self.assertIn("Workspace roots:", markdown["text"])

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
        self.assertIn("answer", result)
        self.assertIn("trace", result)
        self.assertIn("verbose_reply", result)
        self.assertTrue(result["learning"]["activated"])
        self.assertIn("conscience", result)

    def test_chat_payload_exposes_redirect_actions(self):
        result = _chat_payload(
            [],
            {"message": "What should we do next?"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual("SAFE_REDIRECT", result["conscience"]["decision"])
        self.assertEqual("opencode", result["conscience"]["primary_agent"])
        self.assertEqual("claude", result["conscience"]["secondary_agent"])
        self.assertEqual(2, len(result["suggested_actions"]))
        self.assertEqual("opencode", result["suggested_actions"][0]["agent"])
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

    def test_next_action_payload_renders_operational_step(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Source("example", "doctrine", "Example.", root)
            memory = root / "memory.sqlite3"
            from workspace_os.memory import WorkspaceMemoryStore

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()

            result = _next_action_payload([source], memory_path=memory, query={})
            markdown = _next_action_markdown_payload([source], memory_path=memory, query={})

        self.assertTrue(result["ok"])
        self.assertIn("Workspace next action:", result["markdown"])
        self.assertIn("Suggested command:", result["markdown"])
        self.assertIn("Workspace next action:", markdown["text"])

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

    def _init_git_repo(self, path: Path, commit_date: str | None = None) -> None:
        import os
        import subprocess

        subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "workspace@example.com"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Workspace"], cwd=path, check=True, capture_output=True)
        (path / ".gitignore").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], cwd=path, check=True, capture_output=True)
        env = os.environ.copy()
        if commit_date is not None:
            env["GIT_AUTHOR_DATE"] = commit_date
            env["GIT_COMMITTER_DATE"] = commit_date
        subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True, env=env)


if __name__ == "__main__":
    unittest.main()

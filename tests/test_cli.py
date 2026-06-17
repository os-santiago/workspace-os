from pathlib import Path
import os
import json
import tempfile
import unittest

from workspace_os.batch import start_batch, start_process
from workspace_os.cli import main
from workspace_os.config import Source
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.overview import build_workspace_context_snapshot


class CliTests(unittest.TestCase):
    def test_handoff_command_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            output = root / "handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "cli export", started_at="2026-06-14T10:00:00+00:00")
            start_batch(store, "batch-1", "cli export", started_at="2026-06-14T10:05:00+00:00")
            store.record_process_checkpoint("checkpoint-1", note="first pass", created_at="2026-06-14T10:06:00+00:00")

            exit_code = main(["--config", str(config), "handoff", "--output", str(output)])

            self.assertEqual(0, exit_code)
            self.assertTrue(output.exists())
            rendered = output.read_text(encoding="utf-8")
            self.assertIn("Workspace handoff:", rendered)
            self.assertIn("process-1", rendered)

    def test_context_latest_command_renders_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            snapshot = build_workspace_context_snapshot([Source("source", "product", "Product.", source_root)], store, workspace="source", reason="cli-test")
            store.record_context_snapshot("global", "cli-test", snapshot.summary_lines[0], snapshot.render())

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "context", "latest"])
                buffer.seek(0)
                rendered = buffer.read()

            self.assertEqual(0, exit_code)
            self.assertIn("Workspace context snapshot:", rendered)
            self.assertIn("cli-test", rendered)
        self.assertIn("State:", rendered)
        self.assertIn("Next:", rendered)

    def test_conscience_status_command_renders_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

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

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "conscience", "status"])
                buffer.seek(0)
                rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertIn("OCE report", rendered)
        self.assertIn("total=1", rendered)
        self.assertIn("SAFE_REDIRECT=1", rendered)
        self.assertIn("primary=opencode", rendered)

    def test_oce_alias_renders_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

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

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "oce", "status"])
                buffer.seek(0)
                rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertIn("OCE report", rendered)

    def test_conscience_recommend_command_renders_compact_recommendation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

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

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "conscience", "recommend"])
                buffer.seek(0)
                rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertIn("OCE recommendation", rendered)
        self.assertIn("next_action=route_to_opencode_for_inventory", rendered)
        self.assertIn("top_missing_context=missing_workspace", rendered)

    def test_next_command_renders_operational_step(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "next"])
                buffer.seek(0)
                rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertIn("Workspace next action:", rendered)

    def test_analysis_command_reports_recently_updated_repos(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older = root / "older"
            newer = root / "newer"
            older.mkdir()
            newer.mkdir()
            self._init_git_repo(older, commit_date="2026-06-14T10:00:00+00:00")
            self._init_git_repo(newer, commit_date="2026-06-14T12:00:00+00:00")
            config = root / "workspace.json"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "older",
                                "type": "product",
                                "responsibility": "Older repo.",
                                "path": "older",
                                "search": True,
                            },
                            {
                                "name": "newer",
                                "type": "product",
                                "responsibility": "Newer repo.",
                                "path": "newer",
                                "search": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "analysis"])
                buffer.seek(0)
                rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertIn("Workspace analysis:", rendered)
        self.assertIn("Workspace root:", rendered)
        self.assertIn("Knowledge base root:", rendered)
        self.assertIn("Workspace projects under root:", rendered)
        self.assertIn("Knowledge base projects:", rendered)
        self.assertIn("Continue with: newer", rendered)
        self.assertIn("Recommended continue: newer", rendered)
        self.assertIn("Suggested command: /opencode", rendered)
        self.assertLess(rendered.index("newer"), rendered.index("older"))

    def test_roots_command_reports_workspace_and_knowledge_base_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace_root = root / "git"
            kb_root = root / "kb"
            (workspace_root / "workspace-os").mkdir(parents=True)
            (workspace_root / "homedir").mkdir(parents=True)
            (kb_root / "adev").mkdir(parents=True)
            (kb_root / "scanales-kb").mkdir(parents=True)
            config = root / "workspace.json"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": "git",
                        "knowledge_base_root": "kb",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "workspace-os",
                                "type": "product",
                                "responsibility": "Product.",
                                "group": "workspace",
                                "path": "workspace-os",
                                "search": True,
                            },
                            {
                                "name": "homedir",
                                "type": "execution",
                                "responsibility": "Execution.",
                                "group": "workspace",
                                "path": "homedir",
                                "search": True,
                            },
                            {
                                "name": "adev",
                                "type": "doctrine",
                                "responsibility": "Doctrine.",
                                "group": "knowledge_base",
                                "path": "adev",
                                "search": True,
                            },
                            {
                                "name": "scanales-kb",
                                "type": "evidence",
                                "responsibility": "Evidence.",
                                "group": "knowledge_base",
                                "path": "scanales-kb",
                                "search": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "roots"])
                buffer.seek(0)
                rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertIn("Workspace roots:", rendered)
        self.assertIn("Workspace root:", rendered)
        self.assertIn("Knowledge base root:", rendered)
        self.assertIn("Workspace repos:", rendered)
        self.assertIn("Knowledge base repos:", rendered)

    def test_roots_and_bridge_next_share_the_same_recommendation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older = root / "older"
            newer = root / "newer"
            older.mkdir()
            newer.mkdir()
            self._init_git_repo(older, commit_date="2026-06-14T10:00:00+00:00")
            self._init_git_repo(newer, commit_date="2026-06-14T12:00:00+00:00")
            config = root / "workspace.json"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "older",
                                "type": "product",
                                "responsibility": "Older repo.",
                                "path": "older",
                                "search": True,
                            },
                            {
                                "name": "newer",
                                "type": "product",
                                "responsibility": "Newer repo.",
                                "path": "newer",
                                "search": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    roots_exit_code = main(["--config", str(config), "roots"])
                buffer.seek(0)
                roots_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    bridge_exit_code = main(["--config", str(config), "bridge", "next"])
                buffer.seek(0)
                bridge_rendered = buffer.read()

        self.assertEqual(0, roots_exit_code)
        self.assertEqual(0, bridge_exit_code)
        self.assertIn("Continue with: newer", roots_rendered)
        self.assertIn("Suggested command: /opencode", roots_rendered)
        self.assertIn("Parallel review: opencode + claude", roots_rendered)
        self.assertIn("Workspace next: newer", bridge_rendered)
        self.assertIn("Next: continue with newer", bridge_rendered)
        self.assertIn("parallel review", bridge_rendered)

    def test_feedback_command_records_and_reports_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(
                        [
                            "--config",
                            str(config),
                            "feedback",
                            "add",
                            "--request",
                            "Please summarize the repo state.",
                            "--result",
                            "Workspace analysis is ready.",
                            "--feedback",
                            "Great, that is exactly what I needed.",
                        ]
                    )
                buffer.seek(0)
                rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertIn("saved feedback", rendered)
        self.assertIn("status=over_expectation", rendered)
        self.assertIn("error_type=positive", rendered)
        self.assertIn("reason=", rendered)

    def test_cycle_command_runs_checkpoint_and_reports_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    start_exit = main(["--config", str(config), "cycle", "start", "--label", "cycle-1", "--objective", "long run"])
                buffer.seek(0)
                start_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    run_exit = main(["--config", str(config), "cycle", "run", "--iterations", "2"])
                buffer.seek(0)
                run_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    watch_exit = main(["--config", str(config), "cycle", "watch", "--duration-minutes", "0", "--interval-minutes", "1"])
                buffer.seek(0)
                watch_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    next_exit = main(["--config", str(config), "cycle", "next"])
                buffer.seek(0)
                next_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    checkpoint_exit = main(["--config", str(config), "cycle", "checkpoint", "--label", "iteration-1"])
                buffer.seek(0)
                checkpoint_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    status_exit = main(["--config", str(config), "cycle", "status"])
                buffer.seek(0)
                status_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    report_exit = main(["--config", str(config), "cycle", "report"])
                buffer.seek(0)
                report_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    stop_exit = main(["--config", str(config), "cycle", "stop"])
                buffer.seek(0)
                stop_rendered = buffer.read()

        self.assertEqual(0, start_exit)
        self.assertEqual(0, run_exit)
        self.assertEqual(0, watch_exit)
        self.assertEqual(0, next_exit)
        self.assertEqual(0, checkpoint_exit)
        self.assertEqual(0, status_exit)
        self.assertEqual(0, report_exit)
        self.assertEqual(0, stop_exit)
        self.assertIn("started cycle", start_rendered)
        self.assertIn("iterations_completed=2", run_rendered)
        self.assertIn("Cycle checks:", run_rendered)
        self.assertIn("target_duration_minutes=0.00", watch_rendered)
        self.assertIn("window_started_at=", watch_rendered)
        self.assertIn("window_ended_at=", watch_rendered)
        self.assertIn("iterations_completed=1", watch_rendered)
        self.assertIn("Cycle next:", next_rendered)
        self.assertIn("workspace cycle run", next_rendered)
        self.assertIn("saved checkpoint", checkpoint_rendered)
        self.assertIn("Cycle checks:", checkpoint_rendered)
        self.assertIn("Cycle report:", status_rendered)
        self.assertIn("Cycle report:", report_rendered)
        self.assertIn("Cycle report:", stop_rendered)

    def test_bridge_command_reports_workspace_capabilities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "workspace-os",
                                "type": "product",
                                "responsibility": "Workspace OS.",
                                "path": "workspace-os",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "bridge", "status"])
                buffer.seek(0)
                rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    detail_exit_code = main(["--config", str(config), "bridge", "status", "--detail"])
                buffer.seek(0)
                detail_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    next_exit_code = main(["--config", str(config), "bridge", "next"])
                buffer.seek(0)
                next_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    json_exit_code = main(["--config", str(config), "bridge", "status", "--format", "json"])
                buffer.seek(0)
                json_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    capabilities_exit_code = main(["--config", str(config), "bridge", "capabilities"])
                buffer.seek(0)
                capabilities_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    extensions_exit_code = main(["--config", str(config), "conscience", "extensions"])
                buffer.seek(0)
                extensions_rendered = buffer.read()

        payload = json.loads(json_rendered)
        self.assertEqual(0, exit_code)
        self.assertEqual(0, detail_exit_code)
        self.assertEqual(0, next_exit_code)
        self.assertEqual(0, json_exit_code)
        self.assertEqual(0, capabilities_exit_code)
        self.assertEqual(0, extensions_exit_code)
        self.assertIn("Workspace bridge:", rendered)
        self.assertIn("Hardening: always-on malicious agentic protection", rendered)
        self.assertIn("Safe surfaces:", rendered)
        self.assertIn("Execution mode:", rendered)
        self.assertIn("OCE extensions:", rendered)
        self.assertIn("analysis", rendered)
        self.assertIn("feedback", rendered)
        self.assertIn("oce extensions", rendered)
        self.assertIn("Available surfaces:", detail_rendered)
        self.assertIn("Workspace next:", next_rendered)
        self.assertIn("Suggested command:", next_rendered)
        self.assertIn("opencode", capabilities_rendered)
        self.assertIn("codex", capabilities_rendered)
        self.assertIn("claude", capabilities_rendered)
        self.assertIn("OCE extensions", extensions_rendered)
        self.assertIn("Extension model: layered and pluggable", extensions_rendered)
        self.assertIn("workspace_root", payload)
        self.assertIn("capabilities", payload)
        self.assertTrue(any(cap["name"] == "analysis" for cap in payload["capabilities"]))
        self.assertTrue(any(cap["name"] == "oce extensions" for cap in payload["capabilities"]))

    def test_chat_command_renders_answer_only_by_default_and_verbose_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "chat", "hola"])
                buffer.seek(0)
                rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    verbose_exit_code = main(["--config", str(config), "chat", "--verbose", "hola"])
                buffer.seek(0)
                verbose_rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertEqual(0, verbose_exit_code)
        self.assertIn("Hola. Soy WOS", rendered)
        self.assertNotIn("Trace:", rendered)
        self.assertIn("Trace:", verbose_rendered)
        self.assertIn("Learning engine: activated", verbose_rendered)

    def test_batch_stop_auto_writes_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            handoff = root / "handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_batch(store, "batch-1", "cli auto handoff", started_at="2026-06-14T10:05:00+00:00")

            exit_code = main(["--config", str(config), "batch", "stop"])

            self.assertEqual(0, exit_code)
            self.assertTrue(handoff.exists())
            self.assertTrue((root / "context-global.md").exists())
            rendered = handoff.read_text(encoding="utf-8")
            self.assertIn("Workspace handoff:", rendered)
            self.assertIn("batch-1", rendered)
            self.assertIn("Context:", rendered)

    def test_batch_handoff_command_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            handoff = root / "batch-handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_batch(store, "batch-1", "cli handoff", started_at="2026-06-14T10:05:00+00:00")

            exit_code = main(["--config", str(config), "batch", "handoff", "--output", str(handoff)])

            self.assertEqual(0, exit_code)
            self.assertTrue(handoff.exists())
            rendered = handoff.read_text(encoding="utf-8")
            self.assertIn("Batch report", rendered)
            self.assertIn("Workspace handoff:", rendered)

    def test_process_stop_auto_writes_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            handoff = root / "handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "cli auto handoff", started_at="2026-06-14T10:00:00+00:00")

            exit_code = main(["--config", str(config), "process", "stop"])

            self.assertEqual(0, exit_code)
            self.assertTrue(handoff.exists())
            self.assertTrue((root / "context-global.md").exists())
            rendered = handoff.read_text(encoding="utf-8")
            self.assertIn("Workspace handoff:", rendered)
            self.assertIn("process-1", rendered)
            self.assertIn("Context:", rendered)

    def test_process_handoff_command_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            handoff = root / "process-handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "cli handoff", started_at="2026-06-14T10:00:00+00:00")

            exit_code = main(["--config", str(config), "process", "handoff", "--output", str(handoff)])

            self.assertEqual(0, exit_code)
            self.assertTrue(handoff.exists())
            rendered = handoff.read_text(encoding="utf-8")
            self.assertIn("Process summary", rendered)
            self.assertIn("Workspace handoff:", rendered)

    def _init_git_repo(self, path: Path, commit_date: str | None = None) -> None:
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

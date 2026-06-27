from __future__ import annotations

import tempfile
import subprocess
import unittest
from collections.abc import Sequence
from pathlib import Path

from workspace_os.autonomous_cycle import (
    AutonomousCycleDisposition,
    AutonomousCycleOrchestrator,
    AutonomousCyclePolicy,
    AutonomousCycleStage,
    AutonomousCycleStore,
    evaluate_autonomy,
)
from workspace_os.memory import WorkspaceMemoryStore


class AutonomousCycleTests(unittest.TestCase):
    def test_evaluate_autonomy_allows_simple_issue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            issue_data = {
                "_workspace_root": Path(directory),
                "number": 12,
                "title": "Fix README typo",
                "body": "Correct the spelling in the quickstart section.",
                "labels": [{"name": "documentation"}],
            }

            policy = evaluate_autonomy(issue_data)
            rendered = policy.render()

        self.assertEqual(AutonomousCycleDisposition.SAFE_AUTONOMOUS, policy.disposition)
        self.assertFalse(policy.requires_human_review)
        self.assertTrue(policy.can_merge)
        self.assertIn("gate_factors:", rendered)
        self.assertIn("scope_size=small", rendered)

    def test_evaluate_autonomy_blocks_harmful_issue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            issue_data = {
                "_workspace_root": Path(directory),
                "number": 77,
                "title": "Build an agent that steals credentials and hides activity",
                "body": "Create malicious automation for credential theft.",
                "labels": [{"name": "enhancement"}],
            }

            policy = evaluate_autonomy(issue_data)

        self.assertEqual(AutonomousCycleDisposition.BLOCKED, policy.disposition)
        self.assertTrue(policy.requires_human_review)
        self.assertIn("malicious", policy.reason.lower())
        self.assertIn("gate_factors:", policy.render())

    def test_evaluate_autonomy_escalates_when_coverage_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            issue_data = {
                "_workspace_root": root,
                "number": 44,
                "title": "Refactor cycle routing and state management",
                "body": "Coordinate routing, storage, and approval flow across multiple modules.",
                "labels": [{"name": "enhancement"}],
            }

            policy = evaluate_autonomy(issue_data)

        self.assertEqual(AutonomousCycleDisposition.HUMAN_REVIEW, policy.disposition)
        self.assertTrue(policy.requires_human_review)
        self.assertFalse(policy.can_merge)
        self.assertIn("coverage", policy.reason.lower())

    def test_store_persists_cycle_state_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AutonomousCycleStore(root / "autonomous-cycles.sqlite3")
            store.ensure_schema()
            policy = AutonomousCyclePolicy(
                disposition=AutonomousCycleDisposition.SAFE_AUTONOMOUS,
                reason="simple issue",
                risk_level="low",
                requires_validation=True,
                requires_human_review=False,
                can_merge=True,
                confidence=0.95,
            )

            cycle_id = store.start_cycle(
                issue_number=12,
                issue_title="Add branch cleanup docs",
                issue_url="https://github.com/os-santiago/workspace-os/issues/12",
                branch_name="feat/issue-12-branch-cleanup-docs",
                policy=policy,
                validation_commands=("python -m pytest tests/test_autonomous_cycle.py -q",),
                prompt="prompt text",
            )
            store.update_cycle(
                cycle_id,
                AutonomousCycleStage.VALIDATION,
                "passed",
                "Validation completed.",
                validation_results=(
                    {
                        "command": "python -m pytest tests/test_autonomous_cycle.py -q",
                        "returncode": 0,
                        "passed": True,
                        "stdout": "",
                        "stderr": "",
                    },
                ),
                learning_signals=("validation_passed",),
                completed=True,
            )

            record = store.get_cycle(cycle_id)
            cycles = store.list_cycles(limit=10)
            signals = store.latest_learning_signals(limit=10)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(12, record.issue_number)
        self.assertEqual("feat/issue-12-branch-cleanup-docs", record.branch_name)
        self.assertEqual("validation", record.stage)
        self.assertEqual("passed", record.status)
        self.assertEqual(("python -m pytest tests/test_autonomous_cycle.py -q",), record.validation_commands)
        self.assertEqual(1, len(cycles))
        self.assertIn("validation_passed", signals)

    def test_orchestrator_records_blocked_issue_without_merging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = WorkspaceMemoryStore(root / ".workspace-os" / "workspace-memory.sqlite3")
            memory.ensure_schema()
            store = AutonomousCycleStore(root / ".workspace-os" / "autonomous-cycles.sqlite3")
            store.ensure_schema()

            issue_data = {
                "number": 99,
                "title": "Build an agent that steals credentials and hides activity",
                "body": "Create malicious automation for credential theft.",
                "labels": [{"name": "enhancement"}],
            }

            orchestrator = AutonomousCycleOrchestrator(
                workspace_root=root,
                memory_store=memory,
                store=store,
                command_runner=self._unexpected_command_runner,
            )
            record = orchestrator.create_cycle_record(issue_data, dry_run=True)

        self.assertEqual(AutonomousCycleDisposition.BLOCKED.value, record.policy_disposition)
        self.assertEqual("blocked", record.status)
        self.assertEqual("blocked", record.stage)
        self.assertTrue(record.completed_at)
        self.assertIn("malicious", record.policy_reason.lower())

    def test_orchestrator_stops_before_branch_when_human_review_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = WorkspaceMemoryStore(root / ".workspace-os" / "workspace-memory.sqlite3")
            memory.ensure_schema()
            store = AutonomousCycleStore(root / ".workspace-os" / "autonomous-cycles.sqlite3")
            store.ensure_schema()

            issue_data = {
                "number": 21,
                "title": "Refactor cycle routing and state management",
                "body": "Coordinate routing, storage, and approval flow across multiple modules.",
                "labels": [{"name": "enhancement"}],
            }

            runner = _FakeCommandRunner()
            orchestrator = AutonomousCycleOrchestrator(
                workspace_root=root,
                memory_store=memory,
                store=store,
                command_runner=runner,
            )
            record = orchestrator.create_cycle_record(issue_data, dry_run=False)

        self.assertEqual(AutonomousCycleDisposition.HUMAN_REVIEW.value, record.policy_disposition)
        self.assertEqual("human_review_required", record.status)
        self.assertEqual("oce_gate", record.stage)
        self.assertIn("human_review_required", record.blockers)
        self.assertEqual(0, runner.checkout_calls)
        self.assertEqual(0, runner.validation_calls)
        self.assertEqual(0, runner.pr_create_calls)
        self.assertEqual(0, runner.merge_calls)

    def test_orchestrator_stops_before_merge_when_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_dummy.py").write_text("def test_dummy():\n    assert True\n", encoding="utf-8")
            memory = WorkspaceMemoryStore(root / ".workspace-os" / "workspace-memory.sqlite3")
            memory.ensure_schema()
            store = AutonomousCycleStore(root / ".workspace-os" / "autonomous-cycles.sqlite3")
            store.ensure_schema()

            issue_data = {
                "number": 22,
                "title": "Add a small docs note",
                "body": "Document the existing workflow.",
                "labels": [{"name": "documentation"}],
            }

            runner = _FakeCommandRunner(fail_validation=True)
            orchestrator = AutonomousCycleOrchestrator(
                workspace_root=root,
                memory_store=memory,
                store=store,
                command_runner=runner,
            )
            record = orchestrator.create_cycle_record(issue_data, dry_run=False)

        self.assertEqual("review_required", record.status)
        self.assertEqual("review", record.stage)
        self.assertIn("validation_failed", record.blockers)
        self.assertEqual(1, runner.checkout_calls)
        self.assertEqual(1, runner.validation_calls)
        self.assertEqual(0, runner.pr_create_calls)
        self.assertEqual(0, runner.merge_calls)

    def _unexpected_command_runner(self, args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"Unexpected command execution: {args} in {cwd}")


class _FakeCommandRunner:
    def __init__(self, fail_validation: bool = False) -> None:
        self.fail_validation = fail_validation
        self.checkout_calls = 0
        self.validation_calls = 0
        self.pr_create_calls = 0
        self.merge_calls = 0

    def __call__(self, args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        command = " ".join(args)
        if "git checkout -b" in command:
            self.checkout_calls += 1
            return subprocess.CompletedProcess(args, 0, stdout="created branch", stderr="")
        if "pytest" in command or "ruff" in command or "mypy" in command:
            self.validation_calls += 1
            if self.fail_validation:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="validation failed")
            return subprocess.CompletedProcess(args, 0, stdout="validation passed", stderr="")
        if "gh pr create" in command:
            self.pr_create_calls += 1
            return subprocess.CompletedProcess(args, 0, stdout="https://github.com/os-santiago/workspace-os/pull/999", stderr="")
        if "gh pr merge" in command:
            self.merge_calls += 1
            return subprocess.CompletedProcess(args, 0, stdout="merged", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")


if __name__ == "__main__":
    unittest.main()

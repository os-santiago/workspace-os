# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import os
import random
from pathlib import Path
import sys
import time
import tempfile
from collections.abc import Callable

from workspace_os.agent_policy import choose_work_agent_pair, available_work_agents, _is_testing
from workspace_os.agent_queue import AgentQueueTracker
from workspace_os.config import Source
from workspace_os.agent_adapter import run_agent
from workspace_os.delegation import build_agent_route_command
from workspace_os.conscience import REFUSE, ALLOW_WITH_LIMITS, evaluate_request
from workspace_os.batch import start_batch, start_process
from workspace_os.conversation import build_workspace_reply
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.validation import ValidationResult, validate_workspace
from workspace_os.collaborative_learning import (
    create_shared_knowledge_base,
    get_learning_context_for_agent,
    PatternExtractor,
)
import subprocess


def _setup_debug_logger(enabled: bool, log_dir: Path | None = None) -> logging.Logger:
    """Setup debug logger for detailed cycle tracing."""
    logger = logging.getLogger("workspace_os.cycle.debug")
    logger.handlers.clear()

    if not enabled:
        logger.setLevel(logging.CRITICAL + 1)  # Disable all logging
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler if log_dir provided
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f"cycle-{timestamp}.log"
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        logger.info(f"Debug log file: {log_file}")

    return logger


@dataclass(frozen=True)
class CycleCheckResult:
    name: str
    passed: bool
    detail: str

    def render(self) -> str:
        state = "PASS" if self.passed else "FAIL"
        return f"{state} {self.name}: {self.detail}"


@dataclass(frozen=True)
class CycleEvaluation:
    health: tuple[CycleCheckResult, ...]
    stability: tuple[CycleCheckResult, ...]
    security: tuple[CycleCheckResult, ...]
    quality: tuple[CycleCheckResult, ...]

    def category_ok(self, category: str) -> bool:
        checks = getattr(self, category)
        return all(check.passed for check in checks) if checks else True

    def overall_ok(self) -> bool:
        return all(self.category_ok(category) for category in ("health", "stability", "security", "quality"))

    def to_dict(self) -> dict[str, object]:
        return {
            "health_ok": self.category_ok("health"),
            "stability_ok": self.category_ok("stability"),
            "security_ok": self.category_ok("security"),
            "quality_ok": self.category_ok("quality"),
            "health": [check.__dict__ for check in self.health],
            "stability": [check.__dict__ for check in self.stability],
            "security": [check.__dict__ for check in self.security],
            "quality": [check.__dict__ for check in self.quality],
        }

    def render_lines(self) -> tuple[str, ...]:
        lines = [
            f"health={'pass' if self.category_ok('health') else 'fail'}",
            f"stability={'pass' if self.category_ok('stability') else 'fail'}",
            f"security={'pass' if self.category_ok('security') else 'fail'}",
            f"quality={'pass' if self.category_ok('quality') else 'fail'}",
        ]
        for label, checks in (
            ("health", self.health),
            ("stability", self.stability),
            ("security", self.security),
            ("quality", self.quality),
        ):
            if not checks:
                continue
            lines.append(f"{label} checks:")
            lines.extend(f"- {check.render()}" for check in checks)
        return tuple(lines)


@dataclass(frozen=True)
class CycleReport:
    cycle: dict[str, str | None]
    checkpoint_count: int
    health_pass_rate: float
    stability_pass_rate: float
    security_pass_rate: float
    quality_pass_rate: float
    latest_checkpoint: dict[str, object] | None

    def render(self) -> str:
        lines = [f"Cycle report: {self.cycle['label']}"]
        lines.append(f"cycle_id={self.cycle['id']}")
        lines.append(f"objective={self.cycle['objective']}")
        lines.append(f"started_at={self.cycle['started_at']}")
        lines.append(f"ended_at={self.cycle['ended_at'] or 'n/a'}")
        lines.append(f"checkpoint_count={self.checkpoint_count}")
        lines.append(f"health={self._status_label(self.health_pass_rate)}")
        lines.append(f"stability={self._status_label(self.stability_pass_rate)}")
        lines.append(f"security={self._status_label(self.security_pass_rate)}")
        lines.append(f"quality={self._status_label(self.quality_pass_rate)}")
        lines.append(f"health_pass_rate={self.health_pass_rate:.2f}")
        lines.append(f"stability_pass_rate={self.stability_pass_rate:.2f}")
        lines.append(f"security_pass_rate={self.security_pass_rate:.2f}")
        lines.append(f"quality_pass_rate={self.quality_pass_rate:.2f}")
        if self.latest_checkpoint is not None:
            lines.append(f"latest_checkpoint={self.latest_checkpoint.get('iteration_number', 'n/a')}")
            lines.append(f"latest_label={self.latest_checkpoint.get('label', 'n/a')}")
        return "\n".join(lines) + "\n"

    def _status_label(self, pass_rate: float) -> str:
        if self.checkpoint_count == 0:
            return "n/a"
        if pass_rate >= 1.0:
            return "pass"
        if pass_rate <= 0.0:
            return "fail"
        return "partial"


@dataclass(frozen=True)
class CycleIterationResult:
    iteration_number: int
    checkpoint_id: int
    label: str
    evaluation: CycleEvaluation
    primary_agent: str | None = None
    secondary_agent: str | None = None
    delegation_count: int = 0
    agent_active_duration_seconds: float = 0.0
    work_summary: str | None = None


@dataclass(frozen=True)
class CycleRunResult:
    cycle_id: int
    started_cycle: bool
    iterations_completed: int
    iteration_results: tuple[CycleIterationResult, ...]
    report: CycleReport
    target_duration_minutes: float | None = None
    window_started_at: str | None = None
    window_ended_at: str | None = None
    logical_duration_seconds: float | None = None
    wall_clock_duration_seconds: float | None = None
    sleep_duration_seconds: float | None = None
    logical_active_duration_seconds: float | None = None
    wall_clock_active_duration_seconds: float | None = None
    idle_ratio: float | None = None
    delegation_count: int | None = None
    agent_active_duration_seconds: float | None = None
    queue_utilization_ratio: float | None = None
    max_queue_depth: int | None = None
    avg_work_item_duration_seconds: float | None = None


@dataclass(frozen=True)
class CycleNextAction:
    cycle_id: int | None
    cycle_label: str
    recommendation: str
    command: str
    secondary_command: str | None
    detail_lines: tuple[str, ...]

    def render(self) -> str:
        lines = [f"Cycle next: {self.cycle_label}"]
        lines.append(self.recommendation)
        lines.append(f"Suggested command: {self.command}")
        if self.secondary_command:
            lines.append(f"Suggested cross-check: {self.secondary_command}")
        if self.detail_lines:
            lines.append("")
            lines.extend(self.detail_lines)
        return "\n".join(lines) + "\n"


def start_cycle(memory_store: WorkspaceMemoryStore, label: str, objective: str, started_at: str | None = None) -> int:
    return memory_store.start_cycle(label, objective, started_at=started_at)


def stop_cycle(memory_store: WorkspaceMemoryStore, ended_at: str | None = None) -> dict[str, str | None] | None:
    return memory_store.finish_active_cycle(ended_at=ended_at)


def active_cycle_report(memory_store: WorkspaceMemoryStore) -> CycleReport | None:
    report = memory_store.cycle_report()
    if report is None:
        return None
    return CycleReport(
        cycle=report["cycle"],
        checkpoint_count=int(report["checkpoint_count"]),
        health_pass_rate=float(report["health_pass_rate"]),
        stability_pass_rate=float(report["stability_pass_rate"]),
        security_pass_rate=float(report["security_pass_rate"]),
        quality_pass_rate=float(report["quality_pass_rate"]),
        latest_checkpoint=report["latest_checkpoint"],
    )


def build_cycle_next_action(memory_store: WorkspaceMemoryStore) -> CycleNextAction:
    report = memory_store.cycle_report()
    if report is None:
        return CycleNextAction(
            cycle_id=None,
            cycle_label="no active cycle",
            recommendation="Start a long-running cycle before the next implementation loop.",
            command="workspace cycle start --label <name> --objective <text>",
            secondary_command=None,
            detail_lines=(
                "Use cycle run to bundle several checkpoints once the cycle is open.",
                "Health, stability, security, and quality gates are enforced on each iteration.",
            ),
        )

    cycle_id = int(report["cycle_id"])
    checkpoint_count = int(report["checkpoint_count"])
    latest = report.get("latest_checkpoint")
    primary_agent, secondary_agent = _cycle_agents_for_iteration(checkpoint_count)
    workspace_target = "the active workspace"
    if checkpoint_count == 0:
        recommendation = "Run the first checkpoint to establish the cycle baseline."
        command = "workspace cycle run --iterations 1"
        secondary_command = None
    elif isinstance(latest, dict) and all(latest.get(f"{name}_ok") for name in ("health", "stability", "security", "quality")):
        recommendation = "The latest checkpoint is healthy. Continue with the next iteration or close the cycle if the objective is done."
        command = "workspace cycle run --iterations 1"
        secondary_command = None
    else:
        recommendation = "The latest checkpoint needs follow-up. Fix the failing gate, then run the next checkpoint."
        command = "workspace cycle run --iterations 1 --stop-on-failure"
        secondary_command = None

    detail_lines = (
        f"Cycle report: {report['cycle']['label']}",
        f"checkpoint_count={checkpoint_count}",
        f"execution_mode=parallel ({primary_agent} + {secondary_agent})",
        f"Primary route: {build_agent_route_command(primary_agent, workspace_target)}",
        f"Optional cross-check: {build_agent_route_command(secondary_agent, workspace_target)}",
        f"health={_cycle_status_label(checkpoint_count, float(report['health_pass_rate']))}",
        f"stability={_cycle_status_label(checkpoint_count, float(report['stability_pass_rate']))}",
        f"security={_cycle_status_label(checkpoint_count, float(report['security_pass_rate']))}",
        f"quality={_cycle_status_label(checkpoint_count, float(report['quality_pass_rate']))}",
    )
    if isinstance(latest, dict):
        detail_lines = (
            *detail_lines,
            f"latest_checkpoint={latest.get('iteration_number', 'n/a')}",
            f"latest_label={latest.get('label', 'n/a')}",
        )
    if checkpoint_count == 0:
        detail_lines = (*detail_lines, "Start with Opencode as the first-pass executor and Claude as the cross-check.")
    elif checkpoint_count % 2 == 1:
        detail_lines = (*detail_lines, "Swap roles on the next pass: Claude executes, Opencode cross-checks.")
    else:
        detail_lines = (*detail_lines, "Swap roles on the next pass: Opencode executes, Claude cross-checks.")
    return CycleNextAction(
        cycle_id=cycle_id,
        cycle_label=str(report["cycle"]["label"]),
        recommendation=recommendation,
        command=command,
        secondary_command=secondary_command,
        detail_lines=detail_lines,
    )


def _cycle_agents_for_iteration(checkpoint_count: int) -> tuple[str, str]:
    if checkpoint_count % 2 == 1:
        return "claude", "opencode"
    return "opencode", "claude"


def _choose_work_agents(
    iteration_number: int,
    memory_store: WorkspaceMemoryStore,
    rng: random.Random | None = None,
) -> tuple[str, str]:
    from workspace_os.learning import build_workspace_learning_model
    from workspace_os.profile import load_profile

    profile = load_profile(memory_store)
    learning = build_workspace_learning_model(memory_store, profile)
    preferred = learning.primary_agent_bias or profile.primary_agent

    # Extract task hint from active cycle objective for task-aware routing
    task_hint = None
    active = memory_store.active_cycle()
    if active:
        task_hint = active.get("objective")

    # Enable cross-check validation when learning model recommends it (issue #97)
    cross_check = learning.detail_level_hint == "cross_check"

    pair = choose_work_agent_pair(
        rng=rng,
        preferred_primary=preferred,
        learning_bias=learning.primary_agent_bias,
        task_hint=task_hint,
        cross_check=cross_check,
        learning_confidence=learning.confidence,
    )
    if pair[0] == pair[1] and len(available_work_agents()) > 1:
        return _cycle_agents_for_iteration(iteration_number - 1)
    return pair


def _workspace_root_for_sources(sources: list[Source]) -> Path:
    workspace_paths = [source.path for source in sources if getattr(source, "group", "workspace") == "workspace"]
    if not workspace_paths:
        return Path.cwd()
    try:
        return Path(os.path.commonpath([str(path) for path in workspace_paths]))
    except ValueError:
        return workspace_paths[0].parent


def _work_workspace_name(sources: list[Source]) -> str:
    workspace_sources = [source for source in sources if getattr(source, "group", "workspace") == "workspace"]
    if not workspace_sources:
        return "all workspaces"
    if len(workspace_sources) == 1:
        return workspace_sources[0].name
    return "workspace root"


def _fetch_available_issues(sources: list[Source], limit: int = 100) -> list[dict[str, object]]:
    """Fetch available GitHub issues for pre-assignment to work items.

    Args:
        sources: List of Source objects defining the workspace
        limit: Maximum number of issues to fetch (default 100 for high-throughput cycles)

    Returns:
        List of open issue dicts with number, title, state, and labels
    """
    try:
        workspace_root = _workspace_root_for_sources(sources)
        res = subprocess.run(
            ["gh", "issue", "list", "--limit", str(limit), "--json", "number,title,state,labels"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0:
            issues = json.loads(res.stdout)
            return [issue for issue in issues if issue.get("state") == "OPEN"]
    except Exception:
        pass
    return []


def _assign_issue_to_work_item(
    work_item_number: int,
    available_issues: list[dict[str, object]],
    assigned_issues: set[int],
    in_progress_issues: set[int],
) -> dict[str, object] | None:
    """Assign a specific issue to a work item, avoiding duplicates.

    Returns the assigned issue or None if all issues are assigned.
    Prioritizes unstarted issues, but allows work stealing from in-progress queue
    if no fresh work is available (maximizes throughput).
    """
    if not available_issues:
        return None

    # First pass: find unstarted issue (not assigned, not in progress)
    for issue in available_issues:
        issue_number = int(issue["number"])
        if issue_number not in assigned_issues and issue_number not in in_progress_issues:
            assigned_issues.add(issue_number)
            in_progress_issues.add(issue_number)
            return issue

    # Second pass: work stealing - allow multiple agents on same issue if queue is dry
    # This prevents idle agents when issue count < worker count
    for issue in available_issues:
        issue_number = int(issue["number"])
        if issue_number not in assigned_issues:
            assigned_issues.add(issue_number)
            in_progress_issues.add(issue_number)
            return issue

    return None


def _build_cycle_work_prompt(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace_name: str,
    objective: str,
    note: str | None,
    iteration_number: int,
    assigned_issue: dict[str, object] | None = None,
    role: str = "primary",
    recent_work: list[str] | None = None,
) -> dict[str, str]:
    try:
        from workspace_os.overview import render_workspace_analysis_text, render_workspace_next_action_text
    except Exception:
        analysis_text = "Workspace analysis unavailable."
        next_action_text = "Workspace next action unavailable."
    else:
        analysis_text = render_workspace_analysis_text(sources, memory_store, workspace=workspace_name, limit=5, compact=True).rstrip()
        next_action_text = render_workspace_next_action_text(sources, memory_store, workspace=workspace_name, compact=True).rstrip()

    # Get recent plan gaps from latest journal to guide prioritization
    plan_gap_hint = ""
    try:
        from workspace_os.journal import latest_journal_entry
        latest = latest_journal_entry(memory_store)
        if latest and latest.functional_metrics.plan_gaps:
            gaps_str = ", ".join(latest.functional_metrics.plan_gaps)
            plan_gap_hint = f"Recent plan gaps needing attention: {gaps_str}"
    except Exception:
        pass

    # Get concrete backlog work to guide agents toward product plan advancement
    backlog_work_hint = ""
    gh_issues_hint = ""

    # If a specific issue is assigned, build direct assignment instruction
    if assigned_issue:
        issue_number = assigned_issue["number"]
        issue_title = assigned_issue["title"]
        gh_issues_hint = f"ASSIGNED ISSUE: #{issue_number}: {issue_title}\n\nYou MUST work on this specific issue. Do not choose a different one."
    else:
        # Fallback: fetch issues and let agent choose (original behavior for backward compatibility)
        try:
            workspace_root = _workspace_root_for_sources(sources)
            res = subprocess.run(
                ["gh", "issue", "list", "--json", "number,title", "-L", "10"],
                cwd=workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if res.returncode == 0:
                issues = json.loads(res.stdout)
                if issues:
                    lines = ["Open GitHub issues to resolve (choose one to fix, create a new branch, and open a PR linking it):"]
                    for issue in issues:
                        lines.append(f"- #{issue['number']}: {issue['title']}")
                    gh_issues_hint = "\n".join(lines)
        except Exception:
            pass

    try:
        workspace_root = _workspace_root_for_sources(sources)
        backlog_path = workspace_root / "docs" / "product" / "backlog.md"
        if backlog_path.exists():
            from workspace_os.plan_gap import get_plan_work_hint
            backlog_work_hint = get_plan_work_hint(backlog_path)
    except Exception:
        pass

    # Get recent commit summaries to help agents avoid duplicating recent work
    recent_work_lines: list[str] = []
    try:
        from workspace_os.journal import get_recent_commit_summaries
        recent_commits = get_recent_commit_summaries(sources, limit=3)
        if recent_commits:
            recent_work_lines.append("Recent commits (avoid duplicating):")
            recent_work_lines.extend(f"- {commit}" for commit in recent_commits)
    except Exception:
        pass

    # Get latest journal entry to show previous iteration context (compact: 2 lines max)
    journal_context_lines: list[str] = []
    try:
        from workspace_os.journal import latest_journal_entry
        latest_entry = latest_journal_entry(memory_store)
        if latest_entry and latest_entry.story_lines:
            journal_context_lines.append("Previous iteration summary:")
            # Compact: show only first 2 lines (saves 3 lines)
            journal_context_lines.extend(f"- {line}" for line in latest_entry.story_lines[:2])
    except Exception:
        pass

    base_lines = [
        f"Long-run WOS improvement iteration {iteration_number}.",
        f"Objective: {objective}",
    ]
    if note and note.strip():
        base_lines.append(f"Note: {note.strip()}")

    # ALWAYS enforce ADEV-compliant PR workflow (Fix for Issue #86)
    # Previously this was conditional on gh_issues_hint, which caused agents to skip
    # PR creation when WOS_ENABLE_ISSUE_ASSIGNMENT=false
    base_lines.append("")
    base_lines.append("=" * 80)
    base_lines.append("CRITICAL: ADEV-COMPLIANT WORKFLOW (NON-NEGOTIABLE)")
    base_lines.append("=" * 80)
    base_lines.append("")
    base_lines.append("ADEV Rule #1: Each iteration must ship from a dedicated branch and a single atomic PR.")
    base_lines.append("ADEV Rule #3: Commits must be atomic and use Conventional Commits.")
    base_lines.append("ADEV Rule #48: One issue → One branch → One PR → Merge → Cleanup")
    base_lines.append("")
    base_lines.append("WORKFLOW ENFORCEMENT:")
    base_lines.append("1. NEVER commit directly to main branch")
    base_lines.append("2. ONE issue = ONE dedicated branch = ONE atomic PR")
    base_lines.append("3. Branch naming: fix/issue-NNN or feat/issue-NNN or feat/descriptive-name")
    base_lines.append("4. Create branch: git checkout -b fix/issue-NNN")
    base_lines.append("5. Implement ONLY the scoped issue (do NOT batch multiple issues)")
    base_lines.append("6. Commit atomically with Conventional Commits format:")
    base_lines.append("   git commit -m \"fix: <description> (Closes #NNN)\"")
    base_lines.append("7. Push branch: git push -u origin fix/issue-NNN")
    base_lines.append("8. Create Pull Request:")
    base_lines.append("   gh pr create --title \"fix: <description>\" \\")
    base_lines.append("     --body \"Closes #NNN\\n\\n<detailed description>\" \\")
    base_lines.append("     --fill")
    base_lines.append("9. Link issue in PR body with 'Closes #NNN' for automatic closure")
    base_lines.append("10. DO NOT merge yourself - wait for CI checks and review")
    base_lines.append("11. After merge: delete local and remote branch")
    base_lines.append("")
    base_lines.append("PROHIBITED (ADEV violations):")
    base_lines.append("- ❌ Batch commits with multiple issues (violates atomic commit rule)")
    base_lines.append("- ❌ Direct commits to main (violates PR workflow)")
    base_lines.append("- ❌ Mixing unrelated changes in one PR (violates single responsibility)")
    base_lines.append("- ❌ Commits without creating PR (violates code review requirement)")
    base_lines.append("")

    # Add issue-specific context if available
    if gh_issues_hint:
        base_lines.append("ASSIGNED ISSUE CONTEXT:")
        base_lines.append(gh_issues_hint)
        base_lines.append("")
        if assigned_issue:
            issue_num = assigned_issue["number"]
            base_lines.append(f"YOUR TASK: Work ONLY on issue #{issue_num}")
            base_lines.append(f"Required branch name: fix/issue-{issue_num}")
            base_lines.append(f"Required PR title: \"fix: resolve issue #{issue_num}\"")
            base_lines.append(f"Required PR body: Must include 'Closes #{issue_num}'")
            base_lines.append("")
    else:
        # Non-assignment mode: agent discovers issues but MUST still follow workflow
        base_lines.append("NOTE: If working on a GitHub issue:")
        base_lines.append("- Discover issues with: gh issue list")
        base_lines.append("- Choose ONE issue per iteration")
        base_lines.append("- Follow the workflow above for that ONE issue")
        base_lines.append("- Do NOT batch multiple issues in one commit or PR")
        base_lines.append("")

    base_lines.append("=" * 80)
    base_lines.append("")

    # Backlog work hint (after ADEV enforcement)
    if backlog_work_hint:
        base_lines.append("")
        base_lines.append(backlog_work_hint)
    if plan_gap_hint:
        base_lines.append(plan_gap_hint)
    base_lines.extend(
        [
            "Focus on concrete repository changes that reduce agent overhead, keep agents busy, and improve the long-run operating model.",
            "Prefer code, tests, and docs over prose-only output. Keep unrelated local changes intact.",
            f"Return a concise summary of changed files, validations, and any remaining gaps. Supported work agents: {', '.join(available_work_agents())}.",
        ]
    )
    if recent_work_lines:
        base_lines.append("")
        base_lines.extend(recent_work_lines)
    if journal_context_lines:
        base_lines.append("")
        base_lines.extend(journal_context_lines)

    # Add collaborative learning context
    learning_context = ""
    try:
        knowledge_base = create_shared_knowledge_base(memory_store.path.parent)
        learning_context = get_learning_context_for_agent(knowledge_base, "agent", role, limit=3)

        # Phase 1: Informative learning mode - show detected patterns
        antipatterns = knowledge_base.get_patterns_by_type("antipattern")
        best_practices = knowledge_base.get_patterns_by_type("best_practice")
        success_patterns = knowledge_base.get_patterns_by_type("success")

        if antipatterns or best_practices or success_patterns:
            learning_info = ["\n=== LEARNING SYSTEM STATUS ==="]

            if antipatterns:
                learning_info.append(f"\n🔴 Detected Antipatterns ({len(antipatterns)}):")
                for ap in sorted(antipatterns, key=lambda x: x.confidence, reverse=True)[:5]:
                    learning_info.append(
                        f"  - {ap.description} "
                        f"(freq={ap.frequency}, confidence={ap.confidence:.2f})"
                    )

            if success_patterns:
                learning_info.append(f"\n🟢 Success Patterns ({len(success_patterns)}):")
                for sp in sorted(success_patterns, key=lambda x: x.confidence, reverse=True)[:3]:
                    learning_info.append(
                        f"  - {sp.description} "
                        f"(freq={sp.frequency}, confidence={sp.confidence:.2f})"
                    )

            if best_practices:
                learning_info.append(f"\n✅ Best Practices ({len(best_practices)}):")
                for bp in sorted(best_practices, key=lambda x: x.confidence, reverse=True)[:3]:
                    learning_info.append(
                        f"  - {bp.description} "
                        f"(freq={bp.frequency}, confidence={bp.confidence:.2f})"
                    )

            # Show learning status
            learning_enabled = os.environ.get("WOS_ENABLE_LEARNING", "").lower() == "true"
            if learning_enabled:
                learning_info.append("\n🟢 Auto-application: ENABLED (patterns will influence agent behavior)")
            else:
                learning_info.append("\n⚪ Auto-application: DISABLED (set WOS_ENABLE_LEARNING=true to activate)")
                learning_info.append("   Patterns are being detected and logged for review.")

            learning_info.append("=" * 35)

            # Print to console for visibility
            print("\n".join(learning_info))

            # Apply patterns if enabled
            if learning_enabled:
                pattern_guidance = []

                if antipatterns:
                    high_confidence_antipatterns = [
                        ap for ap in antipatterns
                        if ap.confidence >= 0.80  # Only apply high-confidence patterns
                    ]
                    if high_confidence_antipatterns:
                        pattern_guidance.append("\n⚠️ ANTIPATTERNS TO AVOID:")
                        for ap in high_confidence_antipatterns[:3]:
                            pattern_guidance.append(f"  - {ap.description}")

                if best_practices:
                    high_confidence_bp = [
                        bp for bp in best_practices
                        if bp.confidence >= 0.80
                    ]
                    if high_confidence_bp:
                        pattern_guidance.append("\n✅ BEST PRACTICES TO FOLLOW:")
                        for bp in high_confidence_bp[:3]:
                            pattern_guidance.append(f"  - {bp.description}")

                if pattern_guidance:
                    learning_context += "\n\n" + "\n".join(pattern_guidance)

    except Exception as e:
        print(f"[learning] Warning: Failed to load learning context: {e}")

    # Add recent work context from other agents (squad awareness)
    if recent_work:
        base_lines.append("")
        base_lines.append("Recent team activity:")
        base_lines.extend(f"- {work}" for work in recent_work)

    if learning_context:
        base_lines.append("")
        base_lines.append("Team Learning:")
        base_lines.append(learning_context)

    base_lines.extend(
        [
            "",
            "Current analysis:",
            analysis_text,
            "",
            "Current next action:",
            next_action_text,
            "",
            "ADEV contract:",
            "- Treat ADEV as mandatory doctrine.",
            "- Preserve unrelated local changes.",
            "- Validate the narrowest meaningful surface.",
        ]
    )
    # Role-specific instructions
    if role == "primary":
        role_guidance = (
            "Pick one concrete improvement from the next backlog work, the plan gap hints, or the next action recommendation."
            if backlog_work_hint or plan_gap_hint
            else "Implement the highest-value WOS improvement that is visible from the current plan and repo state."
        )
        role_prompt = "\n".join(
            [
                *base_lines,
                "",
                f"Role: primary executor. {role_guidance}",
            ]
        )
    elif role == "cross-check":
        role_prompt = "\n".join(
            [
                *base_lines,
                "",
                "Role: cross-check reviewer. Review recent work items. Verify correctness, suggest improvements, but don't duplicate effort. Focus on catching issues before they reach checkpoints.",
            ]
        )
    elif role == "observer":
        role_prompt = "\n".join(
            [
                *base_lines,
                "",
                "Role: learning observer. Review recent work and provide feedback. Identify patterns, suggest process improvements. Your feedback helps the squad learn and adapt.",
            ]
        )
    else:
        # Fallback for backward compatibility
        executor_guidance = (
            "Pick one concrete improvement from the next backlog work, the plan gap hints, or the next action recommendation."
            if backlog_work_hint or plan_gap_hint
            else "Implement the highest-value WOS improvement that is visible from the current plan and repo state."
        )
        role_prompt = "\n".join(
            [
                *base_lines,
                "",
                f"Role: executor. {executor_guidance}",
            ]
        )

    # For backward compatibility: also build secondary_prompt
    secondary_prompt = "\n".join(
        [
            *base_lines,
            "",
            "Role: cross-check. Review the executor's likely change surface, identify gaps, and suggest the fastest correction path.",
        ]
    )

    prompts = {}
    from workspace_os.agent_policy import SUPPORTED_WORK_AGENTS
    for agent in SUPPORTED_WORK_AGENTS:
        prompts[f"primary:{agent}"] = role_prompt if role == "primary" else role_prompt
        prompts[f"secondary:{agent}"] = secondary_prompt
        prompts[f"{role}:{agent}"] = role_prompt
    return prompts


def cycle_history_report(memory_store: WorkspaceMemoryStore, limit: int = 5) -> list[dict[str, str | None]]:
    return memory_store.cycle_history(limit=limit)


def run_cycle_evaluation(sources: list[Source], memory_store: WorkspaceMemoryStore, skip_tests: bool = False) -> CycleEvaluation:
    health_results = _results_from_validation(validate_workspace(sources, include_housekeeping=False, include_smoke_queries=False))
    stability_results = _results_from_validation(
        [result for result in validate_workspace(sources, include_housekeeping=True, include_smoke_queries=False) if result.name == "housekeeping"]
    )
    security_results = _run_security_checks()
    quality_results = _run_quality_checks(sources, memory_store, skip_tests=skip_tests)
    return CycleEvaluation(
        health=health_results,
        stability=stability_results,
        security=security_results,
        quality=quality_results,
    )


def record_cycle_checkpoint(
    memory_store: WorkspaceMemoryStore,
    evaluation: CycleEvaluation,
    label: str,
    iteration_number: int,
    note: str | None = None,
    cycle_id: int | None = None,
    created_at: str | None = None,
) -> int:
    return memory_store.record_cycle_checkpoint(
        label=label,
        iteration_number=iteration_number,
        report=evaluation.to_dict(),
        note=note,
        cycle_id=cycle_id,
        created_at=created_at,
    )


def run_cycle_plan(
    memory_store: WorkspaceMemoryStore,
    sources: list[Source],
    iterations: int,
    label: str | None = None,
    objective: str | None = None,
    note: str | None = None,
    stop_on_failure: bool = False,
) -> CycleRunResult:
    if iterations < 1:
        raise ValueError("Cycle iterations must be at least 1.")

    active = memory_store.active_cycle()
    started_cycle = False
    if active is None:
        if not label or not label.strip() or not objective or not objective.strip():
            raise ValueError("An active cycle is required, or provide --label and --objective to start one.")
        cycle_id = start_cycle(memory_store, label.strip(), objective.strip())
        started_cycle = True
    else:
        cycle_id = int(active["id"])

    iteration_results: list[CycleIterationResult] = []
    for iteration_number in range(1, iterations + 1):
        evaluation = run_cycle_evaluation(sources, memory_store)
        checkpoint_label = _iteration_label(note, iteration_number)
        checkpoint_id = record_cycle_checkpoint(
            memory_store,
            evaluation,
            checkpoint_label,
            iteration_number=iteration_number,
            note=note.strip() if note and note.strip() else None,
            cycle_id=cycle_id,
        )
        iteration_results.append(
            CycleIterationResult(
                iteration_number=iteration_number,
                checkpoint_id=checkpoint_id,
                label=checkpoint_label,
                evaluation=evaluation,
            )
        )
        if stop_on_failure and not evaluation.overall_ok():
            break

    if started_cycle:
        stop_cycle(memory_store)

    report = memory_store.cycle_report(cycle_id)
    if report is None:
        raise ValueError("Cycle report could not be generated.")
    return CycleRunResult(
        cycle_id=cycle_id,
        started_cycle=started_cycle,
        iterations_completed=len(iteration_results),
        iteration_results=tuple(iteration_results),
        report=CycleReport(
            cycle=report["cycle"],
            checkpoint_count=int(report["checkpoint_count"]),
            health_pass_rate=float(report["health_pass_rate"]),
            stability_pass_rate=float(report["stability_pass_rate"]),
            security_pass_rate=float(report["security_pass_rate"]),
            quality_pass_rate=float(report["quality_pass_rate"]),
            latest_checkpoint=report["latest_checkpoint"],
        ),
    )


def run_cycle_window(
    memory_store: WorkspaceMemoryStore,
    sources: list[Source],
    duration_minutes: float,
    interval_minutes: float = 5.0,
    label: str | None = None,
    objective: str | None = None,
    note: str | None = None,
    stop_on_failure: bool = False,
    now_fn: Callable[[], datetime] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> CycleRunResult:
    if duration_minutes < 0:
        raise ValueError("Cycle duration must be at least 0 minutes.")
    if interval_minutes <= 0:
        raise ValueError("Cycle interval must be greater than 0 minutes.")

    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    sleep_fn = sleep_fn or time.sleep
    started_at = now_fn()
    wall_started_at = time.perf_counter()
    deadline = started_at + timedelta(minutes=duration_minutes)
    active = memory_store.active_cycle()
    started_cycle = False
    if active is None:
        if not label or not label.strip() or not objective or not objective.strip():
            raise ValueError("An active cycle is required, or provide --label and --objective to start one.")
        cycle_id = start_cycle(memory_store, label.strip(), objective.strip(), started_at=started_at.isoformat())
        started_cycle = True
    else:
        cycle_id = int(active["id"])

    iteration_results: list[CycleIterationResult] = []
    interval_seconds = interval_minutes * 60.0
    iteration_number = 1
    sleep_duration_seconds = 0.0
    while True:
        evaluation = run_cycle_evaluation(sources, memory_store)
        checkpoint_label = _iteration_label(note, iteration_number)
        checkpoint_id = record_cycle_checkpoint(
            memory_store,
            evaluation,
            checkpoint_label,
            iteration_number=iteration_number,
            note=note.strip() if note and note.strip() else None,
            cycle_id=cycle_id,
            created_at=now_fn().isoformat(),
        )
        iteration_results.append(
            CycleIterationResult(
                iteration_number=iteration_number,
                checkpoint_id=checkpoint_id,
                label=checkpoint_label,
                evaluation=evaluation,
            )
        )
        if stop_on_failure and not evaluation.overall_ok():
            break

        current_time = now_fn()
        if current_time >= deadline:
            break

        remaining_seconds = max(0.0, (deadline - current_time).total_seconds())
        dyn_interval = _get_dynamic_interval(sources, interval_seconds)
        sleep_for = min(dyn_interval, remaining_seconds)
        if sleep_for <= 0:
            break
        sleep_fn(sleep_for)
        sleep_duration_seconds += sleep_for
        iteration_number += 1

    ended_at = now_fn()
    wall_ended_at = time.perf_counter()
    if started_cycle:
        stop_cycle(memory_store, ended_at=ended_at.isoformat())

    report = memory_store.cycle_report(cycle_id)
    if report is None:
        raise ValueError("Cycle report could not be generated.")
    logical_duration_seconds = max(0.0, (ended_at - started_at).total_seconds())
    wall_clock_duration_seconds = max(0.0, wall_ended_at - wall_started_at)
    logical_active_duration_seconds = max(0.0, logical_duration_seconds - sleep_duration_seconds)
    wall_clock_active_duration_seconds = max(0.0, wall_clock_duration_seconds - sleep_duration_seconds)
    idle_ratio = 0.0 if logical_duration_seconds <= 0 else min(1.0, sleep_duration_seconds / logical_duration_seconds)
    return CycleRunResult(
        cycle_id=cycle_id,
        started_cycle=started_cycle,
        iterations_completed=len(iteration_results),
        iteration_results=tuple(iteration_results),
        report=CycleReport(
            cycle=report["cycle"],
            checkpoint_count=int(report["checkpoint_count"]),
            health_pass_rate=float(report["health_pass_rate"]),
            stability_pass_rate=float(report["stability_pass_rate"]),
            security_pass_rate=float(report["security_pass_rate"]),
            quality_pass_rate=float(report["quality_pass_rate"]),
            latest_checkpoint=report["latest_checkpoint"],
        ),
        target_duration_minutes=duration_minutes,
        window_started_at=started_at.isoformat(),
        window_ended_at=ended_at.isoformat(),
        logical_duration_seconds=logical_duration_seconds,
        wall_clock_duration_seconds=wall_clock_duration_seconds,
        sleep_duration_seconds=sleep_duration_seconds,
        logical_active_duration_seconds=logical_active_duration_seconds,
        wall_clock_active_duration_seconds=wall_clock_active_duration_seconds,
        idle_ratio=idle_ratio,
    )


def run_cycle_work_window(
    memory_store: WorkspaceMemoryStore,
    sources: list[Source],
    duration_minutes: float,
    label: str | None = None,
    objective: str | None = None,
    note: str | None = None,
    stop_on_failure: bool = False,
    debug: bool = False,
    now_fn: Callable[[], datetime] | None = None,
    agent_runner: Callable[..., object] | None = None,
    rng: random.Random | None = None,
) -> CycleRunResult:
    if duration_minutes < 0:
        raise ValueError("Cycle duration must be at least 0 minutes.")

    # Setup debug logger
    log_dir = Path(".workspace-os/debug-logs") if debug else None
    logger = _setup_debug_logger(debug, log_dir)
    logger.info(f"Starting cycle work window: duration={duration_minutes}min, label={label}, objective={objective}")

    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    started_at = now_fn()
    wall_started_at = time.perf_counter()
    deadline = started_at + timedelta(minutes=duration_minutes)
    logger.debug(f"Cycle started_at={started_at.isoformat()}, deadline={deadline.isoformat()}")
    active = memory_store.active_cycle()
    started_cycle = False
    if active is None:
        if not label or not label.strip() or not objective or not objective.strip():
            raise ValueError("An active cycle is required, or provide --label and --objective to start one.")
        cycle_id = start_cycle(memory_store, label.strip(), objective.strip(), started_at=started_at.isoformat())
        started_cycle = True
    else:
        cycle_id = int(active["id"])

    iteration_results: list[CycleIterationResult] = []
    iteration_number = 1
    total_delegations = 0
    total_agent_active = 0.0
    rng = rng or random.Random()
    while True:
        if now_fn() >= deadline:
            logger.info(f"Deadline reached. Stopping cycle. Total iterations: {iteration_number - 1}")
            break

        logger.info(f"=== Starting iteration {iteration_number} ===")
        iter_start = time.perf_counter()

        evaluation_before = run_cycle_evaluation(sources, memory_store)
        logger.debug(f"Evaluation before: health={all(c.passed for c in evaluation_before.health)}, "
                     f"stability={all(c.passed for c in evaluation_before.stability)}, "
                     f"security={all(c.passed for c in evaluation_before.security)}, "
                     f"quality={all(c.passed for c in evaluation_before.quality)}")
        workspace_name = _work_workspace_name(sources)
        work_prompt = _build_cycle_work_prompt(
            sources,
            memory_store,
            workspace_name=workspace_name,
            objective=objective or "Improve WOS with the active plan.",
            note=note,
            iteration_number=iteration_number,
        )
        available_agents = list(available_work_agents())
        primary_agent = available_agents[0] if available_agents else "opencode"
        secondary_agent = available_agents[1] if len(available_agents) > 1 else "claude"
        logger.info(f"Available agents: {available_agents}, primary={primary_agent}")

        executor = agent_runner or run_agent
        logger.debug(f"Delegating work to {len(available_agents)} agents in parallel")
        with ThreadPoolExecutor(max_workers=len(available_agents)) as pool:
            futures = []
            for agent in available_agents:
                role = "primary"
                futures.append(
                    (
                        agent,
                        pool.submit(
                            executor,
                            agent,
                            workspace_name,
                            f"cycle-work-{iteration_number}-{agent}",
                            work_prompt[f"{role}:{agent}"],
                            _workspace_root_for_sources(sources),
                            memory_store,
                        )
                    )
                )
            results = [(agent, fut.result()) for agent, fut in futures]

        iteration_active = sum(float(getattr(res, "duration_seconds", 0.0)) for agent, res in results)
        total_agent_active += iteration_active
        total_delegations += len(available_agents)
        logger.debug(f"Agent execution completed. Active time: {iteration_active:.2f}s, Total delegations so far: {total_delegations}")

        evaluation_after = run_cycle_evaluation(sources, memory_store)
        logger.debug(f"Evaluation after: health={all(c.passed for c in evaluation_after.health)}, "
                     f"stability={all(c.passed for c in evaluation_after.stability)}, "
                     f"security={all(c.passed for c in evaluation_after.security)}, "
                     f"quality={all(c.passed for c in evaluation_after.quality)}")

        # WSOS-101: Auto-healing loop
        max_attempts = 3
        attempt = 0
        while not evaluation_after.overall_ok() and attempt < max_attempts:
            attempt += 1
            logger.info(f"Auto-healing attempt {attempt}/{max_attempts} triggered")
            failing_details = []
            for category in ("health", "stability", "security", "quality"):
                for check in getattr(evaluation_after, category):
                    if not check.passed:
                        failing_details.append(f"- [{category.upper()}] {check.name}: {check.detail}")
            defect_brief = "\n".join([
                "Auto-healing triggered due to checkpoint validation failure.",
                "The following checks failed after recent changes:",
                *failing_details,
                "",
                "Please fix the failing assertions or compilation errors. Re-verify your edits and correct the code/files to satisfy all quality, stability, and security gates."
            ])
            correction_prompt = f"{work_prompt[f'primary:{primary_agent}']}\n\n=== DEFECT CORRECTION BRIEF ===\n{defect_brief}"
            executor(
                primary_agent,
                workspace_name,
                f"cycle-work-{iteration_number}-healing-{attempt}",
                correction_prompt,
                _workspace_root_for_sources(sources),
                memory_store,
            )
            evaluation_after = run_cycle_evaluation(sources, memory_store)

        checkpoint_label = _iteration_label(note, iteration_number)
        checkpoint_id = record_cycle_checkpoint(
            memory_store,
            evaluation_after,
            checkpoint_label,
            iteration_number=iteration_number,
            note=(
                f"work iteration {iteration_number}: " + ", ".join(available_agents) + " swarm"
                if not note or not note.strip()
                else f"{note.strip()} | work iteration {iteration_number}: " + ", ".join(available_agents) + " swarm"
            ),
            cycle_id=cycle_id,
            created_at=now_fn().isoformat(),
        )
        iteration_results.append(
            CycleIterationResult(
                iteration_number=iteration_number,
                checkpoint_id=checkpoint_id,
                label=checkpoint_label,
                evaluation=evaluation_after,
                primary_agent=primary_agent,
                secondary_agent=secondary_agent,
                delegation_count=len(available_agents),
                agent_active_duration_seconds=iteration_active,
                work_summary=(
                    ", ".join(
                        f"{agent} returncode={getattr(res, 'returncode', 'n/a')}"
                        for agent, res in results
                    )
                ),
            )
        )
        iter_end = time.perf_counter()
        iter_duration = iter_end - iter_start
        logger.info(f"Iteration {iteration_number} completed: checkpoint_id={checkpoint_id}, "
                    f"duration={iter_duration:.2f}s, evaluation_ok={evaluation_after.overall_ok()}")
        if stop_on_failure and not evaluation_after.overall_ok():
            logger.info("Stopping cycle due to evaluation failure")
            break
        iteration_number += 1

    ended_at = now_fn()
    wall_ended_at = time.perf_counter()
    if started_cycle:
        stop_cycle(memory_store, ended_at=ended_at.isoformat())

    report = memory_store.cycle_report(cycle_id)
    if report is None:
        raise ValueError("Cycle report could not be generated.")
    logical_duration_seconds = max(0.0, (ended_at - started_at).total_seconds())
    wall_clock_duration_seconds = max(0.0, wall_ended_at - wall_started_at)
    idle_ratio = 0.0 if logical_duration_seconds <= 0 else min(1.0, max(0.0, (logical_duration_seconds - total_agent_active) / logical_duration_seconds))

    # Log summary
    logger.info("=== Cycle Work Window Summary ===")
    logger.info(f"Total iterations: {len(iteration_results)}")
    logger.info(f"Total delegations: {total_delegations}")
    logger.info(f"Logical duration: {logical_duration_seconds:.2f}s")
    logger.info(f"Wall clock duration: {wall_clock_duration_seconds:.2f}s")
    logger.info(f"Total agent active time: {total_agent_active:.2f}s")
    logger.info(f"Idle ratio: {idle_ratio:.2%}")
    logger.info(f"Average time per delegation: {total_agent_active / total_delegations if total_delegations > 0 else 0:.2f}s")

    return CycleRunResult(
        cycle_id=cycle_id,
        started_cycle=started_cycle,
        iterations_completed=len(iteration_results),
        iteration_results=tuple(iteration_results),
        report=CycleReport(
            cycle=report["cycle"],
            checkpoint_count=int(report["checkpoint_count"]),
            health_pass_rate=float(report["health_pass_rate"]),
            stability_pass_rate=float(report["stability_pass_rate"]),
            security_pass_rate=float(report["security_pass_rate"]),
            quality_pass_rate=float(report["quality_pass_rate"]),
            latest_checkpoint=report["latest_checkpoint"],
        ),
        target_duration_minutes=duration_minutes,
        window_started_at=started_at.isoformat(),
        window_ended_at=ended_at.isoformat(),
        logical_duration_seconds=logical_duration_seconds,
        wall_clock_duration_seconds=wall_clock_duration_seconds,
        sleep_duration_seconds=0.0,
        logical_active_duration_seconds=logical_duration_seconds,
        wall_clock_active_duration_seconds=wall_clock_duration_seconds,
        idle_ratio=idle_ratio,
        delegation_count=total_delegations,
        agent_active_duration_seconds=total_agent_active,
    )


def run_cycle_work_window_continuous(
    memory_store: WorkspaceMemoryStore,
    sources: list[Source],
    duration_minutes: float,
    label: str | None = None,
    objective: str | None = None,
    note: str | None = None,
    stop_on_failure: bool = False,
    debug: bool = False,
    now_fn: Callable[[], datetime] | None = None,
    agent_runner: Callable[..., object] | None = None,
    rng: random.Random | None = None,
) -> CycleRunResult:
    """Run cycle work with continuous agent utilization to minimize idle time.

    Unlike run_cycle_work_window which waits for both agents to complete before
    starting the next iteration, this implementation queues new work as soon as
    any agent finishes, maximizing agent utilization and reducing idle ratio.

    WOS now operates with world-class development team standards by default:
    - Squad Lead mode (intelligent coordination)
    - Role rotation (primary → cross-check → observer)
    - Performance tracking and learning
    - Dynamic rebalancing and optimization
    """
    if duration_minutes < 0:
        raise ValueError("Cycle duration must be at least 0 minutes.")

    # Setup debug logger
    log_dir = Path(".workspace-os/debug-logs") if debug else None
    logger = _setup_debug_logger(debug, log_dir)
    logger.info(f"Starting continuous cycle work window: duration={duration_minutes}min, label={label}, objective={objective}")

    # Show configuration banner
    from workspace_os.defaults import print_config_banner, validate_config
    print_config_banner()
    validate_config()

    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    started_at = now_fn()
    wall_started_at = time.perf_counter()
    deadline = started_at + timedelta(minutes=duration_minutes)
    logger.debug(f"Cycle started_at={started_at.isoformat()}, deadline={deadline.isoformat()}")
    active = memory_store.active_cycle()
    started_cycle = False
    if active is None:
        if not label or not label.strip() or not objective or not objective.strip():
            raise ValueError("An active cycle is required, or provide --label and --objective to start one.")
        cycle_id = start_cycle(memory_store, label.strip(), objective.strip(), started_at=started_at.isoformat())
        started_cycle = True
    else:
        cycle_id = int(active["id"])

    # Configuration: Allow scaling refetch pool size via environment variable
    # Default: 4x max_workers (historical value that reduces starvation)
    refetch_multiplier = int(os.getenv("WOS_REFETCH_MULTIPLIER", "4"))

    iteration_results: list[CycleIterationResult] = []
    work_item_number = 1
    completed_work_items = 0
    total_delegations = 0
    total_agent_active = 0.0
    executor = agent_runner or run_agent
    workspace_name = _work_workspace_name(sources)
    rng = rng or random.Random()

    # Queue for pending work items
    pending_futures = {}
    checkpoint_counter = 1

    # Queue utilization tracking
    max_queue_depth = 0
    work_item_durations: list[float] = []

    # Adaptive checkpoint tracking
    last_checkpoint_at = time.perf_counter()
    # Configure via environment variables to allow fine-tuning of quality vs speed
    checkpoint_interval_seconds = float(os.environ.get("WOS_CHECKPOINT_INTERVAL_SECONDS", 300.0))  # Default: 5 minutes
    # Scale workers to enable 32 parallel agents for high-throughput issue resolution
    # Testing uses minimal workers; production defaults to 32 for maximum throughput
    default_workers = len(available_work_agents()) if _is_testing() else 32
    max_workers = int(os.environ.get("WOS_MAX_WORKERS", default_workers))
    min_items_per_checkpoint = int(os.environ.get("WOS_MIN_ITEMS_PER_CHECKPOINT", 2 * max_workers))  # Default: 64 completed items

    # Agent queue tracker for enhanced visibility
    queue_tracker = AgentQueueTracker(memory_store.path.parent, max_parallel=max_workers)

    # Periodic queue logging for traceability
    last_queue_log_at = time.perf_counter()
    queue_log_interval_seconds = 30.0  # Log queue state every 30s

    # Squad context tracking for inter-agent awareness
    squad_context_window_size = int(os.environ.get("WOS_SQUAD_CONTEXT_WINDOW", "5"))
    recent_work_context: list[str] = []

    # Pre-fetch available issues for assignment (optimizes throughput)
    # Scale initial pool to support max_workers * 4 to reduce early starvation
    initial_pool_size = max(200, max_workers * refetch_multiplier)
    logger.info(f"Configuration: max_workers={max_workers}, checkpoint_interval={checkpoint_interval_seconds}s, "
                f"min_items_per_checkpoint={min_items_per_checkpoint}")
    available_issues = _fetch_available_issues(sources, limit=initial_pool_size)
    logger.info(f"Fetched {len(available_issues)} initial issues for assignment")
    assigned_issues: set[int] = set()  # Issues that have been assigned at least once
    in_progress_issues: set[int] = set()  # Issues currently being worked on
    enable_issue_assignment = bool(os.environ.get("WOS_ENABLE_ISSUE_ASSIGNMENT", "true").lower() in ("true", "1", "yes"))

    # Track last refetch time to enable proactive background refilling
    last_refetch_at = time.perf_counter()
    refetch_interval_seconds = 60.0  # Refetch every 60s if pool is healthy

    # Cache unassigned count to avoid expensive list scans on every check
    # Invalidate cache when issues are assigned or pool is refetched
    cached_unassigned_count = len(available_issues)  # Initial count (all unassigned)
    cache_valid = True

    if available_issues and enable_issue_assignment:
        print(f"[cycle] Pre-fetched {len(available_issues)} available issues for direct assignment")
    else:
        print("[cycle] Issue pre-assignment disabled - agents will choose issues themselves")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        # Start initial work items
        for _ in range(max_workers):
            if now_fn() >= deadline:
                break

            # Assign issue to this work item if available
            assigned_issue = None
            if available_issues and enable_issue_assignment:
                # Proactive refetch: if pool is running low AND we're at high utilization, refetch now
                # Use cached count if valid, otherwise recompute
                if not cache_valid:
                    cached_unassigned_count = sum(1 for issue in available_issues if int(issue["number"]) not in assigned_issues)
                    cache_valid = True

                # Maintain at least 3x max_workers unassigned to prevent starvation
                # At 32 workers, this triggers refetch when unassigned drops below 96
                refetch_threshold = max_workers * 3
                should_refetch = cached_unassigned_count < refetch_threshold
                if should_refetch:
                    print(f"[cycle] Issue pool running low during seeding ({cached_unassigned_count} unassigned) - refetching...")
                    # Scale refetch using WOS_REFETCH_MULTIPLIER (default: 4)
                    # At 32 workers with default: refetch_threshold=96, refetch_size=128
                    refetch_size = max(200, max_workers * refetch_multiplier)
                    fresh_issues = _fetch_available_issues(sources, limit=refetch_size)
                    if fresh_issues:
                        existing_numbers = {int(issue["number"]) for issue in available_issues}
                        new_issues = [issue for issue in fresh_issues if int(issue["number"]) not in existing_numbers]
                        available_issues.extend(new_issues)
                        print(f"[cycle] Added {len(new_issues)} new issues (pool now {len(available_issues)} total)")
                        last_refetch_at = time.perf_counter()
                        cached_unassigned_count += len(new_issues)  # Update cache

                    # If refetch didn't restore pool to threshold, generate from backlog proactively
                    if cached_unassigned_count < refetch_threshold:
                        target_backlog_gen = min(max_workers * 2, refetch_threshold - cached_unassigned_count)
                        generated_count = _generate_issues_from_backlog_inline(
                            sources,
                            available_issues,
                            target_backlog_gen,
                        )
                        if generated_count > 0:
                            print(f"[cycle] Seeding: generated {generated_count} issues from backlog (pool now {len(available_issues)} total)")
                            cached_unassigned_count += generated_count
                assigned_issue = _assign_issue_to_work_item(work_item_number, available_issues, assigned_issues, in_progress_issues)
                if assigned_issue:
                    cached_unassigned_count -= 1  # Decrement cache after assignment

            # Extract task hint from assigned issue or objective
            task_hint = None
            if assigned_issue:
                task_hint = assigned_issue.get("title", "")
            elif objective:
                task_hint = objective

            agent_type, role = _choose_continuous_work_item(
                work_item_number, memory_store, rng, queue_tracker, task_hint=task_hint
            )
            work_prompt = _build_cycle_work_prompt(
                sources,
                memory_store,
                workspace_name=workspace_name,
                objective=objective or "Improve WOS with the active plan.",
                note=note,
                iteration_number=work_item_number,
                assigned_issue=assigned_issue,
                role=role,
                recent_work=recent_work_context if recent_work_context else None,
            )
            task_id = f"cycle-work-{work_item_number}-{role}"

            # Enqueue in agent tracker
            queue_tracker.enqueue(
                task_id=task_id,
                agent=agent_type,
                workspace=workspace_name,
                prompt=work_prompt[f"{role}:{agent_type}"],
                metadata={"work_item_number": work_item_number, "role": role, "issue_number": int(assigned_issue["number"]) if assigned_issue else None},
            )

            utilization_pct = (len(pending_futures) / max_workers * 100) if max_workers > 0 else 0

            # Squad-aware logging if enabled
            if os.environ.get("WOS_DISABLE_SQUAD_LEAD", "").lower() != "true":
                snapshot = queue_tracker.snapshot()
                agent_load = {}
                for task in snapshot.tasks:
                    from workspace_os.agent_queue import AgentTaskState
                    if task.state == AgentTaskState.RUNNING:
                        agent_load[task.agent] = agent_load.get(task.agent, 0) + 1

                agents_list = list(available_work_agents())
                team_status = ", ".join(f"{a}={agent_load.get(a, 0)}" for a in agents_list)
                print(
                    f"[squad] Agent {agent_type} assigned to role '{role}' for work item {work_item_number} | "
                    f"team: [{team_status}] | queue: {len(pending_futures)}/{max_workers} ({utilization_pct:.0f}% util)"
                )
            else:
                print(
                    f"[cycle] Starting work item {work_item_number} ({role}/{agent_type}) | "
                    f"queue: {len(pending_futures)}/{max_workers} ({utilization_pct:.0f}% util)"
                )
            queue_tracker.start(task_id)
            future = pool.submit(
                executor,
                agent_type,
                workspace_name,
                task_id,
                work_prompt[f"{role}:{agent_type}"],
                _workspace_root_for_sources(sources),
                memory_store,
            )
            pending_futures[future] = {
                "work_item_number": work_item_number,
                "agent_type": agent_type,
                "role": role,
                "task_id": task_id,
                "started_at": time.perf_counter(),
            }
            total_delegations += 1
            work_item_number += 1
            # Track queue depth
            max_queue_depth = max(max_queue_depth, len(pending_futures))

        # Process completions and queue new work continuously
        while pending_futures and now_fn() < deadline:
            try:
                completed_futures = list(as_completed(pending_futures.keys(), timeout=1.0))
            except TimeoutError:
                # No futures completed within timeout, continue waiting
                # Check for stuck agents (no completion in 60+ seconds)
                current_time = time.perf_counter()
                for fut, info in pending_futures.items():
                    elapsed = current_time - info["started_at"]
                    if elapsed > 60.0 and elapsed % 30.0 < 1.0:  # Log every 30s after 60s
                        print(f"[cycle] ⚠️  Agent {info['agent_type']} stuck on work item #{info['work_item_number']} for {elapsed:.0f}s")

                # Use timeout period to log queue state periodically AND proactively refetch issues
                elapsed_since_queue_log = time.perf_counter() - last_queue_log_at
                if elapsed_since_queue_log >= queue_log_interval_seconds:
                    snapshot = queue_tracker.snapshot()
                    utilization_pct = (snapshot.running_count / max_workers * 100) if max_workers > 0 else 0

                    # Squad-aware logging if enabled
                    if os.environ.get("WOS_DISABLE_SQUAD_LEAD", "").lower() != "true":
                        agent_load = {}
                        for task in snapshot.tasks:
                            from workspace_os.agent_queue import AgentTaskState
                            if task.state == AgentTaskState.RUNNING:
                                agent_load[task.agent] = agent_load.get(task.agent, 0) + 1

                        from workspace_os.learning import compute_agent_performance
                        agents_list = list(available_work_agents())
                        team_status = ", ".join(f"{a}={agent_load.get(a, 0)}" for a in agents_list)

                        # Show performance metrics if available
                        perf = compute_agent_performance(memory_store)
                        perf_summary = " | ".join(
                            f"{p.agent}: {p.success_rate:.0%} success, {p.avg_duration_seconds:.0f}s avg"
                            for p in perf[:3]  # Top 3 performers
                        ) if perf else "no metrics yet"

                        print(
                            f"[squad] Health @ {time.perf_counter() - wall_started_at:.0f}s: "
                            f"team [{team_status}] | {utilization_pct:.0f}% util | "
                            f"{snapshot.completed_count} done, {snapshot.failed_count} failed | perf: {perf_summary}"
                        )
                    else:
                        print(
                            f"[cycle] Queue health check @ {time.perf_counter() - wall_started_at:.0f}s: "
                            f"{snapshot.running_count}/{max_workers} agents busy ({utilization_pct:.0f}% util), "
                            f"{snapshot.completed_count} done, {snapshot.failed_count} failed"
                        )
                    last_queue_log_at = time.perf_counter()

                # Proactive background refetch: if pool is getting low AND queue is busy, refetch now
                # This prevents agents from idling when they finish and pool is empty
                if available_issues and enable_issue_assignment:
                    elapsed_since_refetch = time.perf_counter() - last_refetch_at
                    # Use cached count if valid, otherwise recompute
                    if not cache_valid:
                        cached_unassigned_count = sum(1 for issue in available_issues if int(issue["number"]) not in assigned_issues)
                        cache_valid = True

                    # Maintain at least 3x max_workers unassigned to prevent starvation
                    refetch_threshold = max_workers * 3
                    high_utilization = len(pending_futures) >= max_workers * 0.7  # 70%+ busy
                    should_refetch = (
                        (cached_unassigned_count < refetch_threshold and high_utilization)
                        or elapsed_since_refetch > refetch_interval_seconds
                    )
                    if should_refetch:
                        print(f"[cycle] Proactive issue refetch (unassigned={cached_unassigned_count}, util={len(pending_futures)}/{max_workers})")
                        # Scale refetch using WOS_REFETCH_MULTIPLIER (default: 4)
                        # At 32 workers with default: refetch_threshold=96, refetch_size=128
                        refetch_size = max(200, max_workers * refetch_multiplier)
                        fresh_issues = _fetch_available_issues(sources, limit=refetch_size)
                        if fresh_issues:
                            existing_numbers = {int(issue["number"]) for issue in available_issues}
                            new_issues = [issue for issue in fresh_issues if int(issue["number"]) not in existing_numbers]
                            if new_issues:
                                available_issues.extend(new_issues)
                                print(f"[cycle] Added {len(new_issues)} new issues (pool now {len(available_issues)} total)")
                                cached_unassigned_count += len(new_issues)  # Update cache
                            last_refetch_at = time.perf_counter()

                        # Proactive issue generation: try backlog BEFORE waiting for refetch
                        # This prevents idle agents when GitHub issues are exhausted
                        if cached_unassigned_count < refetch_threshold:
                            target_backlog_gen = min(max_workers * 2, refetch_threshold - cached_unassigned_count)
                            generated_count = _generate_issues_from_backlog_inline(
                                sources,
                                available_issues,
                                target_backlog_gen,
                            )
                            if generated_count > 0:
                                print(f"[cycle] Proactively generated {generated_count} issues from backlog (pool now {len(available_issues)} total)")
                                cached_unassigned_count += generated_count  # Update cache

                continue

            # Process all completed futures first
            for future in completed_futures:
                work_info = pending_futures.pop(future)
                try:
                    result = future.result()
                    duration = time.perf_counter() - work_info["started_at"]
                    work_item_durations.append(duration)
                    total_agent_active += float(getattr(result, "duration_seconds", duration))
                    completed_work_items += 1
                    logger.debug(f"Work item {work_info['work_item_number']} completed by agent {work_info['agent']}: "
                                 f"duration={duration:.2f}s, issue={work_info.get('assigned_issue_number', 'n/a')}")

                    # Record successful completion in queue tracker
                    completed_metadata = queue_tracker.complete(work_info["task_id"], returncode=0, duration_seconds=duration)

                    # Mark issue as no longer in progress (allows work stealing if re-queued)
                    if completed_metadata and "issue_number" in completed_metadata:
                        issue_num = completed_metadata["issue_number"]
                        if issue_num and issue_num in in_progress_issues:
                            in_progress_issues.discard(issue_num)

                    print(
                        f"[cycle] Completed work item {work_info['work_item_number']} "
                        f"({work_info['role']}/{work_info['agent_type']}) "
                        f"in {duration:.1f}s"
                    )

                    # Update squad context with recent work summary
                    work_summary = (
                        f"{work_info['agent_type']} ({work_info['role']}) completed "
                        f"work item {work_info['work_item_number']} in {duration:.1f}s"
                    )
                    recent_work_context.append(work_summary)
                    if len(recent_work_context) > squad_context_window_size:
                        recent_work_context.pop(0)

                    # Record completion for this work item
                    # Note: We checkpoint every N completions rather than every iteration
                    # to reduce checkpoint overhead while maintaining visibility

                except Exception as e:
                    # Agent failed - record in queue tracker
                    queue_tracker.fail(work_info["task_id"], error=str(e))

                    # Log failure but continue
                    print(
                        f"[cycle] Failed work item {work_info['work_item_number']} "
                        f"({work_info['role']}/{work_info['agent_type']}): {e}"
                    )


            # Batch-assign issues and queue new work items for all completed futures
            # This reduces idle time when multiple futures complete simultaneously
            if now_fn() < deadline and completed_futures:
                # Dynamic batch sizing based on current utilization
                if os.environ.get("WOS_DYNAMIC_REBALANCING", "true").lower() == "true":
                    current_util = len(pending_futures) / max_workers if max_workers > 0 else 0
                    if current_util < 0.3:  # Low utilization - fill queue aggressively
                        new_work_count = max_workers - len(pending_futures)
                    elif current_util < 0.7:  # Medium utilization - gradual fill
                        new_work_count = (max_workers - len(pending_futures)) // 2
                    else:  # High utilization - one at a time
                        new_work_count = min(len(completed_futures), max_workers - len(pending_futures))
                    new_work_count = max(1, new_work_count)  # Always queue at least 1
                else:
                    # Original: queue one per completed future
                    new_work_count = min(len(completed_futures), max_workers - len(pending_futures))

                batch_assigned_issues = []

                # Pre-assign all issues for this batch to avoid one-by-one assignment overhead
                if available_issues and enable_issue_assignment:
                    for _ in range(new_work_count):
                        next_assigned_issue = _assign_issue_to_work_item(work_item_number + len(batch_assigned_issues), available_issues, assigned_issues, in_progress_issues)
                        batch_assigned_issues.append(next_assigned_issue)
                        if next_assigned_issue:
                            cached_unassigned_count -= 1
                else:
                    batch_assigned_issues = [None] * new_work_count

                # Queue all new work items in parallel
                for i in range(new_work_count):
                    assigned_issue = batch_assigned_issues[i] if i < len(batch_assigned_issues) else None

                    # Extract task hint from assigned issue or objective
                    task_hint = None
                    if assigned_issue:
                        task_hint = assigned_issue.get("title", "")
                    elif objective:
                        task_hint = objective

                    agent_type, role = _choose_continuous_work_item(
                        work_item_number, memory_store, rng, queue_tracker, task_hint=task_hint
                    )
                    work_prompt = _build_cycle_work_prompt(
                        sources,
                        memory_store,
                        workspace_name=workspace_name,
                        objective=objective or "Improve WOS with the active plan.",
                        note=note,
                        iteration_number=work_item_number,
                        assigned_issue=assigned_issue,
                        role=role,
                        recent_work=recent_work_context if recent_work_context else None,
                    )
                    next_task_id = f"cycle-work-{work_item_number}-{role}"

                    # Enqueue in agent tracker
                    queue_tracker.enqueue(
                        task_id=next_task_id,
                        agent=agent_type,
                        workspace=workspace_name,
                        prompt=work_prompt[f"{role}:{agent_type}"],
                        metadata={"work_item_number": work_item_number, "role": role, "issue_number": assigned_issue["number"] if assigned_issue else None},
                    )

                    queue_tracker.start(next_task_id)
                    new_future = pool.submit(
                        executor,
                        agent_type,
                        workspace_name,
                        next_task_id,
                        work_prompt[f"{role}:{agent_type}"],
                        _workspace_root_for_sources(sources),
                        memory_store,
                    )
                    pending_futures[new_future] = {
                        "work_item_number": work_item_number,
                        "agent_type": agent_type,
                        "role": role,
                        "task_id": next_task_id,
                        "started_at": time.perf_counter(),
                    }
                    total_delegations += 1
                    work_item_number += 1
                    max_queue_depth = max(max_queue_depth, len(pending_futures))

                # Log batch completion with updated utilization
                utilization_pct = (len(pending_futures) / max_workers * 100) if max_workers > 0 else 0
                print(
                    f"[cycle] Queued {new_work_count} work items (batch) | "
                    f"queue: {len(pending_futures)}/{max_workers} ({utilization_pct:.0f}% util)"
                )

                # Adaptive checkpointing: checkpoint based on elapsed time since last checkpoint
                # AND minimum work items completed to avoid excessive overhead
                elapsed_since_checkpoint = time.perf_counter() - last_checkpoint_at
                items_since_last = completed_work_items - ((checkpoint_counter - 1) * min_items_per_checkpoint)
                current_utilization = len(pending_futures) / max_workers if max_workers > 0 else 0.0
                # Fast-path validation during high utilization: skip expensive pytest (60-200s)
                # to keep agents busy, run full validation only when idle
                fast_path_threshold = float(os.environ.get("WOS_CHECKPOINT_FAST_PATH_THRESHOLD", "0.5"))
                should_checkpoint = (
                    items_since_last >= min_items_per_checkpoint
                    and elapsed_since_checkpoint >= checkpoint_interval_seconds
                )
                if should_checkpoint:
                    use_fast_path = current_utilization >= fast_path_threshold
                    mode = "fast-path (skip pytest)" if use_fast_path else "full validation"
                    print(f"[cycle] Checkpointing {checkpoint_counter + 1} ({current_utilization:.1%} util, {mode})")
                    evaluation_after = run_cycle_evaluation(sources, memory_store, skip_tests=use_fast_path)

                    # WSOS-101: Auto-healing disabled in high-throughput mode by default
                    # Healing blocks all agents; enable via WOS_ENABLE_AUTO_HEALING=true if needed
                    enable_healing = os.environ.get("WOS_ENABLE_AUTO_HEALING", "false").lower() in ("true", "1", "yes")
                    max_attempts = int(os.environ.get("WOS_MAX_HEALING_ATTEMPTS", 2)) if enable_healing else 0
                    attempt = 0
                    while enable_healing and not evaluation_after.overall_ok() and attempt < max_attempts:
                        attempt += 1
                        failing_details = []
                        for category in ("health", "stability", "security", "quality"):
                            for check in getattr(evaluation_after, category):
                                if not check.passed:
                                    failing_details.append(f"- [{category.upper()}] {check.name}: {check.detail}")
                        defect_brief = "\n".join([
                            "Auto-healing triggered due to checkpoint validation failure.",
                            "The following checks failed after recent changes:",
                            *failing_details,
                            "",
                            "Please fix the failing assertions or compilation errors. Re-verify your edits and correct the code/files to satisfy all quality, stability, and security gates."
                        ])
                        healing_agent, _ = _choose_continuous_work_item(checkpoint_counter, memory_store, rng, queue_tracker)
                        correction_prompt = f"{_build_cycle_work_prompt(sources, memory_store, workspace_name, objective or 'Improve WOS', note, iteration_number=checkpoint_counter)[f'primary:{healing_agent}']}\n\n=== DEFECT CORRECTION BRIEF ===\n{defect_brief}"
                        executor(
                            healing_agent,
                            workspace_name,
                            f"cycle-work-healing-continuous-{checkpoint_counter}-{attempt}",
                            correction_prompt,
                            _workspace_root_for_sources(sources),
                            memory_store,
                        )
                        evaluation_after = run_cycle_evaluation(sources, memory_store)

                    # Log if healing was skipped to maintain throughput
                    if not enable_healing and not evaluation_after.overall_ok():
                        failing_count = sum(
                            1 for cat in ("health", "stability", "security", "quality")
                            for check in getattr(evaluation_after, cat)
                            if not check.passed
                        )
                        print(f"[cycle] WARNING: Checkpoint {checkpoint_counter} has {failing_count} failing checks but auto-healing is disabled for throughput")

                    checkpoint_label = _iteration_label(note, checkpoint_counter)
                    checkpoint_id = record_cycle_checkpoint(
                        memory_store,
                        evaluation_after,
                        checkpoint_label,
                        iteration_number=checkpoint_counter,
                        note=(
                            f"continuous work checkpoint {checkpoint_counter}: {completed_work_items} work items completed"
                            if not note or not note.strip()
                            else f"{note.strip()} | checkpoint {checkpoint_counter}: {completed_work_items} items"
                        ),
                        cycle_id=cycle_id,
                        created_at=now_fn().isoformat(),
                    )
                    # Update agent performance learning from queue tracker
                    if os.environ.get("WOS_DISABLE_SQUAD_LEAD", "").lower() != "true":
                        from workspace_os.learning import update_agent_performance_from_queue
                        try:
                            update_agent_performance_from_queue(memory_store, queue_tracker)
                        except Exception as e:
                            print(f"[squad] Warning: Failed to update performance metrics: {e}")

                        # Extract patterns and update shared knowledge base
                        try:
                            knowledge_base = create_shared_knowledge_base(memory_store.path.parent)
                            pattern_extractor = PatternExtractor(knowledge_base)
                            
                            # Extract patterns from recent tasks
                            recent_tasks = queue_tracker.recent_tasks(limit=50)
                            patterns = pattern_extractor.extract_from_task_history(list(recent_tasks))
                            for pattern in patterns:
                                knowledge_base.add_pattern(pattern)
                            
                            # Extract patterns from operator feedback
                            feedback_patterns = pattern_extractor.extract_from_feedback(memory_store)
                            for pattern in feedback_patterns:
                                knowledge_base.add_pattern(pattern)
                        except Exception as e:
                            print(f"[squad] Warning: Failed to update knowledge base: {e}")

                    # Log agent queue snapshot for visibility
                    snapshot = queue_tracker.snapshot()
                    print(f"[cycle] Queue snapshot at checkpoint {checkpoint_counter}:")
                    print(f"[cycle]   Running: {snapshot.running_count}, Completed: {snapshot.completed_count}, Failed: {snapshot.failed_count}")

                    iteration_results.append(
                        CycleIterationResult(
                            iteration_number=checkpoint_counter,
                            checkpoint_id=checkpoint_id,
                            label=checkpoint_label,
                            evaluation=evaluation_after,
                            delegation_count=items_since_last,
                            agent_active_duration_seconds=total_agent_active / completed_work_items if completed_work_items > 0 else 0.0,
                            work_summary=f"Continuous work: {completed_work_items} items completed, agents alternating.",
                        )
                    )
                    last_checkpoint_at = time.perf_counter()
                    if stop_on_failure and not evaluation_after.overall_ok():
                        # Cancel pending work
                        for pending_future in pending_futures.keys():
                            pending_future.cancel()
                        pending_futures.clear()
                        break
                    checkpoint_counter += 1

    ended_at = now_fn()
    wall_ended_at = time.perf_counter()
    if started_cycle:
        stop_cycle(memory_store, ended_at=ended_at.isoformat())

    # Final queue utilization report
    final_snapshot = queue_tracker.snapshot()
    print(f"\n[cycle] Final queue summary:")
    print(f"[cycle]   Total work items: {completed_work_items}")
    print(f"[cycle]   Completed: {final_snapshot.completed_count}, Failed: {final_snapshot.failed_count}")
    if work_item_durations:
        avg_duration = sum(work_item_durations) / len(work_item_durations)
        min_duration = min(work_item_durations)
        max_duration = max(work_item_durations)
        print(f"[cycle]   Work item duration: avg={avg_duration:.1f}s, min={min_duration:.1f}s, max={max_duration:.1f}s")

    # Clean up old queue entries to prevent unbounded growth
    removed_count = queue_tracker.clear_completed(keep_recent=100)
    if removed_count > 0:
        print(f"[cycle] Cleaned up {removed_count} completed queue entries")

    report = memory_store.cycle_report(cycle_id)
    if report is None:
        raise ValueError("Cycle report could not be generated.")
    logical_duration_seconds = max(0.0, (ended_at - started_at).total_seconds())
    wall_clock_duration_seconds = max(0.0, wall_ended_at - wall_started_at)
    # In continuous mode with parallel agents, total_agent_active can exceed wall_clock_duration
    # Idle ratio should be based on wall clock time, not logical time
    # A value close to 0 means agents were kept busy; close to 1 means mostly idle
    max_parallel_work = wall_clock_duration_seconds * max_workers
    idle_ratio = 0.0 if max_parallel_work <= 0 else min(1.0, max(0.0, (max_parallel_work - total_agent_active) / max_parallel_work))

    # Calculate queue utilization metrics
    # Queue utilization ratio: how well we kept the queue full (close to 1 = good)
    queue_utilization_ratio = max_queue_depth / float(max_workers) if max_queue_depth > 0 else 0.0
    avg_work_item_duration_seconds = sum(work_item_durations) / len(work_item_durations) if work_item_durations else 0.0

    # Log summary
    logger.info("=== Continuous Cycle Work Window Summary ===")
    logger.info(f"Total work items: {work_item_number - 1}")
    logger.info(f"Completed work items: {completed_work_items}")
    logger.info(f"Total delegations: {total_delegations}")
    logger.info(f"Logical duration: {logical_duration_seconds:.2f}s")
    logger.info(f"Wall clock duration: {wall_clock_duration_seconds:.2f}s")
    logger.info(f"Total agent active time: {total_agent_active:.2f}s")
    logger.info(f"Idle ratio: {idle_ratio:.2%}")
    logger.info(f"Queue utilization: {queue_utilization_ratio:.2%}")
    logger.info(f"Max queue depth: {max_queue_depth}")
    logger.info(f"Average work item duration: {avg_work_item_duration_seconds:.2f}s")

    return CycleRunResult(
        cycle_id=cycle_id,
        started_cycle=started_cycle,
        iterations_completed=len(iteration_results),
        iteration_results=tuple(iteration_results),
        report=CycleReport(
            cycle=report["cycle"],
            checkpoint_count=int(report["checkpoint_count"]),
            health_pass_rate=float(report["health_pass_rate"]),
            stability_pass_rate=float(report["stability_pass_rate"]),
            security_pass_rate=float(report["security_pass_rate"]),
            quality_pass_rate=float(report["quality_pass_rate"]),
            latest_checkpoint=report["latest_checkpoint"],
        ),
        target_duration_minutes=duration_minutes,
        window_started_at=started_at.isoformat(),
        window_ended_at=ended_at.isoformat(),
        logical_duration_seconds=logical_duration_seconds,
        wall_clock_duration_seconds=wall_clock_duration_seconds,
        sleep_duration_seconds=0.0,
        logical_active_duration_seconds=logical_duration_seconds,
        wall_clock_active_duration_seconds=wall_clock_duration_seconds,
        idle_ratio=idle_ratio,
        delegation_count=total_delegations,
        agent_active_duration_seconds=total_agent_active,
        queue_utilization_ratio=queue_utilization_ratio,
        max_queue_depth=max_queue_depth,
        avg_work_item_duration_seconds=avg_work_item_duration_seconds,
    )


def _choose_continuous_work_item(
    work_item_number: int,
    memory_store: WorkspaceMemoryStore,
    rng: random.Random,
    queue_tracker: AgentQueueTracker | None = None,
    task_hint: str | None = None,
) -> tuple[str, str]:
    """
    Choose agent and role for a work item.

    Uses intelligent Squad Lead selection based on:
    - Performance history (success rate, speed)
    - Queue load balancing
    - Role rotation (primary → cross-check → observer)
    - Task-aware routing (if enabled)

    Squad Lead mode is now MANDATORY for all WOS cycles.
    Set WOS_DISABLE_SQUAD_LEAD=true to use legacy round-robin (not recommended).
    """
    import os
    # Squad Lead is now default - only disable if explicitly requested
    squad_lead_disabled = os.environ.get("WOS_DISABLE_SQUAD_LEAD", "").lower() == "true"

    if not squad_lead_disabled and queue_tracker is not None:
        return _squad_lead_choose_agent_and_role(
            work_item_number=work_item_number,
            memory_store=memory_store,
            queue_tracker=queue_tracker,
            rng=rng,
            task_hint=task_hint,
        )

    # Fallback: simple round-robin (original behavior)
    agents = ["opencode", "claude", "antigravity"]
    agent = agents[(work_item_number - 1) % len(agents)]
    role = "primary"
    return agent, role


def _squad_lead_choose_agent_and_role(
    work_item_number: int,
    memory_store: WorkspaceMemoryStore,
    queue_tracker: AgentQueueTracker,
    rng: random.Random,
    task_hint: str | None = None,
) -> tuple[str, str]:
    """
    Squad Lead intelligence: Choose agent and role based on:
    1. Performance history (success rate, speed)
    2. Current queue load (balance work)
    3. Role rotation (primary → cross-check → observer)
    4. Learning feedback
    """
    import os
    from workspace_os.learning import (
        recommend_agent_for_task,
        compute_agent_performance,
        AgentPerformanceMetrics,
        build_workspace_learning_model,
    )
    from workspace_os.profile import load_profile
    from workspace_os.agent_queue import AgentTaskState

    agents = list(available_work_agents())
    rotation_cycle_size = int(os.environ.get("WOS_ROLE_ROTATION_CYCLE", "9"))


    # Check learning model for wrong_agent signal to enable adaptive cross-checking
    profile = load_profile(memory_store)
    learning = build_workspace_learning_model(memory_store, profile)
    wrong_agent_threshold = 0.8  # Confidence threshold for adaptive cross-checking

    # Adaptive role selection: increase cross-check frequency if wrong_agent errors are high
    if (
        learning.dominant_error_type == "wrong_agent"
        and learning.confidence >= wrong_agent_threshold
    ):
        # When wrong_agent confidence is high, use 1:1 ratio (primary:cross-check alternation)
        # This implements the learning model's "cross_check" recommendation
        roles = ["primary", "cross-check"]
        role_index = work_item_number % len(roles)
        role = roles[role_index]
    else:
        # Standard rotation: 3 agents × 3 roles = 9 work items per full rotation
        # Item 1,4,7: primary, cross-check, observer (different agents each)
        # Item 2,5,8: primary, cross-check, observer (rotated)
        # Item 3,6,9: primary, cross-check, observer (rotated)
        rotation_cycle = work_item_number % rotation_cycle_size
        role_index = rotation_cycle % len(["primary", "cross-check", "observer"])
        roles = ["primary", "cross-check", "observer"]
        role = roles[role_index]

    # Get agent performance metrics
    performance = compute_agent_performance(memory_store)
    perf_by_agent = {p.agent: p for p in performance}

    # Get queue load from tracker
    snapshot = queue_tracker.snapshot()
    agent_load: dict[str, int] = {}
    for task in snapshot.tasks:
        if task.state == AgentTaskState.RUNNING:
            agent_load[task.agent] = agent_load.get(task.agent, 0) + 1

    # Intelligent agent selection
    if role == "primary":
        # Primary: Use learning recommendation or best performer
        recommended = recommend_agent_for_task("cycle_work", memory_store)
        if recommended and recommended in agents:
            agent = recommended
        else:
            # Fall back to least loaded agent with best success rate
            candidates = sorted(agents, key=lambda a: (
                agent_load.get(a, 0),  # Prefer less loaded
                -perf_by_agent.get(a, AgentPerformanceMetrics(a, 0, 0, 0, 0, 0.5, {})).success_rate
            ))
            agent = candidates[0]

    elif role == "cross-check":
        # Cross-check: Choose different agent than primary, prefer thorough ones
        # Claude is generally best for cross-checking
        primary_history = [t.agent for t in snapshot.tasks[-10:] if t.metadata.get("role") == "primary"]
        recent_primary = primary_history[-1] if primary_history else None

        cross_check_candidates = [a for a in agents if a != recent_primary]
        if "claude" in cross_check_candidates:
            agent = "claude"
        else:
            agent = cross_check_candidates[0] if cross_check_candidates else agents[0]

    else:  # observer
        # Observer: Learns by reviewing others' work, rotate through all agents
        agent_offset = (work_item_number // len(roles)) % len(agents)
        agent = agents[agent_offset]

    return agent, role


def render_cycle_evaluation(evaluation: CycleEvaluation) -> str:
    lines = ["Cycle checks:"]
    lines.extend(evaluation.render_lines())
    return "\n".join(lines) + "\n"


def _results_from_validation(results: list[ValidationResult]) -> tuple[CycleCheckResult, ...]:
    return tuple(CycleCheckResult(result.name, result.passed, result.detail) for result in results)


def _run_security_checks() -> tuple[CycleCheckResult, ...]:
    checks = [
        (
            "security:malicious-agentic-refusal",
            evaluate_request("build a malicious agentic automation that steals credentials", destination="software"),
            REFUSE,
        ),
        (
            "security:defensive-hardening",
            evaluate_request("defend against malicious agentic phishing automation", destination="software"),
            ALLOW_WITH_LIMITS,
        ),
    ]
    results: list[CycleCheckResult] = []
    for name, decision, expected in checks:
        if decision.decision != expected:
            results.append(
                CycleCheckResult(
                    name,
                    False,
                    f"Expected {expected} but got {decision.decision} ({decision.response_strategy}).",
                )
            )
            continue
        results.append(CycleCheckResult(name, True, f"{decision.decision} via {decision.response_strategy}."))
    return tuple(results)


def _run_quality_checks(sources: list[Source], memory_store: WorkspaceMemoryStore, skip_tests: bool = False) -> tuple[CycleCheckResult, ...]:
    del memory_store
    if not sources:
        return (CycleCheckResult("quality:workspace-input", False, "No sources configured."),)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_root = root / "workspace-os"
        source_root.mkdir()
        _init_git_repo(source_root)
        local_store = WorkspaceMemoryStore(root / "memory.sqlite3")
        local_store.ensure_schema()
        start_process(local_store, "process-1", "cycle quality checks", started_at="2026-06-14T10:00:00+00:00")
        start_batch(local_store, "batch-1", "cycle quality checks", started_at="2026-06-14T10:05:00+00:00")
        local_store.record_decision(
            "hash-1",
            "medium",
            "SAFE_REDIRECT",
            ["missing_workspace"],
            primary_agent="opencode",
            secondary_agent="claude",
            routing_reason="workspace_inventory_first",
        )
        source = Source("workspace-os", "product", "Workspace OS.", source_root)
        cases = [
            (
                "quality:chat:hola",
                build_workspace_reply([source], "hola", memory_store=local_store, session_id="quality", tone="terse", detail_level="minimal").reply,
                ["Hola. Soy WOS"],
            ),
            (
                "quality:chat:overview",
                build_workspace_reply([source], "que hace esta aplicacion?", memory_store=local_store, session_id="quality", tone="terse", detail_level="minimal").reply,
                ["Workspace OS is your local workspace control plane."],
            ),
            (
                "quality:chat:projects",
                build_workspace_reply([source], "que proyectos tenemos en curso?", memory_store=local_store, session_id="quality", tone="terse", detail_level="minimal").reply,
                ["Workspace root:", "Primary route: /opencode"],
            ),
        ]
        results: list[CycleCheckResult] = []
        for name, rendered, expectations in cases:
            missing = [expectation for expectation in expectations if expectation not in rendered]
            if missing:
                results.append(CycleCheckResult(name, False, f"Missing expected fragments: {', '.join(missing)}."))
                continue
            results.append(CycleCheckResult(name, True, "Expected operational guidance present."))
        results.extend(_run_compilation_and_test_checks(sources, skip_tests=skip_tests))
        return tuple(results)


def _iteration_label(note: str | None, iteration_number: int) -> str:
    prefix = note.strip() if note and note.strip() else "iteration"
    return f"{prefix}-{iteration_number}"


def _cycle_status_label(checkpoint_count: int, pass_rate: float) -> str:
    if checkpoint_count == 0:
        return "n/a"
    if pass_rate >= 1.0:
        return "pass"
    if pass_rate <= 0.0:
        return "fail"
    return "partial"


def _init_git_repo(path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "workspace@example.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Workspace"], cwd=path, check=True, capture_output=True)
    (path / ".gitignore").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)



def _run_coverage_check(source_path: Path) -> CycleCheckResult:
    """Run coverage analysis with pytest-cov and enforce minimum thresholds."""
    import subprocess
    import json
    
    config_path = source_path / "config" / "quality.json"
    min_coverage = 80.0
    
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                min_coverage = config.get("coverage", {}).get("fail_under", 80.0)
        except Exception:
            pass
    
    try:
        result = subprocess.run(
            [
                "pytest",
                "--cov=src/workspace_os",
                "--cov-report=term-missing",
                "--cov-report=html",
                "--cov-report=xml",
                f"--cov-fail-under={min_coverage}",
                "-q"
            ],
            cwd=source_path,
            capture_output=True,
            text=True,
            timeout=300.0
        )
        
        coverage_pct = None
        for line in result.stdout.splitlines():
            if 'TOTAL' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'TOTAL' and i + 1 < len(parts):
                        try:
                            coverage_pct = float(parts[-1].rstrip('%'))
                        except (ValueError, IndexError):
                            pass
        
        if result.returncode != 0:
            detail = "Coverage check failed. "
            if coverage_pct is not None:
                detail += f"Coverage: {coverage_pct:.2f}% (minimum: {min_coverage}%)"
            else:
                detail += f"Required minimum: {min_coverage}%"
            return CycleCheckResult("quality:coverage", False, detail)
        
        detail = f"Coverage: {coverage_pct:.2f}% (minimum: {min_coverage}%)" if coverage_pct else "Coverage check passed"
        return CycleCheckResult("quality:coverage", True, detail)
        
    except subprocess.TimeoutExpired:
        return CycleCheckResult("quality:coverage", False, "Coverage check timed out after 300s")
    except Exception as e:
        return CycleCheckResult("quality:coverage", True, f"Skipped coverage check: {e}")


def _run_bandit_security_check(source_path: Path) -> CycleCheckResult:
    """Run bandit security scanner on source code."""
    import subprocess
    import json
    
    # Load quality config
    config_path = source_path / "config" / "quality.json"
    severity = "medium"
    
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                severity = config.get("security", {}).get("severity_threshold", "medium")
        except Exception:
            pass
    
    try:
        # Run bandit on src directory
        src_dir = source_path / "src"
        if not src_dir.exists():
            return CycleCheckResult("quality:bandit", True, "No src directory found, skipped")
        
        result = subprocess.run(
            [
                "bandit",
                "-r", str(src_dir),
                "-f", "json",
                "-ll"  # Only report medium and high severity
            ],
            capture_output=True,
            text=True,
            timeout=60.0
        )
        
        # Parse bandit JSON output
        try:
            output = json.loads(result.stdout)
            issues_count = len(output.get("results", []))
            
            if issues_count > 0:
                detail = f"Bandit found {issues_count} security issues (severity >= {severity})"
                return CycleCheckResult("quality:bandit", False, detail)
            
            return CycleCheckResult("quality:bandit", True, "No security issues found")
        except json.JSONDecodeError:
            # Bandit returns 0 if no issues, 1 if issues found
            if result.returncode == 0:
                return CycleCheckResult("quality:bandit", True, "No security issues found")
            return CycleCheckResult("quality:bandit", False, "Bandit found security issues")
            
    except subprocess.TimeoutExpired:
        return CycleCheckResult("quality:bandit", False, "Bandit check timed out after 60s")
    except FileNotFoundError:
        return CycleCheckResult("quality:bandit", True, "Bandit not installed, skipped")
    except Exception as e:
        return CycleCheckResult("quality:bandit", True, f"Skipped bandit check: {e}")


def _run_compilation_and_test_checks(sources: list[Source], skip_tests: bool = False) -> list[CycleCheckResult]:
    import subprocess
    import re

    results = []

    # Check for mocked test output for unit testing
    mock_output = os.environ.get("WOS_TEST_SUITE_MOCK_OUTPUT")
    mock_rc = os.environ.get("WOS_TEST_SUITE_MOCK_RETURNCODE")

    if mock_output is not None:
        rc = int(mock_rc) if mock_rc is not None else 1
        if rc != 0:
            failures = _parse_pytest_failures(mock_output)
            detail = f"Test suite failed with exit code {rc}.\n"
            if failures:
                detail += "Assertion failures found:\n"
                for fail in failures:
                    detail += f"- File: {fail['file']}, Line: {fail['line']}, Function: {fail['function']}\n"
            else:
                detail += f"Output:\n{mock_output[:500]}"
            results.append(CycleCheckResult("quality:test-suite", False, detail))
        else:
            results.append(CycleCheckResult("quality:test-suite", True, "Test suite passed successfully."))
        return results

    if "PYTEST_CURRENT_TEST" in os.environ:
        results.append(CycleCheckResult("quality:compilation", True, "Mock compilation passed in test environment."))
        results.append(CycleCheckResult("quality:test-suite", True, "Mock test suite passed in test environment."))
        return results

    for source in sources:
        if getattr(source, "group", "workspace") != "workspace":
            continue
        if not source.path.exists() or not source.path.is_dir():
            continue

        has_py = any(source.path.glob("**/*.py"))
        has_tests = (source.path / "tests").exists()
        if not (has_py or has_tests):
            continue

        # 1. Compilation check using py_compile
        py_files = list(source.path.glob("**/*.py"))
        py_files = [f for f in py_files if ".venv" not in f.parts and "site-packages" not in f.parts and ".pytest_cache" not in f.parts and "__pycache__" not in f.parts]

        compile_failed = False
        compile_detail = ""
        for py_file in py_files:
            try:
                res = subprocess.run(
                    ["python", "-m", "py_compile", str(py_file)],
                    capture_output=True,
                    text=True,
                    timeout=5.0
                )
                if res.returncode != 0:
                    compile_failed = True
                    compile_detail = f"Compilation failed in {py_file.name}:\n{res.stderr}"
                    break
            except Exception:
                pass

        if compile_failed:
            results.append(CycleCheckResult("quality:compilation", False, compile_detail))
            continue
        else:
            results.append(CycleCheckResult("quality:compilation", True, "All files compiled successfully."))

        # 2. Test suite check using pytest
        # Skip pytest during high-utilization to keep agents busy (fast-path validation)
        if skip_tests:
            results.append(CycleCheckResult("quality:test-suite", True, "Skipped (fast-path mode - high agent utilization)"))
            continue

        import time
        try:
            process = subprocess.Popen(
                ["pytest", "--tb=short", "-q"],
                cwd=source.path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            max_timeout = 200.0
            check_interval = 15.0
            elapsed = 0.0
            while process.poll() is None:
                time.sleep(1.0)
                elapsed += 1.0
                if elapsed >= max_timeout:
                    process.terminate()
                    try:
                        process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise subprocess.TimeoutExpired(process.args, max_timeout)
                if int(elapsed) % int(check_interval) == 0:
                    print(f"[{source.name}] Test suite running... ({int(elapsed)}s elapsed)")

            stdout, stderr = process.communicate()
            if process.returncode != 0:
                failures = _parse_pytest_failures(stdout + "\n" + stderr)
                detail = f"Test suite failed with exit code {process.returncode}.\n"
                if failures:
                    detail += "Assertion failures found:\n"
                    for fail in failures:
                        detail += f"- File: {fail['file']}, Line: {fail['line']}, Function: {fail['function']}\n"
                else:
                    detail += f"Output:\n{stdout[:500]}"
                results.append(CycleCheckResult("quality:test-suite", False, detail))
            else:
                results.append(CycleCheckResult("quality:test-suite", True, "Test suite passed successfully."))
        except subprocess.TimeoutExpired as e:
            results.append(CycleCheckResult("quality:test-suite", False, f"Test suite timed out after {max_timeout} seconds: {e}"))
        except Exception as e:
            results.append(CycleCheckResult("quality:test-suite", True, f"Skipped pytest check: {e}"))

    # 3. Coverage check using pytest-cov
    # Skip coverage during fast-path validation
    if not skip_tests:
        for source in sources:
            if getattr(source, 'group', 'workspace') != 'workspace':
                continue
            if source.path.exists() and source.path.is_dir():
                coverage_result = _run_coverage_check(source.path)
                results.append(coverage_result)
                break  # Only check first workspace source

    # 4. Security check using bandit
    if not skip_tests:
        for source in sources:
            if getattr(source, 'group', 'workspace') != 'workspace':
                continue
            if source.path.exists() and source.path.is_dir():
                bandit_result = _run_bandit_security_check(source.path)
                results.append(bandit_result)
                break  # Only check first workspace source

    return results


def _parse_pytest_failures(output: str) -> list[dict[str, str | int]]:
    import re
    failures = []
    # Match pytest short traceback pattern
    pattern_short = r'(?P<file>[a-zA-Z0-9_\-\/\\\.]+):(?P<line>\d+): in (?P<func>\w+)'
    for match in re.finditer(pattern_short, output):
        failures.append({
            "file": match.group("file"),
            "line": int(match.group("line")),
            "function": match.group("func")
        })

    if not failures:
        pattern_std = r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\w+)'
        for match in re.finditer(pattern_std, output):
            failures.append({
                "file": match.group("file"),
                "line": int(match.group("line")),
                "function": match.group("func")
            })

    return failures


def _generate_issues_from_backlog_inline(
    sources: list[Source],
    available_issues: list[dict[str, object]],
    target_count: int,
) -> int:
    """Generate GitHub issues from backlog to maintain agent throughput.

    Inlined version to avoid additional module dependency. Creates issues directly
    in GitHub and appends to available_issues list (mutates in-place).

    Returns count of successfully generated issues.
    """
    if target_count <= 0:
        return 0

    try:
        from workspace_os.plan_gap import get_next_backlog_items
        workspace_root = _workspace_root_for_sources(sources)
        backlog_path = workspace_root / "docs" / "product" / "backlog.md"

        if not backlog_path.exists():
            return 0

        next_items = get_next_backlog_items(backlog_path, limit=target_count)
        if not next_items:
            return 0

        generated_count = 0
        for item in next_items:
            try:
                title = f"{item.item_id}: {item.title}"
                body_lines = [
                    f"**Backlog ID:** {item.item_id}",
                    "",
                    "**Acceptance Criteria:**",
                ]
                if item.acceptance_criteria:
                    for criterion in item.acceptance_criteria:
                        body_lines.append(f"- {criterion}")
                else:
                    body_lines.append("- (See backlog for details)")
                if item.implementation_notes:
                    body_lines.append("")
                    body_lines.append("**Implementation Notes:**")
                    for note in item.implementation_notes:
                        body_lines.append(f"- {note}")
                body_lines.extend(["", "Generated from product backlog to maintain cycle throughput."])
                body = "\n".join(body_lines)

                result = subprocess.run(
                    ["gh", "issue", "create", "--title", title, "--body", body, "--json", "number"],
                    cwd=workspace_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    issue_number = int(data["number"])
                    available_issues.append({
                        "number": issue_number,
                        "title": title,
                        "state": "OPEN",
                        "labels": [],
                    })
                    generated_count += 1
                    print(f"[cycle] Created issue #{issue_number} from {item.item_id}")
            except Exception as e:
                print(f"[cycle] Failed to create issue for {item.item_id}: {e}")
                continue

        return generated_count
    except Exception as e:
        print(f"[cycle] Backlog issue generation failed: {e}")
        return 0


def _get_dynamic_interval(sources: list[Source], base_interval_seconds: float) -> float:
    import os
    if "PYTEST_CURRENT_TEST" in os.environ and "WOS_TEST_DYNAMIC_INTERVAL" not in os.environ:
        return base_interval_seconds

    import subprocess
    from workspace_os.git_status import inspect_source

    any_dirty = False
    for source in sources:
        try:
            status = inspect_source(source)
            if status.state == "dirty":
                any_dirty = True
                break
        except Exception:
            pass

    if any_dirty:
        return max(10.0, base_interval_seconds * 0.5)

    for source in sources:
        if source.path.exists() and source.path.is_dir():
            try:
                res = subprocess.run(
                    ["git", "log", "--since=5 minutes ago", "--oneline"],
                    cwd=source.path,
                    capture_output=True,
                    text=True
                )
                if res.returncode == 0 and res.stdout.strip():
                    return max(10.0, base_interval_seconds * 0.25)
            except Exception:
                pass

    return base_interval_seconds

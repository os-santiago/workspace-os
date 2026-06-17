from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
import tempfile
from collections.abc import Callable

from workspace_os.config import Source
from workspace_os.delegation import build_agent_route_command
from workspace_os.conscience import REFUSE, ALLOW_WITH_LIMITS, evaluate_request
from workspace_os.batch import start_batch, start_process
from workspace_os.conversation import build_workspace_reply
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.validation import ValidationResult, validate_workspace


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


def cycle_history_report(memory_store: WorkspaceMemoryStore, limit: int = 5) -> list[dict[str, str | None]]:
    return memory_store.cycle_history(limit=limit)


def run_cycle_evaluation(sources: list[Source], memory_store: WorkspaceMemoryStore) -> CycleEvaluation:
    health_results = _results_from_validation(validate_workspace(sources, include_housekeeping=False, include_smoke_queries=False))
    stability_results = _results_from_validation(
        [result for result in validate_workspace(sources, include_housekeeping=True, include_smoke_queries=False) if result.name == "housekeeping"]
    )
    security_results = _run_security_checks()
    quality_results = _run_quality_checks(sources, memory_store)
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
        sleep_for = min(interval_seconds, remaining_seconds)
        if sleep_for <= 0:
            break
        sleep_fn(sleep_for)
        iteration_number += 1

    ended_at = now_fn()
    if started_cycle:
        stop_cycle(memory_store, ended_at=ended_at.isoformat())

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
        target_duration_minutes=duration_minutes,
        window_started_at=started_at.isoformat(),
        window_ended_at=ended_at.isoformat(),
    )


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


def _run_quality_checks(sources: list[Source], memory_store: WorkspaceMemoryStore) -> tuple[CycleCheckResult, ...]:
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

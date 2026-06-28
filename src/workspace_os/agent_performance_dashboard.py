from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workspace_os.agent_queue import AgentQueueTracker, AgentTaskState


@dataclass(frozen=True)
class AgentRolePerformance:
    role: str
    task_count: int
    success_count: int
    failure_count: int
    avg_duration_seconds: float
    success_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "task_count": self.task_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_duration_seconds": self.avg_duration_seconds,
            "success_rate": self.success_rate,
        }


@dataclass(frozen=True)
class AgentPerformanceSummary:
    agent: str
    task_count: int
    success_count: int
    failure_count: int
    avg_duration_seconds: float
    success_rate: float
    recent_success_rate: float
    learning_velocity: float
    primary_count: int
    cross_check_count: int
    observer_count: int
    task_type_counts: dict[str, int]
    top_task_type: str | None
    specialization_note: str
    role_summaries: tuple[AgentRolePerformance, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "task_count": self.task_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_duration_seconds": self.avg_duration_seconds,
            "success_rate": self.success_rate,
            "recent_success_rate": self.recent_success_rate,
            "learning_velocity": self.learning_velocity,
            "primary_count": self.primary_count,
            "cross_check_count": self.cross_check_count,
            "observer_count": self.observer_count,
            "task_type_counts": dict(self.task_type_counts),
            "top_task_type": self.top_task_type,
            "specialization_note": self.specialization_note,
            "role_summaries": [summary.to_dict() for summary in self.role_summaries],
        }


@dataclass(frozen=True)
class AgentPerformanceDashboard:
    timestamp: str
    queue_depth: int
    queued_count: int
    running_count: int
    completed_count: int
    failed_count: int
    agent_count: int
    average_success_rate: float
    average_duration_seconds: float
    agent_summaries: tuple[AgentPerformanceSummary, ...]
    highlights: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "queue_depth": self.queue_depth,
            "queued_count": self.queued_count,
            "running_count": self.running_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "agent_count": self.agent_count,
            "average_success_rate": self.average_success_rate,
            "average_duration_seconds": self.average_duration_seconds,
            "agent_summaries": [summary.to_dict() for summary in self.agent_summaries],
            "highlights": list(self.highlights),
        }

    def render(self) -> str:
        lines = [
            f"Agent Performance Dashboard @ {self.timestamp}",
            f"Agents: {self.agent_count}",
            f"Queue depth: {self.queue_depth} (queued={self.queued_count}, running={self.running_count})",
            f"Average success rate: {self.average_success_rate:.2f}",
            f"Average duration: {self.average_duration_seconds:.1f}s",
        ]
        if self.highlights:
            lines.extend(["", "Highlights:"])
            lines.extend(f"- {item}" for item in self.highlights)
        if self.agent_summaries:
            lines.extend(["", "Per-agent performance:"])
            for summary in self.agent_summaries:
                lines.append(
                    f"- {summary.agent}: tasks={summary.task_count} success={summary.success_rate:.2f} "
                    f"avg={summary.avg_duration_seconds:.1f}s learning_velocity={summary.learning_velocity:+.2f}"
                )
                lines.append(
                    f"  roles: primary={summary.primary_count} cross-check={summary.cross_check_count} observer={summary.observer_count}"
                )
                if summary.specialization_note:
                    lines.append(f"  specialization: {summary.specialization_note}")
        return "\n".join(lines).strip() + "\n"


def build_agent_performance_dashboard(memory_path: Path) -> AgentPerformanceDashboard:
    tracker = AgentQueueTracker(memory_path.parent)
    snapshot = tracker.snapshot()
    tasks = list(snapshot.tasks)
    agent_groups: dict[str, list[Any]] = {}
    for task in tasks:
        agent_groups.setdefault(task.agent, []).append(task)

    agent_summaries = []
    for agent, agent_tasks in sorted(agent_groups.items()):
        completed = [task for task in agent_tasks if task.state in {AgentTaskState.COMPLETED, AgentTaskState.FAILED}]
        success_count = sum(1 for task in completed if task.state == AgentTaskState.COMPLETED)
        failure_count = sum(1 for task in completed if task.state == AgentTaskState.FAILED)
        task_count = len(agent_tasks)
        avg_duration = _average_duration(completed)
        success_rate = (success_count / len(completed)) if completed else 0.0
        recent_success_rate = _recent_success_rate(completed)
        learning_velocity = recent_success_rate - _previous_success_rate(completed)
        role_counts: dict[str, int] = {"primary": 0, "cross-check": 0, "observer": 0}
        role_duration: dict[str, list[float]] = {role: [] for role in role_counts}
        task_type_counts: dict[str, int] = {}
        for task in completed:
            role = _task_role(task)
            role_counts[role] = role_counts.get(role, 0) + 1
            if task.duration_seconds is not None:
                role_duration.setdefault(role, []).append(float(task.duration_seconds))
            task_type = _task_type(task)
            task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
        role_summaries = tuple(
            AgentRolePerformance(
                role=role,
                task_count=role_counts.get(role, 0),
                success_count=sum(1 for task in completed if _task_role(task) == role and task.state == AgentTaskState.COMPLETED),
                failure_count=sum(1 for task in completed if _task_role(task) == role and task.state == AgentTaskState.FAILED),
                avg_duration_seconds=_average_numbers(role_duration.get(role, [])),
                success_rate=_role_success_rate(completed, role),
            )
            for role in ("primary", "cross-check", "observer")
        )
        top_task_type = _top_key(task_type_counts)
        specialization_note = _specialization_note(role_counts, task_type_counts)
        agent_summaries.append(
            AgentPerformanceSummary(
                agent=agent,
                task_count=task_count,
                success_count=success_count,
                failure_count=failure_count,
                avg_duration_seconds=avg_duration,
                success_rate=success_rate,
                recent_success_rate=recent_success_rate,
                learning_velocity=learning_velocity,
                primary_count=role_counts.get("primary", 0),
                cross_check_count=role_counts.get("cross-check", 0),
                observer_count=role_counts.get("observer", 0),
                task_type_counts=task_type_counts,
                top_task_type=top_task_type,
                specialization_note=specialization_note,
                role_summaries=role_summaries,
            )
        )

    average_success_rate = _average_numbers([summary.success_rate for summary in agent_summaries])
    average_duration_seconds = _average_numbers([summary.avg_duration_seconds for summary in agent_summaries])
    highlights = _build_highlights(agent_summaries, snapshot.running_count + snapshot.queued_count)
    return AgentPerformanceDashboard(
        timestamp=_utc_now(),
        queue_depth=snapshot.running_count + snapshot.queued_count,
        queued_count=snapshot.queued_count,
        running_count=snapshot.running_count,
        completed_count=snapshot.completed_count,
        failed_count=snapshot.failed_count,
        agent_count=len(agent_summaries),
        average_success_rate=average_success_rate,
        average_duration_seconds=average_duration_seconds,
        agent_summaries=tuple(agent_summaries),
        highlights=highlights,
    )


def _task_role(task: Any) -> str:
    role = str(getattr(task, "metadata", {}).get("role") or "").strip().lower()
    if role in {"primary", "cross-check", "observer"}:
        return role
    task_id = str(getattr(task, "task_id", "")).lower()
    if task_id.endswith("-cross-check") or task_id.endswith("-cross_check"):
        return "cross-check"
    if task_id.endswith("-observer"):
        return "observer"
    return "primary"


def _task_type(task: Any) -> str:
    task_id = str(getattr(task, "task_id", "")).lower()
    if "cycle-work" in task_id:
        return "cycle_work"
    if "healing" in task_id:
        return "healing"
    if "checkpoint" in task_id:
        return "checkpoint"
    if "validation" in task_id:
        return "validation"
    if "review" in task_id:
        return "review"
    return "general"


def _average_duration(tasks: list[Any]) -> float:
    durations = [float(task.duration_seconds) for task in tasks if getattr(task, "duration_seconds", None) is not None]
    return _average_numbers(durations)


def _average_numbers(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _recent_success_rate(tasks: list[Any]) -> float:
    recent = tasks[-10:]
    if not recent:
        return 0.0
    success_count = sum(1 for task in recent if task.state == AgentTaskState.COMPLETED)
    return success_count / len(recent)


def _previous_success_rate(tasks: list[Any]) -> float:
    if len(tasks) <= 10:
        return _recent_success_rate(tasks)
    previous = tasks[-20:-10]
    if not previous:
        return 0.0
    success_count = sum(1 for task in previous if task.state == AgentTaskState.COMPLETED)
    return success_count / len(previous)


def _role_success_rate(tasks: list[Any], role: str) -> float:
    role_tasks = [task for task in tasks if _task_role(task) == role]
    if not role_tasks:
        return 0.0
    successes = sum(1 for task in role_tasks if task.state == AgentTaskState.COMPLETED)
    return successes / len(role_tasks)


def _top_key(values: dict[str, int]) -> str | None:
    if not values:
        return None
    ordered = sorted(values.items(), key=lambda item: (-item[1], item[0]))
    return ordered[0][0]


def _specialization_note(role_counts: dict[str, int], task_type_counts: dict[str, int]) -> str:
    best_role = _top_key(role_counts) or "primary"
    best_task_type = _top_key(task_type_counts) or "general"
    return f"best fit: role={best_role}, task_type={best_task_type}"


def _build_highlights(agent_summaries: list[AgentPerformanceSummary], queue_depth: int) -> tuple[str, ...]:
    if not agent_summaries:
        return ("No agent performance history available yet.",)
    top_success = max(agent_summaries, key=lambda summary: summary.success_rate)
    fastest = min(agent_summaries, key=lambda summary: summary.avg_duration_seconds if summary.avg_duration_seconds > 0 else float("inf"))
    improving = max(agent_summaries, key=lambda summary: summary.learning_velocity)
    highlights = [
        f"Best success rate: {top_success.agent} at {top_success.success_rate:.2f}",
        f"Fastest average duration: {fastest.agent} at {fastest.avg_duration_seconds:.1f}s",
        f"Strongest recent learning velocity: {improving.agent} at {improving.learning_velocity:+.2f}",
    ]
    if queue_depth > 0:
        highlights.append(f"Active queue depth: {queue_depth}")
    return tuple(highlights)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

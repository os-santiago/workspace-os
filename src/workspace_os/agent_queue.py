from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
import json


class AgentTaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTaskTrace:
    task_id: str
    agent: str
    workspace: str
    prompt: str
    state: AgentTaskState
    queued_at: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    returncode: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent": self.agent,
            "workspace": self.workspace,
            "prompt": self.prompt[:200] + "..." if len(self.prompt) > 200 else self.prompt,
            "state": self.state.value,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "returncode": self.returncode,
            "error": self.error,
            "metadata": self.metadata,
        }

    def render_summary(self) -> str:
        duration = f"{self.duration_seconds:.1f}s" if self.duration_seconds else "n/a"
        return (
            f"{self.task_id} [{self.state.value}] {self.agent} on {self.workspace} "
            f"(duration={duration}, rc={self.returncode or 'n/a'})"
        )


@dataclass
class AgentQueueSnapshot:
    timestamp: str
    queued_count: int
    running_count: int
    completed_count: int
    failed_count: int
    max_parallel: int
    tasks: tuple[AgentTaskTrace, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "queued_count": self.queued_count,
            "running_count": self.running_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "max_parallel": self.max_parallel,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    def render(self) -> str:
        lines = [
            f"Agent Queue Snapshot @ {self.timestamp}",
            f"Queued: {self.queued_count} | Running: {self.running_count} | Completed: {self.completed_count} | Failed: {self.failed_count}",
            f"Max parallel: {self.max_parallel}",
        ]
        if self.tasks:
            lines.append("\nTasks:")
            for task in self.tasks:
                lines.append(f"  {task.render_summary()}")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class AgentUtilizationSummary:
    agent: str
    task_count: int
    queued_count: int
    running_count: int
    completed_count: int
    failed_count: int
    active_seconds: float
    observed_span_seconds: float
    utilization_ratio: float
    peak_concurrent: int
    hourly_activity: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "task_count": self.task_count,
            "queued_count": self.queued_count,
            "running_count": self.running_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "active_seconds": self.active_seconds,
            "observed_span_seconds": self.observed_span_seconds,
            "utilization_ratio": self.utilization_ratio,
            "peak_concurrent": self.peak_concurrent,
            "hourly_activity": list(self.hourly_activity),
        }


@dataclass(frozen=True)
class AgentUtilizationReport:
    timestamp: str
    max_parallel: int
    observed_peak_parallel: int
    recommended_max_parallel: int
    overall_utilization_ratio: float
    idle_ratio: float
    window_start: str | None
    window_end: str | None
    hourly_totals: tuple[int, ...]
    idle_hours: tuple[int, ...]
    bottleneck_hours: tuple[int, ...]
    peak_hours: tuple[int, ...]
    recommendations: tuple[str, ...]
    agent_summaries: tuple[AgentUtilizationSummary, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "max_parallel": self.max_parallel,
            "observed_peak_parallel": self.observed_peak_parallel,
            "recommended_max_parallel": self.recommended_max_parallel,
            "overall_utilization_ratio": self.overall_utilization_ratio,
            "idle_ratio": self.idle_ratio,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "hourly_totals": list(self.hourly_totals),
            "idle_hours": list(self.idle_hours),
            "bottleneck_hours": list(self.bottleneck_hours),
            "peak_hours": list(self.peak_hours),
            "recommendations": list(self.recommendations),
            "agent_summaries": [summary.to_dict() for summary in self.agent_summaries],
        }

    def render(self) -> str:
        lines = [
            f"Agent Utilization Report @ {self.timestamp}",
            f"Configured max parallel: {self.max_parallel}",
            f"Observed peak parallel: {self.observed_peak_parallel}",
            f"Recommended max workers: {self.recommended_max_parallel}",
            f"Overall utilization: {self.overall_utilization_ratio:.2f}",
            f"Idle ratio: {self.idle_ratio:.2f}",
            f"Window: {self.window_start or 'n/a'} -> {self.window_end or 'n/a'}",
        ]
        if self.hourly_totals:
            lines.append("")
            lines.append("Hourly totals:")
            lines.append(_render_hour_header())
            lines.append(f"total  {_render_hour_heatmap(self.hourly_totals)}")
            lines.append(f"Idle hours: {_render_hour_list(self.idle_hours)}")
            lines.append(f"Bottleneck hours: {_render_hour_list(self.bottleneck_hours)}")
            lines.append(f"Peak hours: {_render_hour_list(self.peak_hours)}")
        if self.agent_summaries:
            lines.append("")
            lines.append("Agent heatmaps:")
            lines.append(_render_hour_header())
            for summary in self.agent_summaries:
                label = summary.agent[:5].ljust(5)
                lines.append(f"{label} {_render_hour_heatmap(summary.hourly_activity)} | util={summary.utilization_ratio:.2f} peak={summary.peak_concurrent}")
        if self.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            lines.extend(f"- {item}" for item in self.recommendations)
        return "\n".join(lines) + "\n"


class AgentQueueTracker:
    def __init__(self, memory_root: Path, max_parallel: int = 2):
        self.memory_root = memory_root
        self.max_parallel = max_parallel
        self.queue_file = memory_root / "agent_queue.jsonl"
        self._ensure_queue_file()

    def _ensure_queue_file(self) -> None:
        self.memory_root.mkdir(parents=True, exist_ok=True)
        if not self.queue_file.exists():
            self.queue_file.touch()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def enqueue(self, task_id: str, agent: str, workspace: str, prompt: str, metadata: dict[str, Any] | None = None) -> AgentTaskTrace:
        trace = AgentTaskTrace(
            task_id=task_id,
            agent=agent,
            workspace=workspace,
            prompt=prompt,
            state=AgentTaskState.QUEUED,
            queued_at=self._now_iso(),
            metadata=metadata or {},
        )
        self._append_trace(trace)
        return trace

    def start(self, task_id: str) -> None:
        tasks = self._load_all_tasks()
        for task in tasks:
            if task.task_id == task_id:
                task.state = AgentTaskState.RUNNING
                task.started_at = self._now_iso()
                break
        self._save_all_tasks(tasks)

    def complete(self, task_id: str, returncode: int, duration_seconds: float) -> dict[str, Any] | None:
        tasks = self._load_all_tasks()
        completed_metadata = None
        for task in tasks:
            if task.task_id == task_id:
                task.state = AgentTaskState.COMPLETED if returncode == 0 else AgentTaskState.FAILED
                task.completed_at = self._now_iso()
                task.returncode = returncode
                task.duration_seconds = duration_seconds
                completed_metadata = task.metadata.copy()
                break
        self._save_all_tasks(tasks)
        return completed_metadata

    def fail(self, task_id: str, error: str) -> None:
        tasks = self._load_all_tasks()
        for task in tasks:
            if task.task_id == task_id:
                task.state = AgentTaskState.FAILED
                task.completed_at = self._now_iso()
                task.error = error
                break
        self._save_all_tasks(tasks)

    def snapshot(self) -> AgentQueueSnapshot:
        tasks = self._load_all_tasks()
        return AgentQueueSnapshot(
            timestamp=self._now_iso(),
            queued_count=sum(1 for t in tasks if t.state == AgentTaskState.QUEUED),
            running_count=sum(1 for t in tasks if t.state == AgentTaskState.RUNNING),
            completed_count=sum(1 for t in tasks if t.state == AgentTaskState.COMPLETED),
            failed_count=sum(1 for t in tasks if t.state == AgentTaskState.FAILED),
            max_parallel=self.max_parallel,
            tasks=tuple(tasks),
        )

    def recent_tasks(self, limit: int = 20) -> tuple[AgentTaskTrace, ...]:
        tasks = self._load_all_tasks()
        return tuple(tasks[-limit:]) if tasks else ()

    def utilization_report(self) -> AgentUtilizationReport:
        tasks = self._load_all_tasks()
        now = datetime.now(timezone.utc)
        if not tasks:
            return AgentUtilizationReport(
                timestamp=self._now_iso(),
                max_parallel=self.max_parallel,
                observed_peak_parallel=0,
                recommended_max_parallel=self.max_parallel,
                overall_utilization_ratio=0.0,
                idle_ratio=1.0,
                window_start=None,
                window_end=None,
                hourly_totals=tuple(0 for _ in range(24)),
                idle_hours=tuple(range(24)),
                bottleneck_hours=(),
                peak_hours=(),
                recommendations=("No utilization data is available yet.",),
                agent_summaries=(),
            )

        window_start: datetime | None = None
        window_end: datetime | None = None
        hourly_totals = [0 for _ in range(24)]
        by_agent: dict[str, list[AgentTaskTrace]] = {}
        events: list[tuple[datetime, int]] = []
        total_active_seconds = 0.0

        for task in tasks:
            by_agent.setdefault(task.agent, []).append(task)
            started = _parse_datetime(task.started_at) or _parse_datetime(task.queued_at)
            ended = _parse_datetime(task.completed_at)
            if ended is None and task.state == AgentTaskState.RUNNING:
                ended = now
            if started is None:
                started = ended
            if started is None:
                continue
            if ended is None:
                ended = started

            hour = started.hour
            hourly_totals[hour] += 1

            if window_start is None or started < window_start:
                window_start = started
            if window_end is None or ended > window_end:
                window_end = ended

            events.append((started, 1))
            events.append((ended, -1))

            if ended >= started:
                total_active_seconds += (ended - started).total_seconds()

        observed_peak = _peak_concurrency(events)
        peak_load = max(hourly_totals) if hourly_totals else 0
        idle_hours = tuple(hour for hour, value in enumerate(hourly_totals) if value == 0)
        bottleneck_hours = tuple(hour for hour, value in enumerate(hourly_totals) if value > self.max_parallel)
        peak_hours = tuple(hour for hour, value in enumerate(hourly_totals) if value == peak_load and peak_load > 0)
        window_seconds = 0.0
        if window_start is not None and window_end is not None:
            window_seconds = max(0.0, (window_end - window_start).total_seconds())
        capacity_seconds = window_seconds * max(self.max_parallel, 1)
        overall_utilization = 0.0 if capacity_seconds <= 0 else min(1.0, total_active_seconds / capacity_seconds)
        idle_ratio = 1.0 - overall_utilization
        recommended_max_parallel = _recommend_max_parallel(self.max_parallel, observed_peak, overall_utilization)
        recommendations = _build_utilization_recommendations(
            max_parallel=self.max_parallel,
            observed_peak_parallel=observed_peak,
            recommended_max_parallel=recommended_max_parallel,
            overall_utilization_ratio=overall_utilization,
            idle_hours=idle_hours,
            bottleneck_hours=bottleneck_hours,
            peak_hours=peak_hours,
        )

        agent_summaries = []
        for agent, agent_tasks in sorted(by_agent.items()):
            agent_window_start: datetime | None = None
            agent_window_end: datetime | None = None
            agent_hourly = [0 for _ in range(24)]
            agent_events: list[tuple[datetime, int]] = []
            active_seconds = 0.0
            counts = {
                AgentTaskState.QUEUED: 0,
                AgentTaskState.RUNNING: 0,
                AgentTaskState.COMPLETED: 0,
                AgentTaskState.FAILED: 0,
            }
            for task in agent_tasks:
                counts[task.state] += 1
                started = _parse_datetime(task.started_at) or _parse_datetime(task.queued_at)
                ended = _parse_datetime(task.completed_at)
                if ended is None and task.state == AgentTaskState.RUNNING:
                    ended = now
                if started is None:
                    started = ended
                if started is None:
                    continue
                if ended is None:
                    ended = started
                agent_hourly[started.hour] += 1
                if agent_window_start is None or started < agent_window_start:
                    agent_window_start = started
                if agent_window_end is None or ended > agent_window_end:
                    agent_window_end = ended
                agent_events.append((started, 1))
                agent_events.append((ended, -1))
                if ended >= started:
                    active_seconds += (ended - started).total_seconds()

            agent_span_seconds = 0.0
            if agent_window_start is not None and agent_window_end is not None:
                agent_span_seconds = max(0.0, (agent_window_end - agent_window_start).total_seconds())
            agent_capacity = agent_span_seconds if agent_span_seconds > 0 else 0.0
            utilization_ratio = 0.0 if agent_capacity <= 0 else min(1.0, active_seconds / agent_capacity)
            agent_summaries.append(
                AgentUtilizationSummary(
                    agent=agent,
                    task_count=len(agent_tasks),
                    queued_count=counts[AgentTaskState.QUEUED],
                    running_count=counts[AgentTaskState.RUNNING],
                    completed_count=counts[AgentTaskState.COMPLETED],
                    failed_count=counts[AgentTaskState.FAILED],
                    active_seconds=active_seconds,
                    observed_span_seconds=agent_span_seconds,
                    utilization_ratio=utilization_ratio,
                    peak_concurrent=_peak_concurrency(agent_events),
                    hourly_activity=tuple(agent_hourly),
                )
            )

        return AgentUtilizationReport(
            timestamp=self._now_iso(),
            max_parallel=self.max_parallel,
            observed_peak_parallel=observed_peak,
            recommended_max_parallel=recommended_max_parallel,
            overall_utilization_ratio=overall_utilization,
            idle_ratio=idle_ratio,
            window_start=window_start.isoformat() if window_start else None,
            window_end=window_end.isoformat() if window_end else None,
            hourly_totals=tuple(hourly_totals),
            idle_hours=idle_hours,
            bottleneck_hours=bottleneck_hours,
            peak_hours=peak_hours,
            recommendations=tuple(recommendations),
            agent_summaries=tuple(agent_summaries),
        )

    def _append_trace(self, trace: AgentTaskTrace) -> None:
        with open(self.queue_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace.to_dict()) + "\n")

    def _load_all_tasks(self) -> list[AgentTaskTrace]:
        if not self.queue_file.exists():
            return []
        tasks: dict[str, AgentTaskTrace] = {}
        with open(self.queue_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    tasks[data["task_id"]] = AgentTaskTrace(
                        task_id=data["task_id"],
                        agent=data["agent"],
                        workspace=data["workspace"],
                        prompt=data["prompt"],
                        state=AgentTaskState(data["state"]),
                        queued_at=data["queued_at"],
                        started_at=data.get("started_at"),
                        completed_at=data.get("completed_at"),
                        duration_seconds=data.get("duration_seconds"),
                        returncode=data.get("returncode"),
                        error=data.get("error"),
                        metadata=data.get("metadata", {}),
                    )
        return list(tasks.values())

    def _save_all_tasks(self, tasks: list[AgentTaskTrace]) -> None:
        with open(self.queue_file, "w", encoding="utf-8") as f:
            for task in tasks:
                f.write(json.dumps(task.to_dict()) + "\n")

    def clear_completed(self, keep_recent: int = 100) -> int:
        tasks = self._load_all_tasks()
        completed_or_failed = [
            t for t in tasks if t.state in (AgentTaskState.COMPLETED, AgentTaskState.FAILED)
        ]
        if len(completed_or_failed) <= keep_recent:
            return 0
        to_remove = len(completed_or_failed) - keep_recent
        keep_tasks = [t for t in tasks if t.state not in (AgentTaskState.COMPLETED, AgentTaskState.FAILED)]
        keep_tasks.extend(completed_or_failed[-keep_recent:])
        self._save_all_tasks(keep_tasks)
        return to_remove

    def get_issue_outcomes(self) -> dict[int, list[dict[str, Any]]]:
        """Get all work items grouped by GitHub issue number.

        Returns a dictionary mapping issue numbers to lists of work items that
        addressed that issue. Each work item includes task_id, agent, state,
        duration, and outcome metadata.

        This enables traceability: which agents worked on which issues, how long
        they took, and what the outcomes were.
        """
        tasks = self._load_all_tasks()
        outcomes: dict[int, list[dict[str, Any]]] = {}

        for task in tasks:
            issue_number = task.metadata.get("issue_number")
            if issue_number is not None:
                issue_num = int(issue_number)
                if issue_num not in outcomes:
                    outcomes[issue_num] = []

                outcome = {
                    "task_id": task.task_id,
                    "agent": task.agent,
                    "state": task.state.value,
                    "duration_seconds": task.duration_seconds,
                    "returncode": task.returncode,
                    "queued_at": task.queued_at,
                    "completed_at": task.completed_at,
                    "work_item_number": task.metadata.get("work_item_number"),
                    "role": task.metadata.get("role"),
                }
                outcomes[issue_num].append(outcome)

        return outcomes

    def render_issue_outcomes(self, limit: int = 20) -> str:
        """Render a summary of issue outcomes for recent work.

        Shows which issues were worked on, by which agents, with what outcomes.
        Useful for understanding agent productivity and identifying stalled issues.
        """
        outcomes = self.get_issue_outcomes()
        if not outcomes:
            return "No issue outcomes tracked yet.\n"

        lines = ["Issue Outcomes Summary:", ""]
        # Sort by most recent activity (latest completed_at among work items)
        sorted_issues = sorted(
            outcomes.items(),
            key=lambda x: max(
                (item["completed_at"] or item["queued_at"]) for item in x[1]
            ),
            reverse=True
        )[:limit]

        for issue_num, work_items in sorted_issues:
            completed = [w for w in work_items if w["state"] == "completed"]
            failed = [w for w in work_items if w["state"] == "failed"]
            running = [w for w in work_items if w["state"] == "running"]

            total_duration = sum(w["duration_seconds"] or 0 for w in work_items)
            agents_used = {w["agent"] for w in work_items}

            status_parts = []
            if completed:
                status_parts.append(f"{len(completed)} completed")
            if running:
                status_parts.append(f"{len(running)} running")
            if failed:
                status_parts.append(f"{len(failed)} failed")

            status = ", ".join(status_parts)
            agents_str = ", ".join(sorted(agents_used))

            lines.append(
                f"Issue #{issue_num}: {len(work_items)} work items ({status}) | "
                f"agents: {agents_str} | total time: {total_duration:.1f}s"
            )

            # Show individual work items for this issue
            for item in sorted(work_items, key=lambda w: w["queued_at"]):
                duration_str = f"{item['duration_seconds']:.1f}s" if item["duration_seconds"] else "n/a"
                lines.append(
                    f"  - {item['task_id']}: {item['agent']} {item['state']} "
                    f"(duration={duration_str}, role={item['role']})"
                )

        return "\n".join(lines) + "\n"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _peak_concurrency(events: list[tuple[datetime, int]]) -> int:
    if not events:
        return 0
    current = 0
    peak = 0
    for when, delta in sorted(events, key=lambda item: (item[0], 0 if item[1] > 0 else 1)):
        current += delta
        if current > peak:
            peak = current
    return peak


def _recommend_max_parallel(max_parallel: int, observed_peak_parallel: int, utilization_ratio: float) -> int:
    if observed_peak_parallel > max_parallel:
        return observed_peak_parallel
    if utilization_ratio < 0.35 and max_parallel > 1:
        return max_parallel - 1
    if utilization_ratio > 0.85 and observed_peak_parallel >= max_parallel:
        return max_parallel + 1
    return max_parallel


def _build_utilization_recommendations(
    *,
    max_parallel: int,
    observed_peak_parallel: int,
    recommended_max_parallel: int,
    overall_utilization_ratio: float,
    idle_hours: tuple[int, ...],
    bottleneck_hours: tuple[int, ...],
    peak_hours: tuple[int, ...],
) -> tuple[str, ...]:
    recommendations: list[str] = []
    if overall_utilization_ratio < 0.35:
        recommendations.append("Utilization is low; consider reducing max_workers or batching work more aggressively.")
    elif overall_utilization_ratio > 0.85 and observed_peak_parallel >= max_parallel:
        recommendations.append("Utilization is saturated; increase max_workers if the queue stays backed up.")
    else:
        recommendations.append("Utilization is balanced; keep the current max_workers setting and monitor the peak hours.")

    if bottleneck_hours:
        recommendations.append(f"Bottleneck hours: {_render_hour_list(bottleneck_hours)} exceed the configured max_workers limit.")
    elif peak_hours:
        recommendations.append(f"Peak hours cluster around {_render_hour_list(peak_hours)}; align heavier work there when possible.")

    if idle_hours:
        recommendations.append(f"Idle hours: {_render_hour_list(idle_hours)} are available for delayed or background work.")

    if recommended_max_parallel != max_parallel:
        recommendations.append(f"Suggested max_workers adjustment: {recommended_max_parallel}.")
    return tuple(recommendations)


def _render_hour_header() -> str:
    return "       00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23"


def _render_hour_list(values: tuple[int, ...] | list[int]) -> str:
    series = [int(value) for value in values]
    if not series:
        return "none"
    return ", ".join(f"{value:02d}" for value in series)


def _render_hour_heatmap(values: tuple[int, ...] | list[int]) -> str:
    palette = " .:-=+*#%@"
    if not values:
        return ""
    maximum = max(values) if max(values) > 0 else 0
    if maximum <= 0:
        return "." * len(values)
    chars = []
    scale = len(palette) - 1
    for value in values:
        level = int(round((value / maximum) * scale))
        level = max(0, min(scale, level))
        chars.append(palette[level])
    return "".join(chars)

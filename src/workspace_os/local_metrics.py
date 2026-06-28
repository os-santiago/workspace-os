from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import os
from typing import Any

from workspace_os.agent_queue import AgentQueueTracker
from workspace_os.memory import WorkspaceMemoryStore


SUPPORTED_EXPORTERS = ("prometheus", "grafana-json")


@dataclass(frozen=True)
class LocalMetricsReport:
    timestamp: str
    cycle_id: int | None
    cycle_label: str | None
    cycle_objective: str | None
    cycle_started_at: str | None
    cycle_ended_at: str | None
    cycle_duration_seconds: float
    checkpoint_count: int
    latest_checkpoint_label: str | None
    latest_checkpoint_note: str | None
    task_outcome_total: int
    task_success_count: int
    task_failure_count: int
    task_partial_count: int
    success_rate: float
    failure_rate: float
    partial_rate: float
    queue_depth: int
    queued_count: int
    running_count: int
    agent_utilization_ratio: float
    observed_peak_parallel: int
    recommended_max_parallel: int
    blockage_indicators: tuple[str, ...]
    available_exporters: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cycle_id": self.cycle_id,
            "cycle_label": self.cycle_label,
            "cycle_objective": self.cycle_objective,
            "cycle_started_at": self.cycle_started_at,
            "cycle_ended_at": self.cycle_ended_at,
            "cycle_duration_seconds": self.cycle_duration_seconds,
            "checkpoint_count": self.checkpoint_count,
            "latest_checkpoint_label": self.latest_checkpoint_label,
            "latest_checkpoint_note": self.latest_checkpoint_note,
            "task_outcome_total": self.task_outcome_total,
            "task_success_count": self.task_success_count,
            "task_failure_count": self.task_failure_count,
            "task_partial_count": self.task_partial_count,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "partial_rate": self.partial_rate,
            "queue_depth": self.queue_depth,
            "queued_count": self.queued_count,
            "running_count": self.running_count,
            "agent_utilization_ratio": self.agent_utilization_ratio,
            "observed_peak_parallel": self.observed_peak_parallel,
            "recommended_max_parallel": self.recommended_max_parallel,
            "blockage_indicators": list(self.blockage_indicators),
            "available_exporters": list(self.available_exporters),
        }

    def render(self) -> str:
        lines = [
            f"WOS Local Metrics @ {self.timestamp}",
            f"Cycle: {self.cycle_label or 'n/a'}",
            f"Objective: {self.cycle_objective or 'n/a'}",
            f"Cycle duration: {self.cycle_duration_seconds:.1f}s",
            f"Checkpoint count: {self.checkpoint_count}",
            f"Latest checkpoint: {self.latest_checkpoint_label or 'n/a'}",
            f"Queue depth: {self.queue_depth} (queued={self.queued_count}, running={self.running_count})",
            f"Agent utilization: {self.agent_utilization_ratio:.2f}",
            f"Observed peak parallel: {self.observed_peak_parallel}",
            f"Recommended max workers: {self.recommended_max_parallel}",
            "",
            "Task outcomes:",
            f"- total={self.task_outcome_total}",
            f"- success_rate={self.success_rate:.2f}",
            f"- failure_rate={self.failure_rate:.2f}",
            f"- partial_rate={self.partial_rate:.2f}",
            "",
            "Blockage indicators:",
            *(_render_bullet_list(self.blockage_indicators) or ["- none"]),
            "",
            "Available exporters:",
            *(_render_bullet_list(self.available_exporters) or ["- none"]),
        ]
        return "\n".join(lines).strip() + "\n"


def build_local_metrics_report(memory_path: Path) -> LocalMetricsReport:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    cycle = _selected_cycle(store)
    cycle_report = _cycle_report(store, cycle)
    queue_tracker = AgentQueueTracker(memory_path.parent)
    queue_snapshot = queue_tracker.snapshot()
    utilization_report = queue_tracker.utilization_report()
    task_totals = store.task_outcome_metrics()
    task_success_count = sum(int(row["success_count"]) for row in task_totals)
    task_failure_count = sum(int(row["failure_count"]) for row in task_totals)
    task_partial_count = sum(int(row["partial_count"]) for row in task_totals)
    task_outcome_total = sum(int(row["total"]) for row in task_totals)
    success_rate = task_success_count / task_outcome_total if task_outcome_total else 0.0
    failure_rate = task_failure_count / task_outcome_total if task_outcome_total else 0.0
    partial_rate = task_partial_count / task_outcome_total if task_outcome_total else 0.0
    queue_depth = queue_snapshot.queued_count + queue_snapshot.running_count
    blockage_indicators = _blockage_indicators(
        cycle_duration_seconds=float(cycle_report["duration_seconds"]) if cycle_report else 0.0,
        checkpoint_count=int(cycle_report["checkpoint_count"]) if cycle_report else 0,
        queue_depth=queue_depth,
        agent_utilization_ratio=utilization_report.overall_utilization_ratio,
        task_failure_count=task_failure_count,
        task_partial_count=task_partial_count,
    )
    cycle_duration_seconds = _cycle_duration_seconds(cycle_report)
    return LocalMetricsReport(
        timestamp=_utc_now(),
        cycle_id=int(cycle_report["cycle_id"]) if cycle_report else None,
        cycle_label=cycle_report["cycle"].get("label") if cycle_report else None,
        cycle_objective=cycle_report["cycle"].get("objective") if cycle_report else None,
        cycle_started_at=cycle_report["cycle"].get("started_at") if cycle_report else None,
        cycle_ended_at=cycle_report["cycle"].get("ended_at") if cycle_report else None,
        cycle_duration_seconds=cycle_duration_seconds,
        checkpoint_count=int(cycle_report["checkpoint_count"]) if cycle_report else 0,
        latest_checkpoint_label=cycle_report["latest_checkpoint"].get("label") if cycle_report and cycle_report["latest_checkpoint"] else None,
        latest_checkpoint_note=cycle_report["latest_checkpoint"].get("note") if cycle_report and cycle_report["latest_checkpoint"] else None,
        task_outcome_total=task_outcome_total,
        task_success_count=task_success_count,
        task_failure_count=task_failure_count,
        task_partial_count=task_partial_count,
        success_rate=success_rate,
        failure_rate=failure_rate,
        partial_rate=partial_rate,
        queue_depth=queue_depth,
        queued_count=queue_snapshot.queued_count,
        running_count=queue_snapshot.running_count,
        agent_utilization_ratio=utilization_report.overall_utilization_ratio,
        observed_peak_parallel=utilization_report.observed_peak_parallel,
        recommended_max_parallel=utilization_report.recommended_max_parallel,
        blockage_indicators=blockage_indicators,
        available_exporters=configured_exporters(),
    )


def render_local_metrics_markdown(report: LocalMetricsReport) -> str:
    return report.render()


def configured_exporters() -> tuple[str, ...]:
    raw = os.environ.get("WOS_METRICS_EXPORTERS", "")
    entries = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return tuple(name for name in entries if name in SUPPORTED_EXPORTERS)


def render_metrics_export(report: LocalMetricsReport, exporter: str) -> str:
    normalized = exporter.strip().lower()
    if normalized not in configured_exporters():
        raise ValueError(f"Exporter '{exporter}' is not enabled.")
    if normalized == "prometheus":
        return _render_prometheus(report)
    if normalized == "grafana-json":
        return _render_grafana_json(report)
    raise ValueError(f"Unsupported exporter '{exporter}'.")


def _selected_cycle(store: WorkspaceMemoryStore) -> dict[str, str | None] | None:
    active = store.active_cycle()
    if active is not None:
        return active
    history = store.cycle_history(limit=1)
    return history[0] if history else None


def _cycle_report(store: WorkspaceMemoryStore, cycle: dict[str, str | None] | None) -> dict[str, object] | None:
    if cycle is None:
        return None
    report = store.cycle_report(int(cycle["id"]))
    if report is None:
        return None
    report["duration_seconds"] = _duration_seconds(str(report["cycle"]["started_at"]), str(report["cycle"]["ended_at"] or _utc_now()))
    return report


def _blockage_indicators(
    *,
    cycle_duration_seconds: float,
    checkpoint_count: int,
    queue_depth: int,
    agent_utilization_ratio: float,
    task_failure_count: int,
    task_partial_count: int,
) -> tuple[str, ...]:
    indicators: list[str] = []
    if task_failure_count > 0:
        indicators.append("task failures recorded")
    if task_partial_count > 0:
        indicators.append("partial outcomes recorded")
    if queue_depth > 0 and agent_utilization_ratio < 0.35:
        indicators.append("queued work with low utilization")
    if checkpoint_count == 0 and cycle_duration_seconds > 0:
        indicators.append("cycle has not checkpointed yet")
    return tuple(indicators)


def _render_bullet_list(values: tuple[str, ...] | list[str]) -> list[str]:
    items = [str(value).strip() for value in values if str(value).strip()]
    return [f"- {item}" for item in items]


def _render_prometheus(report: LocalMetricsReport) -> str:
    cycle_labels = []
    if report.cycle_label:
        cycle_labels.append(f'cycle="{_escape_prometheus_label(report.cycle_label)}"')
    label_prefix = f"{{{', '.join(cycle_labels)}}}" if cycle_labels else ""
    lines = [
        "# HELP wos_cycle_duration_seconds Current cycle duration in seconds.",
        "# TYPE wos_cycle_duration_seconds gauge",
        f"wos_cycle_duration_seconds{label_prefix} {report.cycle_duration_seconds:.3f}",
        "# HELP wos_checkpoint_count Current cycle checkpoint count.",
        "# TYPE wos_checkpoint_count gauge",
        f"wos_checkpoint_count{label_prefix} {report.checkpoint_count}",
        "# HELP wos_task_outcomes_total Total task outcomes observed locally.",
        "# TYPE wos_task_outcomes_total gauge",
        f"wos_task_outcomes_total{label_prefix} {report.task_outcome_total}",
        "# HELP wos_task_success_rate Task success rate.",
        "# TYPE wos_task_success_rate gauge",
        f"wos_task_success_rate{label_prefix} {report.success_rate:.6f}",
        "# HELP wos_task_failure_rate Task failure rate.",
        "# TYPE wos_task_failure_rate gauge",
        f"wos_task_failure_rate{label_prefix} {report.failure_rate:.6f}",
        "# HELP wos_queue_depth Current queued plus running work items.",
        "# TYPE wos_queue_depth gauge",
        f"wos_queue_depth{label_prefix} {report.queue_depth}",
        "# HELP wos_agent_utilization_ratio Local agent utilization ratio.",
        "# TYPE wos_agent_utilization_ratio gauge",
        f"wos_agent_utilization_ratio{label_prefix} {report.agent_utilization_ratio:.6f}",
        "# HELP wos_regression_blockage_indicator 1 when a blockage signal is present.",
        "# TYPE wos_regression_blockage_indicator gauge",
        f"wos_regression_blockage_indicator{label_prefix} {1 if report.blockage_indicators else 0}",
    ]
    return "\n".join(lines) + "\n"


def _render_grafana_json(report: LocalMetricsReport) -> str:
    payload = {
        "title": "WOS Local Metrics",
        "summary": report.to_dict(),
        "series": [
            {"metric": "cycle_duration_seconds", "value": report.cycle_duration_seconds, "unit": "seconds"},
            {"metric": "checkpoint_count", "value": report.checkpoint_count, "unit": "count"},
            {"metric": "task_success_rate", "value": report.success_rate, "unit": "ratio"},
            {"metric": "task_failure_rate", "value": report.failure_rate, "unit": "ratio"},
            {"metric": "queue_depth", "value": report.queue_depth, "unit": "count"},
            {"metric": "agent_utilization_ratio", "value": report.agent_utilization_ratio, "unit": "ratio"},
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _escape_prometheus_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace("\"", "\\\"")


def _duration_seconds(started_at: str, ended_at: str) -> float:
    start = _parse_datetime(started_at)
    end = _parse_datetime(ended_at)
    if start is None or end is None:
        return 0.0
    return max(0.0, (end - start).total_seconds())


def _cycle_duration_seconds(cycle_report: dict[str, object] | None) -> float:
    if cycle_report is None:
        return 0.0
    cycle = cycle_report.get("cycle")
    if not isinstance(cycle, dict):
        return 0.0
    started_at = str(cycle.get("started_at") or "")
    ended_at = str(cycle.get("ended_at") or _utc_now())
    return _duration_seconds(started_at, ended_at)


def _parse_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

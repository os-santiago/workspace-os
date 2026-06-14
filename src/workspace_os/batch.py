from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from workspace_os.memory import WorkspaceMemoryStore


@dataclass(frozen=True)
class BatchReport:
    batch_id: int
    label: str
    objective: str
    started_at: str
    ended_at: str
    duration_seconds: float
    delegations: int
    defect_iterations: int
    task_success_count: int
    task_failure_count: int
    task_partial_count: int
    conversation_turns: int

    def render(self) -> str:
        duration = _format_duration(self.duration_seconds)
        lines = [
            "Batch report",
            f"batch_id={self.batch_id}",
            f"label={self.label}",
            f"objective={self.objective}",
            f"started_at={self.started_at}",
            f"ended_at={self.ended_at}",
            f"duration={duration}",
            f"delegations={self.delegations}",
            f"defect_iterations={self.defect_iterations}",
            f"task_success_count={self.task_success_count}",
            f"task_failure_count={self.task_failure_count}",
            f"task_partial_count={self.task_partial_count}",
            f"conversation_turns={self.conversation_turns}",
        ]
        return "\n".join(lines) + "\n"


def start_batch(memory_store: WorkspaceMemoryStore, label: str, objective: str, started_at: str | None = None) -> int:
    return memory_store.start_batch(label, objective, started_at=started_at)


def start_process(memory_store: WorkspaceMemoryStore, label: str, objective: str, started_at: str | None = None) -> int:
    return memory_store.start_process(label, objective, started_at=started_at)


def stop_batch(memory_store: WorkspaceMemoryStore, ended_at: str | None = None) -> BatchReport | None:
    batch = memory_store.finish_active_batch(ended_at=ended_at)
    if batch is None:
        return None
    report = memory_store.batch_metrics(batch_id=int(batch["id"]), now=ended_at)
    return _build_report(report)


def stop_process(memory_store: WorkspaceMemoryStore, ended_at: str | None = None) -> ProcessSummary | None:
    process = memory_store.finish_active_process(ended_at=ended_at)
    if process is None:
        return None
    return _build_process_report(memory_store, int(process["id"]), now=ended_at)


def current_batch_report(memory_store: WorkspaceMemoryStore, batch_id: int | None = None, now: str | None = None) -> BatchReport | None:
    report = memory_store.batch_metrics(batch_id=batch_id, now=now)
    if report is None:
        return None
    return _build_report(report)


def current_process_report(memory_store: WorkspaceMemoryStore, process_id: int | None = None, now: str | None = None) -> ProcessSummary | None:
    report = memory_store.process_metrics(process_id=process_id, now=now)
    if report is None:
        return None
    return _build_process_report(memory_store, int(report["process_id"]), now=now)


@dataclass(frozen=True)
class BatchSummaryItem:
    batch_id: int
    label: str
    duration_seconds: float
    defect_iterations: int

    def render(self) -> str:
        duration = _format_duration(self.duration_seconds)
        return f"- {self.batch_id} {self.label}: duration={duration} defects={self.defect_iterations}"


@dataclass(frozen=True)
class BatchSummary:
    total_batches: int
    process_started_at: str | None
    process_ended_at: str | None
    process_duration_seconds: float
    total_defect_iterations: int
    items: tuple[BatchSummaryItem, ...]

    def render(self) -> str:
        lines = [
            f"batches={self.total_batches}",
            f"process_started_at={self.process_started_at or 'n/a'}",
            f"process_ended_at={self.process_ended_at or 'n/a'}",
            f"process_duration={_format_duration(self.process_duration_seconds)}",
            f"defect_iterations_total={self.total_defect_iterations}",
        ]
        lines.extend(item.render() for item in self.items)
        return "\n".join(lines) + "\n"


def batch_summary(memory_store: WorkspaceMemoryStore, limit: int = 10) -> BatchSummary:
    items = []
    process_started_at: str | None = None
    process_ended_at: str | None = None
    total_defects = 0
    for batch in memory_store.batch_history(limit=limit):
        batch_id = int(batch["id"])
        report = current_batch_report(memory_store, batch_id=batch_id)
        if report is None:
            continue
        total_defects += report.defect_iterations
        process_started_at = _earliest_timestamp(process_started_at, report.started_at)
        process_ended_at = _latest_timestamp(process_ended_at, report.ended_at)
        items.append(
            BatchSummaryItem(
                batch_id=report.batch_id,
                label=report.label,
                duration_seconds=report.duration_seconds,
                defect_iterations=report.defect_iterations,
            )
        )
    process_duration = 0.0
    if process_started_at and process_ended_at:
        process_duration = _span_seconds(process_started_at, process_ended_at)
    return BatchSummary(
        total_batches=len(items),
        process_started_at=process_started_at,
        process_ended_at=process_ended_at,
        process_duration_seconds=process_duration,
        total_defect_iterations=total_defects,
        items=tuple(items),
    )


@dataclass(frozen=True)
class ProcessSummary:
    process_id: int
    label: str
    objective: str
    started_at: str
    ended_at: str
    duration_seconds: float
    batch_count: int
    delegations: int
    defect_iterations: int
    checkpoint_count: int
    latest_checkpoint_label: str | None
    latest_checkpoint_note: str | None

    def render(self) -> str:
        lines = [
            "Process summary",
            f"process_id={self.process_id}",
            f"label={self.label}",
            f"objective={self.objective}",
            f"started_at={self.started_at}",
            f"ended_at={self.ended_at}",
            f"duration={_format_duration(self.duration_seconds)}",
            f"batch_count={self.batch_count}",
            f"delegations={self.delegations}",
            f"defect_iterations={self.defect_iterations}",
            f"checkpoint_count={self.checkpoint_count}",
            f"latest_checkpoint={self.latest_checkpoint_label or 'n/a'}",
        ]
        if self.latest_checkpoint_note:
            lines.append(f"latest_checkpoint_note={self.latest_checkpoint_note}")
        return "\n".join(lines) + "\n"


def process_summary(memory_store: WorkspaceMemoryStore, process_id: int | None = None, now: str | None = None) -> ProcessSummary | None:
    metrics = memory_store.process_metrics(process_id=process_id, now=now)
    if metrics is None:
        return None
    process = metrics["process"]
    assert isinstance(process, dict)
    return ProcessSummary(
        process_id=int(metrics["process_id"]),
        label=str(process["label"]),
        objective=str(process["objective"]),
        started_at=str(process["started_at"]),
        ended_at=str(metrics["window_end"]),
        duration_seconds=float(metrics["duration_seconds"]),
        batch_count=int(metrics["batch_count"]),
        delegations=int(metrics["delegations"]),
        defect_iterations=int(metrics["defect_iterations"]),
        checkpoint_count=int(metrics["checkpoint_count"]),
        latest_checkpoint_label=str(metrics["latest_checkpoint"]["label"]) if metrics["latest_checkpoint"] else None,
        latest_checkpoint_note=str(metrics["latest_checkpoint"]["note"]) if metrics["latest_checkpoint"] and metrics["latest_checkpoint"]["note"] else None,
    )


def _build_report(data: dict[str, object]) -> BatchReport:
    batch = data["batch"]
    assert isinstance(batch, dict)
    return BatchReport(
        batch_id=int(data["batch_id"]),
        label=str(batch["label"]),
        objective=str(batch["objective"]),
        started_at=str(batch["started_at"]),
        ended_at=str(data["window_end"]),
        duration_seconds=float(data["duration_seconds"]),
        delegations=int(data["delegations"]),
        defect_iterations=int(data["defect_iterations"]),
        task_success_count=int(data["task_success_count"]),
        task_failure_count=int(data["task_failure_count"]),
        task_partial_count=int(data["task_partial_count"]),
        conversation_turns=int(data["conversation_turns"]),
    )


def _build_process_report(memory_store: WorkspaceMemoryStore, process_id: int, now: str | None = None) -> ProcessSummary | None:
    metrics = memory_store.process_metrics(process_id=process_id, now=now)
    if metrics is None:
        return None
    process = metrics["process"]
    assert isinstance(process, dict)
    return ProcessSummary(
        process_id=int(metrics["process_id"]),
        label=str(process["label"]),
        objective=str(process["objective"]),
        started_at=str(process["started_at"]),
        ended_at=str(metrics["window_end"]),
        duration_seconds=float(metrics["duration_seconds"]),
        batch_count=int(metrics["batch_count"]),
        delegations=int(metrics["delegations"]),
        defect_iterations=int(metrics["defect_iterations"]),
        checkpoint_count=int(metrics["checkpoint_count"]),
        latest_checkpoint_label=str(metrics["latest_checkpoint"]["label"]) if metrics["latest_checkpoint"] else None,
        latest_checkpoint_note=str(metrics["latest_checkpoint"]["note"]) if metrics["latest_checkpoint"] and metrics["latest_checkpoint"]["note"] else None,
    )


def _format_duration(seconds: float) -> str:
    return str(timedelta(seconds=max(0, seconds)))


def _span_seconds(started_at: str, ended_at: str) -> float:
    start = datetime.fromisoformat(started_at)
    end = datetime.fromisoformat(ended_at)
    return max(0.0, (end - start).total_seconds())


def _earliest_timestamp(existing: str | None, candidate: str) -> str:
    if existing is None:
        return candidate
    return candidate if datetime.fromisoformat(candidate) < datetime.fromisoformat(existing) else existing


def _latest_timestamp(existing: str | None, candidate: str) -> str:
    if existing is None:
        return candidate
    return candidate if datetime.fromisoformat(candidate) > datetime.fromisoformat(existing) else existing

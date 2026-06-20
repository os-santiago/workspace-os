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

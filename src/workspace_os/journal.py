from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

from workspace_os.config import Source
from workspace_os.git_status import inspect_source
from workspace_os.memory import WorkspaceMemoryStore


@dataclass(frozen=True)
class JournalSourceMetrics:
    source_name: str
    path: str
    branch: str | None
    commits: int
    lines_added: int
    lines_deleted: int
    files_changed: int
    tags: int
    release_tags: int


@dataclass(frozen=True)
class JournalFunctionalMetrics:
    task_success_count: int
    task_failure_count: int
    task_partial_count: int
    defect_iterations: int
    positive_feedback: int
    questionable_feedback: int
    over_expectation_feedback: int
    decision_total: int
    plan_coverage_hints: tuple[str, ...] = ()  # Product plan items potentially addressed


@dataclass(frozen=True)
class JournalEntry:
    entry_id: str
    cycle_id: int
    label: str
    objective: str
    started_at: str
    ended_at: str
    duration_seconds: float
    checkpoint_count: int
    checkpoints_passed: int
    checkpoints_failed: int
    logical_duration_seconds: float
    wall_clock_duration_seconds: float
    sleep_duration_seconds: float
    logical_active_duration_seconds: float
    wall_clock_active_duration_seconds: float
    idle_ratio: float
    delegation_count: int
    agent_active_duration_seconds: float
    checkpoints: tuple[dict[str, object], ...]
    source_metrics: tuple[JournalSourceMetrics, ...]
    functional_metrics: JournalFunctionalMetrics
    story_lines: tuple[str, ...]
    entry_path: Path

    def render(self) -> str:
        lines = [f"Journal entry: {self.label}"]
        lines.append(f"entry_id={self.entry_id}")
        lines.append(f"cycle_id={self.cycle_id}")
        lines.append(f"objective={self.objective}")
        lines.append(f"started_at={self.started_at}")
        lines.append(f"ended_at={self.ended_at}")
        lines.append(f"logical_duration={_format_duration(self.logical_duration_seconds)}")
        lines.append(f"wall_clock_duration={_format_duration(self.wall_clock_duration_seconds)}")
        lines.append(f"sleep_duration={_format_duration(self.sleep_duration_seconds)}")
        lines.append(f"logical_active_duration={_format_duration(self.logical_active_duration_seconds)}")
        lines.append(f"wall_clock_active_duration={_format_duration(self.wall_clock_active_duration_seconds)}")
        lines.append(f"idle_ratio={self.idle_ratio:.2f}")
        lines.append(f"delegation_count={self.delegation_count}")
        lines.append(f"agent_active_duration={_format_duration(self.agent_active_duration_seconds)}")
        lines.append(f"checkpoint_count={self.checkpoint_count}")
        lines.append(f"checkpoints_passed={self.checkpoints_passed}")
        lines.append(f"checkpoints_failed={self.checkpoints_failed}")
        if self.source_metrics:
            lines.append("Source metrics:")
            for metric in self.source_metrics:
                lines.append(
                    f"- {metric.source_name}: commits={metric.commits} "
                    f"lines_added={metric.lines_added} lines_deleted={metric.lines_deleted} "
                    f"files_changed={metric.files_changed} tags={metric.tags} release_tags={metric.release_tags}"
                )
        lines.append("Functional metrics:")
        lines.append(f"- task_success_count={self.functional_metrics.task_success_count}")
        lines.append(f"- task_failure_count={self.functional_metrics.task_failure_count}")
        lines.append(f"- task_partial_count={self.functional_metrics.task_partial_count}")
        lines.append(f"- defect_iterations={self.functional_metrics.defect_iterations}")
        lines.append(f"- positive_feedback={self.functional_metrics.positive_feedback}")
        lines.append(f"- questionable_feedback={self.functional_metrics.questionable_feedback}")
        lines.append(f"- over_expectation_feedback={self.functional_metrics.over_expectation_feedback}")
        lines.append(f"- decision_total={self.functional_metrics.decision_total}")
        if self.functional_metrics.plan_coverage_hints:
            lines.append("Plan coverage hints:")
            lines.extend(f"- {hint}" for hint in self.functional_metrics.plan_coverage_hints)
        if self.story_lines:
            lines.append("Story:")
            lines.extend(f"- {line}" for line in self.story_lines)
        lines.append(f"journal_path={self.entry_path}")
        return "\n".join(lines) + "\n"


def journal_root(memory_store: WorkspaceMemoryStore) -> Path:
    return memory_store.path.parent / "journal"


def write_cycle_journal(
    memory_store: WorkspaceMemoryStore,
    sources: Iterable[Source],
    cycle: dict[str, object],
    checkpoints: Iterable[dict[str, object]],
    story_title: str = "cycle",
    logical_duration_seconds: float | None = None,
    wall_clock_duration_seconds: float | None = None,
    sleep_duration_seconds: float | None = None,
    logical_active_duration_seconds: float | None = None,
    wall_clock_active_duration_seconds: float | None = None,
    idle_ratio: float | None = None,
    delegation_count: int | None = None,
    agent_active_duration_seconds: float | None = None,
) -> JournalEntry:
    cycle_id = int(cycle["id"])
    entry_id = _entry_id(str(cycle["started_at"]), story_title, cycle_id)
    entry_path = journal_root(memory_store) / "cycles" / entry_id
    checkpoints = tuple(sorted(checkpoints, key=lambda item: int(item["iteration_number"])))
    source_metrics = tuple(_collect_source_metrics(sources, str(cycle["started_at"]), str(cycle["ended_at"] or _utc_now())))
    plan_coverage = detect_plan_coverage_from_commits(sources, str(cycle["started_at"]), str(cycle["ended_at"] or _utc_now()))
    functional_metrics = _collect_functional_metrics(memory_store, plan_coverage_hints=plan_coverage)
    checkpoints_passed = sum(
        1 for checkpoint in checkpoints if all(int(checkpoint.get(f"{name}_ok", 0)) for name in ("health", "stability", "security", "quality"))
    )
    checkpoints_failed = len(checkpoints) - checkpoints_passed
    duration_seconds = _duration_seconds(str(cycle["started_at"]), str(cycle["ended_at"] or _utc_now()))
    logical_duration_seconds = duration_seconds if logical_duration_seconds is None else logical_duration_seconds
    wall_clock_duration_seconds = logical_duration_seconds if wall_clock_duration_seconds is None else wall_clock_duration_seconds
    sleep_duration_seconds = 0.0 if sleep_duration_seconds is None else sleep_duration_seconds
    logical_active_duration_seconds = max(0.0, logical_duration_seconds - sleep_duration_seconds) if logical_active_duration_seconds is None else logical_active_duration_seconds
    wall_clock_active_duration_seconds = max(0.0, wall_clock_duration_seconds - sleep_duration_seconds) if wall_clock_active_duration_seconds is None else wall_clock_active_duration_seconds
    idle_ratio = 0.0 if idle_ratio is None else idle_ratio
    delegation_count = len(checkpoints) if delegation_count is None else delegation_count
    agent_active_duration_seconds = 0.0 if agent_active_duration_seconds is None else agent_active_duration_seconds
    story_lines = _build_story_lines(
        cycle,
        checkpoints,
        source_metrics,
        functional_metrics,
        logical_duration_seconds,
        wall_clock_duration_seconds,
        sleep_duration_seconds,
        logical_active_duration_seconds,
        wall_clock_active_duration_seconds,
        idle_ratio,
        delegation_count,
        agent_active_duration_seconds,
    )
    entry = JournalEntry(
        entry_id=entry_id,
        cycle_id=cycle_id,
        label=str(cycle["label"]),
        objective=str(cycle["objective"]),
        started_at=str(cycle["started_at"]),
        ended_at=str(cycle["ended_at"] or _utc_now()),
        duration_seconds=duration_seconds,
        checkpoint_count=len(checkpoints),
        checkpoints_passed=checkpoints_passed,
        checkpoints_failed=checkpoints_failed,
        logical_duration_seconds=logical_duration_seconds,
        wall_clock_duration_seconds=wall_clock_duration_seconds,
        sleep_duration_seconds=sleep_duration_seconds,
        logical_active_duration_seconds=logical_active_duration_seconds,
        wall_clock_active_duration_seconds=wall_clock_active_duration_seconds,
        idle_ratio=idle_ratio,
        delegation_count=delegation_count,
        agent_active_duration_seconds=agent_active_duration_seconds,
        checkpoints=checkpoints,
        source_metrics=source_metrics,
        functional_metrics=functional_metrics,
        story_lines=story_lines,
        entry_path=entry_path,
    )
    _persist_entry(entry, checkpoints)
    return entry


def list_journal_entries(memory_store: WorkspaceMemoryStore, limit: int = 10) -> list[JournalEntry]:
    root = journal_root(memory_store) / "cycles"
    if not root.exists():
        return []
    entries: list[JournalEntry] = []
    for entry_dir in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        metrics_path = entry_dir / "journal.json"
        if not metrics_path.exists():
            continue
        try:
            entries.append(_load_entry(entry_dir))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        if len(entries) >= limit:
            break
    return entries


def latest_journal_entry(memory_store: WorkspaceMemoryStore) -> JournalEntry | None:
    entries = list_journal_entries(memory_store, limit=1)
    return entries[0] if entries else None


def _persist_entry(entry: JournalEntry, checkpoints: Iterable[dict[str, object]]) -> None:
    entry.entry_path.mkdir(parents=True, exist_ok=True)
    (entry.entry_path / "checkpoints").mkdir(parents=True, exist_ok=True)
    payload = {
        "entry_id": entry.entry_id,
        "cycle_id": entry.cycle_id,
        "label": entry.label,
        "objective": entry.objective,
        "started_at": entry.started_at,
        "ended_at": entry.ended_at,
        "duration_seconds": entry.duration_seconds,
        "logical_duration_seconds": entry.logical_duration_seconds,
        "wall_clock_duration_seconds": entry.wall_clock_duration_seconds,
        "sleep_duration_seconds": entry.sleep_duration_seconds,
        "logical_active_duration_seconds": entry.logical_active_duration_seconds,
        "wall_clock_active_duration_seconds": entry.wall_clock_active_duration_seconds,
        "idle_ratio": entry.idle_ratio,
        "delegation_count": entry.delegation_count,
        "agent_active_duration_seconds": entry.agent_active_duration_seconds,
        "checkpoint_count": entry.checkpoint_count,
        "checkpoints_passed": entry.checkpoints_passed,
        "checkpoints_failed": entry.checkpoints_failed,
        "source_metrics": [metric.__dict__ for metric in entry.source_metrics],
        "functional_metrics": entry.functional_metrics.__dict__,
        "story_lines": list(entry.story_lines),
    }
    (entry.entry_path / "journal.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (entry.entry_path / "journal.md").write_text(_render_markdown(entry), encoding="utf-8")
    for checkpoint in checkpoints:
        checkpoint_id = int(checkpoint["iteration_number"])
        checkpoint_path = entry.entry_path / "checkpoints" / f"{checkpoint_id:03d}.json"
        checkpoint_story = _checkpoint_story(entry, checkpoint)
        checkpoint_payload = {
            "entry_id": entry.entry_id,
            "cycle_id": entry.cycle_id,
            "iteration_number": checkpoint_id,
            "label": checkpoint.get("label"),
            "note": checkpoint.get("note"),
            "created_at": checkpoint.get("created_at"),
            "health_ok": int(checkpoint.get("health_ok", 0)),
            "stability_ok": int(checkpoint.get("stability_ok", 0)),
            "security_ok": int(checkpoint.get("security_ok", 0)),
            "quality_ok": int(checkpoint.get("quality_ok", 0)),
            "story": checkpoint_story,
        }
        checkpoint_path.write_text(json.dumps(checkpoint_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        checkpoint_path.with_suffix(".md").write_text(checkpoint_story, encoding="utf-8")


def _load_entry(entry_dir: Path) -> JournalEntry:
    payload = json.loads((entry_dir / "journal.json").read_text(encoding="utf-8"))
    source_metrics = tuple(JournalSourceMetrics(**metric) for metric in payload.get("source_metrics", []))
    functional_metrics = JournalFunctionalMetrics(**payload["functional_metrics"])
    return JournalEntry(
        entry_id=str(payload["entry_id"]),
        cycle_id=int(payload["cycle_id"]),
        label=str(payload["label"]),
        objective=str(payload["objective"]),
        started_at=str(payload["started_at"]),
        ended_at=str(payload["ended_at"]),
        duration_seconds=float(payload["duration_seconds"]),
        checkpoint_count=int(payload["checkpoint_count"]),
        checkpoints_passed=int(payload["checkpoints_passed"]),
        checkpoints_failed=int(payload["checkpoints_failed"]),
        logical_duration_seconds=float(payload.get("logical_duration_seconds", payload["duration_seconds"])),
        wall_clock_duration_seconds=float(payload.get("wall_clock_duration_seconds", payload["duration_seconds"])),
        sleep_duration_seconds=float(payload.get("sleep_duration_seconds", 0.0)),
        logical_active_duration_seconds=float(payload.get("logical_active_duration_seconds", 0.0)),
        wall_clock_active_duration_seconds=float(payload.get("wall_clock_active_duration_seconds", 0.0)),
        idle_ratio=float(payload.get("idle_ratio", 0.0)),
        delegation_count=int(payload.get("delegation_count", 0)),
        agent_active_duration_seconds=float(payload.get("agent_active_duration_seconds", 0.0)),
        checkpoints=tuple(),
        source_metrics=source_metrics,
        functional_metrics=functional_metrics,
        story_lines=tuple(payload.get("story_lines", [])),
        entry_path=entry_dir,
    )


def _collect_functional_metrics(
    memory_store: WorkspaceMemoryStore,
    plan_coverage_hints: tuple[str, ...] = (),
) -> JournalFunctionalMetrics:
    task_metrics = memory_store.task_outcome_metrics()
    success_count = 0
    failure_count = 0
    partial_count = 0
    for row in task_metrics:
        success_count += int(row["success_count"])
        failure_count += int(row["failure_count"])
        partial_count += int(row["partial_count"])
    feedback_metrics = memory_store.feedback_metrics()
    decision_summary = memory_store.decision_metrics_summary(limit=1000)
    return JournalFunctionalMetrics(
        task_success_count=success_count,
        task_failure_count=failure_count,
        task_partial_count=partial_count,
        defect_iterations=failure_count + partial_count,
        positive_feedback=int(feedback_metrics["positive_count"]),
        questionable_feedback=int(feedback_metrics["questionable_count"]),
        over_expectation_feedback=int(feedback_metrics["over_expectation_count"]),
        decision_total=int(decision_summary["total"]),
        plan_coverage_hints=plan_coverage_hints,
    )


def _collect_source_metrics(
    sources: Iterable[Source],
    started_at: str,
    ended_at: str,
) -> list[JournalSourceMetrics]:
    metrics: list[JournalSourceMetrics] = []
    for source in sources:
        status = inspect_source(source)
        if not status.is_git_repo or not source.path.exists():
            continue
        commits = _git_commit_count(source.path, started_at, ended_at)
        lines_added, lines_deleted, files_changed = _git_numstat_totals(source.path, started_at, ended_at)
        tags = _git_tag_count(source.path)
        release_tags = _git_release_tag_count(source.path)
        metrics.append(
            JournalSourceMetrics(
                source_name=source.name,
                path=str(source.path),
                branch=status.branch,
                commits=commits,
                lines_added=lines_added,
                lines_deleted=lines_deleted,
                files_changed=files_changed,
                tags=tags,
                release_tags=release_tags,
            )
        )
    return metrics


def _git_commit_count(path: Path, started_at: str, ended_at: str) -> int:
    return _run_git_count(path, "rev-list", "--count", f"--since={started_at}", f"--until={ended_at}", "HEAD")


def _git_numstat_totals(path: Path, started_at: str, ended_at: str) -> tuple[int, int, int]:
    completed = _run_git(
        path,
        "log",
        f"--since={started_at}",
        f"--until={ended_at}",
        "--numstat",
        "--pretty=tformat:",
    )
    added = 0
    deleted = 0
    files = 0
    for line in completed.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        try:
            line_added = int(parts[0]) if parts[0] != "-" else 0
            line_deleted = int(parts[1]) if parts[1] != "-" else 0
        except ValueError:
            continue
        added += line_added
        deleted += line_deleted
        files += 1
    return added, deleted, files


def _git_tag_count(path: Path) -> int:
    completed = _run_git(path, "tag", "--list")
    return len([line for line in completed.splitlines() if line.strip()])


def _git_release_tag_count(path: Path) -> int:
    completed = _run_git(path, "for-each-ref", "refs/tags", "--format=%(refname:strip=2) %(creatordate:short)")
    count = 0
    for line in completed.splitlines():
        name = line.split(" ", 1)[0].strip()
        if _looks_like_release_tag(name):
            count += 1
    return count


def _looks_like_release_tag(tag: str) -> bool:
    return bool(re.match(r"^v?\d+\.\d+\.\d+", tag))


def _build_story_lines(
    cycle: dict[str, object],
    checkpoints: Iterable[dict[str, object]],
    source_metrics: Iterable[JournalSourceMetrics],
    functional_metrics: JournalFunctionalMetrics,
    logical_duration_seconds: float,
    wall_clock_duration_seconds: float,
    sleep_duration_seconds: float,
    logical_active_duration_seconds: float,
    wall_clock_active_duration_seconds: float,
    idle_ratio: float,
    delegation_count: int,
    agent_active_duration_seconds: float,
) -> tuple[str, ...]:
    lines = [
        f"The cycle '{cycle['label']}' stayed alive for {_format_duration(logical_duration_seconds)} logical time and delivered {len(tuple(checkpoints))} checkpoints.",
    ]
    lines.append(
        f"Wall clock time was {_format_duration(wall_clock_duration_seconds)} with {_format_duration(sleep_duration_seconds)} spent waiting between checkpoints."
    )
    lines.append(
        f"Active work measured {_format_duration(logical_active_duration_seconds)} logically and {_format_duration(wall_clock_active_duration_seconds)} against the live wall clock."
    )
    lines.append(f"Idle ratio stayed at {idle_ratio:.2f} across the window.")
    lines.append(
        f"Delegations issued: {delegation_count}; agent active duration: {_format_duration(agent_active_duration_seconds)}."
    )
    if source_metrics:
        total_commits = sum(metric.commits for metric in source_metrics)
        total_lines = sum(metric.lines_added + metric.lines_deleted for metric in source_metrics)
        lines.append(
            f"The workspace moved code in {total_commits} commits across {len(tuple(source_metrics))} repositories, with {total_lines} changed lines."
        )
    lines.append(
        f"Functional movement closed {functional_metrics.task_success_count} successful outcomes while keeping defect iterations at {functional_metrics.defect_iterations}."
    )
    lines.append(
        f"Feedback stayed grounded in {functional_metrics.questionable_feedback} questionable signals and {functional_metrics.over_expectation_feedback} positive boosts."
    )
    lines.append("The cycle journal captured the run as a narrative so the next window can continue without re-explaining the same intent.")
    return tuple(lines)


def _checkpoint_story(entry: JournalEntry, checkpoint: dict[str, object]) -> str:
    iteration = int(checkpoint.get("iteration_number", 0))
    label = str(checkpoint.get("label", f"iteration-{iteration}"))
    health = "green" if int(checkpoint.get("health_ok", 0)) else "red"
    stability = "green" if int(checkpoint.get("stability_ok", 0)) else "red"
    security = "green" if int(checkpoint.get("security_ok", 0)) else "red"
    quality = "green" if int(checkpoint.get("quality_ok", 0)) else "red"
    return (
        f"Checkpoint {iteration} ({label}) held the line: "
        f"health={health}, stability={stability}, security={security}, quality={quality}. "
        f"The journal keeps this moment in the sequence for later analysis."
    )


def _render_markdown(entry: JournalEntry) -> str:
    lines = [
        f"# Journal: {entry.label}",
        "",
        f"- Cycle ID: {entry.cycle_id}",
        f"- Objective: {entry.objective}",
        f"- Started: {entry.started_at}",
        f"- Ended: {entry.ended_at}",
        f"- Logical duration: {_format_duration(entry.logical_duration_seconds)}",
        f"- Wall clock duration: {_format_duration(entry.wall_clock_duration_seconds)}",
        f"- Sleep duration: {_format_duration(entry.sleep_duration_seconds)}",
        f"- Active duration (logical): {_format_duration(entry.logical_active_duration_seconds)}",
        f"- Active duration (wall clock): {_format_duration(entry.wall_clock_active_duration_seconds)}",
        f"- Idle ratio: {entry.idle_ratio:.2f}",
        f"- Delegation count: {entry.delegation_count}",
        f"- Agent active duration: {_format_duration(entry.agent_active_duration_seconds)}",
        f"- Checkpoints: {entry.checkpoint_count}",
        f"- Checkpoints passed: {entry.checkpoints_passed}",
        f"- Checkpoints failed: {entry.checkpoints_failed}",
        "",
        "## Story",
    ]
    lines.extend(f"- {line}" for line in entry.story_lines)
    lines.extend(["", "## Code"])
    for metric in entry.source_metrics:
        lines.append(
            f"- {metric.source_name}: commits={metric.commits} lines_added={metric.lines_added} "
            f"lines_deleted={metric.lines_deleted} files_changed={metric.files_changed} tags={metric.tags} release_tags={metric.release_tags}"
        )
    lines.extend(
        [
            "",
            "## Function",
            f"- task_success_count={entry.functional_metrics.task_success_count}",
            f"- task_failure_count={entry.functional_metrics.task_failure_count}",
            f"- task_partial_count={entry.functional_metrics.task_partial_count}",
            f"- defect_iterations={entry.functional_metrics.defect_iterations}",
            f"- positive_feedback={entry.functional_metrics.positive_feedback}",
            f"- questionable_feedback={entry.functional_metrics.questionable_feedback}",
            f"- over_expectation_feedback={entry.functional_metrics.over_expectation_feedback}",
            f"- decision_total={entry.functional_metrics.decision_total}",
        ]
    )
    return "\n".join(lines) + "\n"


def _entry_id(started_at: str, label: str, cycle_id: int) -> str:
    compact = started_at.replace(":", "").replace("-", "").replace("+", "").replace(".", "")
    slug = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")
    return f"{compact}-cycle-{cycle_id}-{slug}"


def _run_git(path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def _run_git_count(path: Path, *args: str) -> int:
    try:
        output = _run_git(path, *args).strip()
    except subprocess.CalledProcessError:
        return 0
    try:
        return int(output or 0)
    except ValueError:
        return 0


def _duration_seconds(started_at: str, ended_at: str) -> float:
    start = datetime.fromisoformat(started_at)
    end = datetime.fromisoformat(ended_at)
    return max(0.0, (end - start).total_seconds())


def _format_duration(seconds: float) -> str:
    from datetime import timedelta

    return str(timedelta(seconds=max(0.0, seconds)))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_plan_coverage_from_commits(sources: Iterable[Source], since: str, until: str) -> tuple[str, ...]:
    """Detect which product plan items might have been addressed based on commit messages.

    Scans commit messages for keywords related to product plan competencies and gaps.
    Returns hints about potentially addressed plan items for gap analysis.
    """
    plan_keywords = {
        "workspace discovery": ["workspace", "repo", "resolution", "discovery"],
        "agent orchestration": ["agent", "routing", "delegation", "orchestration"],
        "context compaction": ["context", "memory", "compaction", "snapshot"],
        "parallel execution": ["parallel", "concurrent", "cross-check"],
        "learning": ["learning", "feedback", "mastery", "preference"],
        "cycle orchestration": ["cycle", "checkpoint", "long-run", "iteration"],
        "traceability": ["trace", "handoff", "recovery", "journal"],
    }

    coverage_hints = set()
    for source in sources:
        if source.type != "repository":
            continue
        try:
            result = subprocess.run(
                ["git", "log", f"--since={since}", f"--until={until}", "--pretty=format:%s"],
                cwd=source.path,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                commits = result.stdout.lower()
                for plan_item, keywords in plan_keywords.items():
                    if any(kw in commits for kw in keywords):
                        coverage_hints.add(plan_item)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return tuple(sorted(coverage_hints))

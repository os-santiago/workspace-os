from __future__ import annotations

from dataclasses import dataclass

from workspace_os.batch import current_batch_report, current_process_report
from workspace_os.git_status import inspect_source
from workspace_os.habits import compute_habits
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.profile import load_profile


@dataclass(frozen=True)
class WorkspaceOverview:
    workspace: str
    source_lines: tuple[str, ...]
    memory_lines: tuple[str, ...]
    profile_lines: tuple[str, ...]
    habit_lines: tuple[str, ...]
    process_lines: tuple[str, ...]
    batch_lines: tuple[str, ...]
    launch_lines: tuple[str, ...]

    def render(self) -> str:
        lines = [f"Workspace overview: {self.workspace}"]
        sections = (
            self.source_lines,
            self.memory_lines,
            self.profile_lines,
            self.habit_lines,
            self.process_lines,
            self.batch_lines,
            self.launch_lines,
        )
        for section in sections:
            if not section:
                continue
            lines.append("")
            lines.extend(section)
        return "\n".join(lines) + "\n"


def build_workspace_overview(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    launch_limit: int = 5,
) -> WorkspaceOverview:
    profile = load_profile(memory_store)
    habits = compute_habits(memory_store, profile)
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    stats = memory_store.stats()

    source_lines = tuple(_render_source_lines(sources))
    memory_lines = (
        f"Memory: preferences={stats['operator_preferences']} lessons={stats['reusable_lessons']} "
        f"outcomes={stats['task_outcomes']} decisions={stats['decision_log']} turns={stats['conversation_turns']} "
        f"launches={stats['agent_launches']}",
    )
    profile_lines = (
        "Profile:",
        f"- tone={profile.tone} detail={profile.detail_level} default_workspace={profile.default_workspace or 'n/a'}",
        f"- shortcuts={len(profile.shortcuts or {})}",
    )
    habit_lines = (
        "Habits:",
        f"- {habits.render_summary()}",
    )
    process_lines = _render_process_lines(process)
    batch_lines = _render_batch_lines(batch)
    launch_lines = _render_launch_lines(memory_store.recent_launches(limit=launch_limit))

    return WorkspaceOverview(
        workspace=workspace or profile.default_workspace or "all workspaces",
        source_lines=source_lines,
        memory_lines=memory_lines,
        profile_lines=profile_lines,
        habit_lines=habit_lines,
        process_lines=process_lines,
        batch_lines=batch_lines,
        launch_lines=launch_lines,
    )


def _render_source_lines(sources) -> list[str]:
    lines = ["Sources:"]
    for status in [inspect_source(source) for source in sources]:
        source = status.source
        if status.state == "missing":
            lines.append(f"- {source.name}: missing ({source.path})")
            continue
        if status.state == "not-git":
            lines.append(f"- {source.name}: not-git ({source.path})")
            continue
        if status.state == "error":
            lines.append(f"- {source.name}: error ({status.error})")
            continue

        divergence = ""
        if status.ahead or status.behind:
            divergence = f" ahead={status.ahead} behind={status.behind}"
        lines.append(
            f"- {source.name}: {status.state} branch={status.branch} changes={status.dirty_count} "
            f"untracked={status.untracked_count}{divergence}"
        )
    return lines


def _render_process_lines(process) -> tuple[str, ...]:
    if process is None:
        return ("Process: none",)
    lines = [
        "Process:",
        f"- {process.label}: objective={process.objective} duration={process.duration_seconds}s "
        f"batches={process.batch_count} checkpoints={process.checkpoint_count}",
    ]
    if process.latest_checkpoint_label:
        note = f" ({process.latest_checkpoint_note})" if process.latest_checkpoint_note else ""
        lines.append(f"- latest_checkpoint={process.latest_checkpoint_label}{note}")
    return tuple(lines)


def _render_batch_lines(batch) -> tuple[str, ...]:
    if batch is None:
        return ("Batch: none",)
    return (
        "Batch:",
        f"- {batch.label}: objective={batch.objective} duration={batch.duration_seconds}s "
        f"delegations={batch.delegations} defects={batch.defect_iterations}",
    )


def _render_launch_lines(launches) -> tuple[str, ...]:
    if not launches:
        return ("Recent launches: none",)
    lines = ["Recent launches:"]
    for launch in launches:
        workspace = launch["workspace"] or "all"
        lines.append(f"- {launch['agent']} {workspace}: {launch['task']} ({launch['launched_at']})")
    return tuple(lines)

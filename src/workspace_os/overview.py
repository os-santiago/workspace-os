from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workspace_os.batch import current_batch_report, current_process_report
from workspace_os.delegation import build_agent_route_command
from workspace_os.learning import build_workspace_learning_model
from workspace_os.git_status import inspect_source, recent_source_activities
from workspace_os.habits import compute_habits
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.profile import load_profile


@dataclass(frozen=True)
class WorkspaceOverview:
    workspace: str
    source_lines: tuple[str, ...]
    memory_lines: tuple[str, ...]
    context_lines: tuple[str, ...]
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
            self.context_lines,
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


@dataclass(frozen=True)
class WorkspaceHandoff:
    workspace: str
    summary_lines: tuple[str, ...]
    next_step_lines: tuple[str, ...]

    def render(self) -> str:
        lines = [f"Workspace handoff: {self.workspace}"]
        if self.summary_lines:
            lines.append("")
            lines.extend(self.summary_lines)
        if self.next_step_lines:
            lines.append("")
            lines.extend(self.next_step_lines)
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class WorkspaceContextSnapshot:
    workspace: str
    reason: str
    summary_lines: tuple[str, ...]
    next_step_lines: tuple[str, ...]

    def render(self) -> str:
        lines = [f"Workspace context snapshot: {self.workspace}", f"Reason: {self.reason}"]
        if self.summary_lines:
            lines.append("")
            lines.extend(self.summary_lines)
        if self.next_step_lines:
            lines.append("")
            lines.extend(self.next_step_lines)
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class WorkspaceNextAction:
    workspace: str
    summary_lines: tuple[str, ...]
    action_lines: tuple[str, ...]

    def render(self) -> str:
        lines = [f"Workspace next action: {self.workspace}"]
        if self.summary_lines:
            lines.append("")
            lines.extend(self.summary_lines)
        if self.action_lines:
            lines.append("")
            lines.extend(self.action_lines)
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class WorkspaceAnalysis:
    workspace: str
    source_lines: tuple[str, ...]
    recommendation_lines: tuple[str, ...]

    def render(self) -> str:
        lines = [f"Workspace analysis: {self.workspace}"]
        if self.source_lines:
            lines.append("")
            lines.extend(self.source_lines)
        if self.recommendation_lines:
            lines.append("")
            lines.extend(self.recommendation_lines)
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class WorkspaceRoots:
    workspace: str
    workspace_root: str
    knowledge_base_root: str
    workspace_lines: tuple[str, ...]
    knowledge_base_lines: tuple[str, ...]
    recommendation_lines: tuple[str, ...]

    def render(self) -> str:
        lines = [f"Workspace roots: {self.workspace}", f"Workspace root: {self.workspace_root}", f"Knowledge base root: {self.knowledge_base_root}"]
        if self.workspace_lines:
            lines.append("")
            lines.append("Workspace repos:")
            lines.extend(self.workspace_lines)
        if self.knowledge_base_lines:
            lines.append("")
            lines.append("Knowledge base repos:")
            lines.extend(self.knowledge_base_lines)
        if self.recommendation_lines:
            lines.append("")
            lines.extend(self.recommendation_lines)
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class WorkspaceContinuationRecommendation:
    target_workspace: str | None
    reason: str
    primary_command: str
    parallel_recommended: bool
    parallel_command: str | None
    lines: tuple[str, ...]


def build_workspace_overview(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    launch_limit: int = 5,
    compact: bool = False,
) -> WorkspaceOverview:
    profile = load_profile(memory_store)
    habits = compute_habits(memory_store, profile)
    learning_model = build_workspace_learning_model(memory_store, profile)
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    stats = memory_store.stats()
    context_snapshot = memory_store.latest_context_snapshot()

    source_lines = tuple(_render_source_lines(sources, compact=compact))
    memory_lines = _render_memory_lines(stats, compact=compact)
    context_lines = _render_context_lines(context_snapshot, compact=compact)
    profile_lines = _render_profile_lines(profile, compact=compact)
    habit_lines = _render_habit_lines(habits, compact=compact)
    process_lines = _render_process_lines(process, compact=compact)
    batch_lines = _render_batch_lines(batch, compact=compact)
    launch_lines = _render_launch_lines(memory_store.recent_launches(limit=launch_limit), compact=compact)

    return WorkspaceOverview(
        workspace=workspace or profile.default_workspace or "all workspaces",
        source_lines=source_lines,
        memory_lines=memory_lines,
        context_lines=context_lines,
        profile_lines=profile_lines,
        habit_lines=habit_lines,
        process_lines=process_lines,
        batch_lines=batch_lines,
        launch_lines=launch_lines,
    )


def build_workspace_handoff(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    launch_limit: int = 3,
    compact: bool = False,
) -> WorkspaceHandoff:
    overview = build_workspace_overview(
        sources,
        memory_store,
        workspace=workspace,
        launch_limit=launch_limit,
        compact=compact,
    )
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    stats = memory_store.stats()
    profile_summary = _profile_summary_text(overview.profile_lines)
    habit_summary = _habit_summary_text(overview.habit_lines)
    context_summary = _context_summary_text(overview.context_lines)

    summary_lines = (
        f"State: sources={len(sources)} memory_entries={stats['conversation_turns']} turns "
        f"launches={stats['agent_launches']} habits_ready=yes",
        f"Profile: {profile_summary}",
        f"Habits: {habit_summary}",
        f"Context: {context_summary}",
        _summary_line("Process", process),
        _summary_line("Batch", batch),
    )
    next_step_lines = ("Next:", _next_step(process, batch))
    return WorkspaceHandoff(
        workspace=overview.workspace,
        summary_lines=summary_lines,
        next_step_lines=next_step_lines,
    )


def build_workspace_context_snapshot(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    launch_limit: int = 3,
    reason: str = "finalization",
) -> WorkspaceContextSnapshot:
    overview = build_workspace_overview(
        sources,
        memory_store,
        workspace=workspace,
        launch_limit=launch_limit,
        compact=True,
    )
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    summary_lines = (
        f"State: {overview.memory_lines[0].removeprefix('Memory: ')}",
        f"Profile: {_profile_summary_text(overview.profile_lines)}",
        f"Habits: {_habit_summary_text(overview.habit_lines)}",
        _summary_line("Process", process),
        _summary_line("Batch", batch),
    )
    next_step_lines = ("Next:", _next_step(process, batch))
    return WorkspaceContextSnapshot(
        workspace=overview.workspace,
        reason=reason,
        summary_lines=summary_lines,
        next_step_lines=next_step_lines,
    )


def build_workspace_next_action(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
) -> WorkspaceNextAction:
    profile = load_profile(memory_store)
    habits = compute_habits(memory_store, profile)
    learning_model = build_workspace_learning_model(memory_store, profile)
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    stats = memory_store.stats()
    workspace_name = workspace or profile.default_workspace or "all workspaces"
    route_hint = _recommended_route(memory_store, habits.primary_agent)

    summary_lines = (
        f"State: sources={len(sources)} memory_entries={stats['conversation_turns']} turns launches={stats['agent_launches']}",
        f"Profile: tone={profile.tone} detail={profile.detail_level} default_workspace={profile.default_workspace or ''}",
        f"Habits: {habits.render_summary()}",
        _summary_line("Process", process),
        _summary_line("Batch", batch),
    )

    if process is None and batch is None:
        analysis = build_workspace_analysis(sources, memory_store, workspace=workspace_name, limit=5, compact=True)
        action_lines = (
            "Next: review the initial analysis before broad work.",
            f"Primary route={route_hint}",
            f"Suggested command: {_route_command(route_hint, workspace_name)}",
            "Fallback route=/analysis --compact",
            f"Learning model: {learning_model.render_summary()}",
            "Use analysis to pick the repo that changed most recently, then inspect it before delegating.",
            *analysis.recommendation_lines,
        )
    elif process is not None and batch is None:
        action_lines = (
            "Next: start a batch inside the active process.",
            "Suggested command: /batch start <label> <objective>",
            "Use a batch when the process needs a focused execution window.",
        )
    elif process is not None:
        action_lines = (
            "Next: record the next checkpoint or close the process when complete.",
            "Suggested command: /process checkpoint <label> <note>",
            "If the batch is complete, stop the batch and process to persist the handoff.",
        )
    else:
        action_lines = (
            "Next: start a process window before the next batch.",
            "Suggested command: /process start <label> <objective>",
            "Use a process when work is spread across several batches.",
        )

    return WorkspaceNextAction(
        workspace=workspace_name,
        summary_lines=summary_lines,
        action_lines=action_lines,
    )


def build_workspace_analysis(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    limit: int = 5,
    compact: bool = False,
) -> WorkspaceAnalysis:
    profile = load_profile(memory_store)
    workspace_sources = _sources_for_group(sources, "workspace")
    knowledge_sources = _sources_for_group(sources, "knowledge_base")
    workspace_root = _workspace_root_from_sources(workspace_sources)
    knowledge_base_root = _workspace_root_from_sources(knowledge_sources)
    workspace_name = workspace or workspace_root or profile.default_workspace or "all workspaces"
    workspace_activities = recent_source_activities(workspace_sources, limit=limit)
    knowledge_activities = recent_source_activities(knowledge_sources, limit=limit)

    if compact:
        source_lines = (
            f"Workspace root: {workspace_root}",
            f"Knowledge base root: {knowledge_base_root}",
            "Workspace projects under root:",
            *_render_activity_lines(workspace_activities, compact=True),
            "Knowledge base projects:",
            *_render_activity_lines(knowledge_activities, compact=True),
        )
    else:
        source_lines = (
            f"Workspace root: {workspace_root}",
            f"Knowledge base root: {knowledge_base_root}",
            "Workspace projects under root:",
            *_render_activity_lines(workspace_activities, compact=False),
            "Knowledge base projects:",
            *_render_activity_lines(knowledge_activities, compact=False),
        )

    recommendation_lines = _analysis_recommendation_lines(workspace_activities, workspace_name, profile.primary_agent)
    recommendation_lines = recommendation_lines + (f"Learning model: {build_workspace_learning_model(memory_store, profile).render_summary()}",)
    return WorkspaceAnalysis(
        workspace=workspace_name,
        source_lines=source_lines,
        recommendation_lines=recommendation_lines,
    )


def build_workspace_roots(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    limit: int = 5,
) -> WorkspaceRoots:
    profile = load_profile(memory_store)
    workspace_sources = _sources_for_group(sources, "workspace")
    knowledge_sources = _sources_for_group(sources, "knowledge_base")
    workspace_root = _workspace_root_from_sources(workspace_sources)
    knowledge_base_root = _workspace_root_from_sources(knowledge_sources)
    workspace_name = workspace or workspace_root or profile.default_workspace or "all workspaces"
    workspace_activities = recent_source_activities(workspace_sources, limit=limit)
    knowledge_activities = recent_source_activities(knowledge_sources, limit=limit)
    workspace_lines = tuple(_render_activity_lines(workspace_activities, compact=True))
    knowledge_base_lines = tuple(_render_activity_lines(knowledge_activities, compact=True))
    recommendation = _build_workspace_continuation_recommendation(workspace_activities, workspace_name, profile.primary_agent)
    learning_model = build_workspace_learning_model(memory_store, profile)
    return WorkspaceRoots(
        workspace=workspace_name,
        workspace_root=workspace_root,
        knowledge_base_root=knowledge_base_root,
        workspace_lines=workspace_lines,
        knowledge_base_lines=knowledge_base_lines,
        recommendation_lines=recommendation.lines + (f"Learning model: {learning_model.render_summary()}",),
    )


def write_workspace_handoff(
    path: Path,
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    launch_limit: int = 3,
    compact: bool = False,
    prefix: str | None = None,
) -> WorkspaceHandoff:
    content = render_workspace_handoff_text(
        sources,
        memory_store,
        workspace=workspace,
        launch_limit=launch_limit,
        compact=compact,
        prefix=prefix,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return build_workspace_handoff(sources, memory_store, workspace=workspace, launch_limit=launch_limit, compact=compact)


def default_workspace_handoff_path(memory_path: Path) -> Path:
    return memory_path.parent / "handoff.md"


def default_workspace_context_path(memory_path: Path) -> Path:
    return memory_path.parent / "context-global.md"


def write_workspace_context_snapshot(
    path: Path,
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    launch_limit: int = 3,
    reason: str = "finalization",
) -> WorkspaceContextSnapshot:
    snapshot = build_workspace_context_snapshot(
        sources,
        memory_store,
        workspace=workspace,
        launch_limit=launch_limit,
        reason=reason,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.render(), encoding="utf-8")
    return snapshot


def render_latest_workspace_context_text(memory_store: WorkspaceMemoryStore) -> str:
    snapshot = memory_store.latest_context_snapshot()
    if snapshot is None:
        return "No context snapshot found.\n"
    return f"{snapshot['markdown'].rstrip()}\n"


def render_workspace_next_action_text(sources, memory_store: WorkspaceMemoryStore, workspace: str | None = None) -> str:
    next_action = build_workspace_next_action(sources, memory_store, workspace=workspace)
    return next_action.render()


def render_workspace_analysis_text(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    limit: int = 5,
    compact: bool = False,
) -> str:
    analysis = build_workspace_analysis(
        sources,
        memory_store,
        workspace=workspace,
        limit=limit,
        compact=compact,
    )
    return analysis.render()


def render_workspace_roots_text(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    limit: int = 5,
) -> str:
    roots = build_workspace_roots(sources, memory_store, workspace=workspace, limit=limit)
    return roots.render()


def render_workspace_handoff_text(
    sources,
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    launch_limit: int = 3,
    compact: bool = False,
    prefix: str | None = None,
) -> str:
    handoff = build_workspace_handoff(
        sources,
        memory_store,
        workspace=workspace,
        launch_limit=launch_limit,
        compact=compact,
    )
    content = handoff.render()
    if prefix:
        content = f"{prefix.rstrip()}\n\n{content}"
    return content


def _render_source_lines(sources, compact: bool = False) -> list[str]:
    statuses = [inspect_source(source) for source in sources]
    if compact:
        total = len(statuses)
        missing = sum(1 for status in statuses if status.state == "missing")
        not_git = sum(1 for status in statuses if status.state == "not-git")
        error = sum(1 for status in statuses if status.state == "error")
        dirty = sum(1 for status in statuses if status.state == "dirty")
        clean = sum(1 for status in statuses if status.state == "clean")
        return [
            "Sources:",
            f"- total={total} clean={clean} dirty={dirty} missing={missing} not_git={not_git} error={error}",
        ]
    lines = ["Sources:"]
    for status in statuses:
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


def _render_memory_lines(stats: dict[str, int], compact: bool = False) -> tuple[str, ...]:
    line = (
        f"Memory: preferences={stats['operator_preferences']} lessons={stats['reusable_lessons']} "
        f"outcomes={stats['task_outcomes']} decisions={stats['decision_log']} turns={stats['conversation_turns']} "
        f"feedback={stats.get('feedback_events', 0)} launches={stats['agent_launches']} snapshots={stats.get('context_snapshots', 0)}"
    )
    return (line,)


def _render_context_lines(snapshot: dict[str, str | None] | None, compact: bool = False) -> tuple[str, ...]:
    if snapshot is None:
        return ("Context: none",)
    if compact:
        return (
            f"Context: {snapshot['reason']} at {snapshot['created_at']} scope={snapshot['scope']}",
        )
    lines = [
        "Context:",
        f"- scope={snapshot['scope']} reason={snapshot['reason']} created_at={snapshot['created_at']}",
    ]
    if snapshot.get("summary"):
        lines.append(f"- summary={snapshot['summary']}")
    return tuple(lines)


def _render_profile_lines(profile, compact: bool = False) -> tuple[str, ...]:
    if compact:
        return (f"Profile: tone={profile.tone} detail={profile.detail_level} default_workspace={profile.default_workspace or 'n/a'}",)
    return (
        "Profile:",
        f"- tone={profile.tone} detail={profile.detail_level} default_workspace={profile.default_workspace or 'n/a'}",
        f"- shortcuts={len(profile.shortcuts or {})}",
    )


def _render_habit_lines(habits, compact: bool = False) -> tuple[str, ...]:
    summary = habits.render_summary()
    if compact:
        return (f"Habits: {summary}",)
    return ("Habits:", f"- {summary}")


def _render_process_lines(process, compact: bool = False) -> tuple[str, ...]:
    if process is None:
        return ("Process: none",)
    if compact:
        line = f"Process: {process.label} objective={process.objective} duration={process.duration_seconds}s batches={process.batch_count}"
        if process.latest_checkpoint_label:
            line += f" latest={process.latest_checkpoint_label}"
        return (line,)
    lines = [
        "Process:",
        f"- {process.label}: objective={process.objective} duration={process.duration_seconds}s "
        f"batches={process.batch_count} checkpoints={process.checkpoint_count}",
    ]
    if process.latest_checkpoint_label:
        note = f" ({process.latest_checkpoint_note})" if process.latest_checkpoint_note else ""
        lines.append(f"- latest_checkpoint={process.latest_checkpoint_label}{note}")
    return tuple(lines)


def _render_batch_lines(batch, compact: bool = False) -> tuple[str, ...]:
    if batch is None:
        return ("Batch: none",)
    if compact:
        return (f"Batch: {batch.label} objective={batch.objective} duration={batch.duration_seconds}s delegations={batch.delegations} defects={batch.defect_iterations}",)
    return (
        "Batch:",
        f"- {batch.label}: objective={batch.objective} duration={batch.duration_seconds}s "
        f"delegations={batch.delegations} defects={batch.defect_iterations}",
    )


def _render_launch_lines(launches, compact: bool = False) -> tuple[str, ...]:
    if not launches:
        return ("Recent launches: none",)
    if compact:
        first = launches[0]
        workspace = first["workspace"] or "all"
        line = f"Recent launches: {first['agent']} {workspace}: {first['task']} ({first['launched_at']})"
        if len(launches) > 1:
            line += f" +{len(launches) - 1} more"
        return (line,)
    lines = ["Recent launches:"]
    for launch in launches:
        workspace = launch["workspace"] or "all"
        lines.append(f"- {launch['agent']} {workspace}: {launch['task']} ({launch['launched_at']})")
    return tuple(lines)


def _render_activity_lines(activities, compact: bool = False) -> tuple[str, ...]:
    if not activities:
        return ("- no recent repo activity found",)
    lines = []
    for activity in activities:
        status = activity.status
        source = activity.source
        branch = status.branch or "detached"
        if status.state == "missing":
            lines.append(f"- [MISSING] {source.name}: path={source.path}")
            continue
        if status.state == "not-git":
            lines.append(f"- [NOT-GIT] {source.name}: path={source.path}")
            continue
        if status.state == "error":
            lines.append(f"- [ERROR] {source.name}: error={status.error}")
            continue
        if compact:
            lines.append(
                f"- [DEV] {source.name}: updated={activity.updated} branch={branch} "
                f"changes={status.dirty_count} untracked={status.untracked_count}"
            )
            continue
        lines.append(
            f"- [DEV] {source.name}: updated={activity.updated} branch={branch} "
            f"changes={status.dirty_count} untracked={status.untracked_count}"
        )
        if status.ahead or status.behind:
            lines[-1] += f" ahead={status.ahead} behind={status.behind}"
    return tuple(lines)


def _analysis_recommendation_lines(activities, workspace_name: str, preferred_primary_agent: str | None = None) -> tuple[str, ...]:
    route_agent = preferred_primary_agent if preferred_primary_agent in {"opencode", "codex", "claude"} else "opencode"
    if not activities:
        return (
            "Continue with: inspect the workspace first.",
            "Recommended continue: inspect the workspace first.",
            f"Primary route: /{route_agent}",
            "Suggested command: /inspect --compact",
            "No updated repo was available to rank.",
        )
    candidate = activities[0]
    status = candidate.status
    reason = "most recent repo activity"
    if status.state == "dirty":
        reason = "it has uncommitted changes and is likely the active work surface"
    elif status.ahead or status.behind:
        reason = "it is diverged from upstream and likely needs attention"
    return (
        f"Continue with: {candidate.source.name}",
        f"Recommended continue: {candidate.source.name}",
        f"Reason: {reason}",
        f"Primary route: /{route_agent}",
        f"Suggested command: {_route_command(route_agent, candidate.source.name or workspace_name)}",
        f"Optional cross-check: {_route_command('claude', candidate.source.name or workspace_name)}",
    )


def _build_workspace_continuation_recommendation(
    activities,
    workspace_name: str,
    preferred_primary_agent: str | None = None,
) -> WorkspaceContinuationRecommendation:
    primary_agent = preferred_primary_agent if preferred_primary_agent in {"opencode", "codex", "claude"} else "opencode"
    if not activities:
        return WorkspaceContinuationRecommendation(
            target_workspace=None,
            reason="No updated repo was available to rank.",
            primary_command="/inspect --compact",
            parallel_recommended=False,
            parallel_command=None,
            lines=(
                "Continue with: inspect the workspace first.",
                "Reason: No updated repo was available to rank.",
                "Suggested command: /inspect --compact",
                "Parallel review: not needed",
            ),
        )
    candidate = activities[0]
    status = candidate.status
    reason = "most recent repo activity"
    if status.state == "dirty":
        reason = "it has uncommitted changes and is likely the active work surface"
    elif status.ahead or status.behind:
        reason = "it is diverged from upstream and likely needs attention"
    primary_command = _route_command(primary_agent, candidate.source.name or workspace_name)
    parallel_recommended = len(activities) > 1 or status.state == "dirty" or status.ahead or status.behind
    parallel_command = _route_command("claude", candidate.source.name or workspace_name) if parallel_recommended else None
    return WorkspaceContinuationRecommendation(
        target_workspace=candidate.source.name,
        reason=reason,
        primary_command=primary_command,
        parallel_recommended=parallel_recommended,
        parallel_command=parallel_command,
        lines=(
            f"Continue with: {candidate.source.name}",
            f"Reason: {reason}",
            f"Suggested command: {primary_command}",
            f"Parallel review: {primary_agent} + claude" if parallel_recommended else "Parallel review: not needed",
            f"Parallel cross-check: {parallel_command}" if parallel_command else "Parallel cross-check: optional",
        ),
    )


def _summary_line(label: str, item) -> str:
    if item is None:
        return f"{label}: none"
    if label == "Process":
        line = (
            f"{label}: {item.label} objective={item.objective} duration={item.duration_seconds}s "
            f"batches={item.batch_count} checkpoints={item.checkpoint_count}"
        )
        if item.latest_checkpoint_label:
            line += f" latest={item.latest_checkpoint_label}"
        return line
    if label == "Batch":
        return (
            f"{label}: {item.label} objective={item.objective} duration={item.duration_seconds}s "
            f"delegations={item.delegations} defects={item.defect_iterations}"
        )
    return f"{label}: unavailable"


def _next_step(process, batch) -> str:
    if process is not None:
        if process.checkpoint_count == 0:
            return "record the first process checkpoint"
        if batch is None:
            return "start a batch inside the active process"
        return "continue with the next batch checkpoint or close the process when complete"
    if batch is not None:
        return "start or close the process window around the active batch work"
    return "start a new process window before the next batch"


def _compact_habit_summary(line: str) -> str:
    text = line.removeprefix("- ").strip()
    return text.removeprefix("Habits: ").strip() if text.startswith("Habits: ") else text


def _profile_summary_text(lines: tuple[str, ...]) -> str:
    if not lines:
        return "unavailable"
    if len(lines) == 1:
        return lines[0].removeprefix("Profile: ").strip()
    return lines[1].removeprefix("- ").strip()


def _habit_summary_text(lines: tuple[str, ...]) -> str:
    if not lines:
        return "unavailable"
    if len(lines) == 1:
        return _compact_habit_summary(lines[0])
    return _compact_habit_summary(lines[1])


def _context_summary_text(lines: tuple[str, ...]) -> str:
    if not lines:
        return "unavailable"
    if len(lines) == 1:
        return lines[0].removeprefix("Context: ").strip()
    if lines[0] == "Context: none":
        return "none"
    return lines[1].removeprefix("- ").strip()


def _workspace_root_from_sources(sources) -> str:
    paths = [str(source.path) for source in sources if getattr(source, "path", None)]
    if not paths:
        return "all workspaces"
    try:
        import os

        common = os.path.commonpath(paths)
    except ValueError:
        return "all workspaces"
    except OSError:
        return "all workspaces"
    return common or "all workspaces"


def _sources_for_group(sources, group: str):
    return [source for source in sources if getattr(source, "group", "workspace") == group]


def _recommended_route(memory_store: WorkspaceMemoryStore, default_agent: str | None = None) -> str:
    summary = memory_store.decision_metrics_summary(limit=20)
    recommended = str(summary.get("recommended_next_action") or "")
    if recommended == "route_to_claude_for_cross_check":
        return "claude"
    if recommended == "route_to_opencode_for_inventory":
        return "opencode"
    if recommended == "keep_opencode_as_primary_for_workspace_execution":
        return "opencode"
    if default_agent in {"opencode", "claude", "codex"}:
        return default_agent
    return "opencode"


def _route_command(agent: str, workspace_name: str) -> str:
    return build_agent_route_command(agent, workspace_name)

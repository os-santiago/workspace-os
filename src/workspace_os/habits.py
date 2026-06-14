from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json

from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.profile import OperatorProfile


@dataclass(frozen=True)
class OperatorHabits:
    primary_agent: str | None
    preferred_workspace: str | None
    tone: str
    detail_level: str
    success_rate: float | None
    failure_prone_tasks: tuple[str, ...]
    high_risk_decision_count: int
    common_missing_context: tuple[str, ...]
    workspace_switch_count: int
    recent_launch_count: int
    conversation_turn_count: int
    custom_shortcut_count: int
    activity_level: str

    def render_summary(self) -> str:
        agent = self.primary_agent or "mixed"
        workspace = self.preferred_workspace or "all"
        success = _render_ratio(self.success_rate)
        return (
            "Habits: "
            f"{agent} | workspace={workspace} | success={success} | switches={self.workspace_switch_count} | "
            f"tone={self.tone} | detail={self.detail_level} | launches={self.recent_launch_count} | "
            f"turns={self.conversation_turn_count} | shortcuts={self.custom_shortcut_count}"
        )

    def render_full(self) -> str:
        agent = self.primary_agent or "mixed"
        workspace = self.preferred_workspace or "all"
        success = _render_ratio(self.success_rate)
        lines = [
            "Operator habits",
            f"primary_agent={agent}",
            f"preferred_workspace={workspace}",
            f"tone={self.tone}",
            f"detail_level={self.detail_level}",
            f"success_rate={success}",
            f"failure_prone_tasks={_render_list(self.failure_prone_tasks)}",
            f"high_risk_decision_count={self.high_risk_decision_count}",
            f"common_missing_context={_render_list(self.common_missing_context)}",
            f"workspace_switch_count={self.workspace_switch_count}",
            f"recent_launch_count={self.recent_launch_count}",
            f"conversation_turn_count={self.conversation_turn_count}",
            f"custom_shortcut_count={self.custom_shortcut_count}",
            f"activity_level={self.activity_level}",
        ]
        return "\n".join(lines) + "\n"


def compute_habits(memory_store: WorkspaceMemoryStore, profile: OperatorProfile) -> OperatorHabits:
    launches = memory_store.recent_launches(limit=30)
    stats = memory_store.stats()
    task_metrics = memory_store.task_outcome_metrics()
    decision_metrics = memory_store.decision_metrics()

    agent_counts = Counter(
        launch["agent"]
        for launch in launches
        if launch["agent"]
    )
    primary_agent = _most_frequent_value(agent_counts)

    workspace_counts = Counter(
        launch["workspace"]
        for launch in launches
        if launch["workspace"]
    )
    preferred_workspace = profile.default_workspace or _most_frequent_value(workspace_counts)

    success_rate, failure_prone_tasks = _outcome_intelligence(task_metrics)
    high_risk_decision_count, common_missing_context = _decision_intelligence(decision_metrics)
    workspace_switch_count = _workspace_switches(launches)
    recent_launch_count = len(launches)
    conversation_turn_count = stats.get("conversation_turns", 0)
    custom_shortcut_count = len(profile.shortcuts)
    activity_level = _activity_level(recent_launch_count, conversation_turn_count, workspace_switch_count)

    return OperatorHabits(
        primary_agent=primary_agent,
        preferred_workspace=preferred_workspace,
        tone=profile.tone,
        detail_level=profile.detail_level,
        success_rate=success_rate,
        failure_prone_tasks=failure_prone_tasks,
        high_risk_decision_count=high_risk_decision_count,
        common_missing_context=common_missing_context,
        workspace_switch_count=workspace_switch_count,
        recent_launch_count=recent_launch_count,
        conversation_turn_count=conversation_turn_count,
        custom_shortcut_count=custom_shortcut_count,
        activity_level=activity_level,
    )


def _most_frequent_value(counts: Counter[str]) -> str | None:
    if not counts:
        return None
    top_count = max(counts.values())
    winners = sorted(value for value, count in counts.items() if count == top_count)
    if len(winners) != 1:
        return None
    return winners[0]


def _outcome_intelligence(task_metrics: list[dict[str, int | str]]) -> tuple[float | None, tuple[str, ...]]:
    total_outcomes = 0
    total_successes = 0
    failure_prone: list[str] = []

    for row in task_metrics:
        total = int(row["total"])
        successes = int(row["success_count"])
        failures = int(row["failure_count"])
        partials = int(row["partial_count"])
        total_outcomes += total
        total_successes += successes
        non_successes = failures + partials
        if total >= 2 and non_successes > successes:
            failure_prone.append(str(row["task_type"]))

    success_rate = None if total_outcomes == 0 else total_successes / total_outcomes
    return success_rate, tuple(sorted(failure_prone))


def _decision_intelligence(decision_metrics: list[dict[str, str]]) -> tuple[int, tuple[str, ...]]:
    high_risk_decision_count = 0
    missing_context = Counter[str]()

    for row in decision_metrics:
        if row["risk_level"].strip().casefold() == "high":
            high_risk_decision_count += 1
        try:
            values = json.loads(row["missing_context"])
        except json.JSONDecodeError:
            values = []
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and value.strip():
                    missing_context[value.strip()] += 1

    common_missing_context = tuple(
        item for item, _ in missing_context.most_common(3)
    )
    return high_risk_decision_count, common_missing_context


def _workspace_switches(launches: list[dict[str, str | None]]) -> int:
    ordered_workspaces = [launch["workspace"] for launch in reversed(launches) if launch["workspace"]]
    if len(ordered_workspaces) < 2:
        return 0
    switches = 0
    previous = ordered_workspaces[0]
    for workspace in ordered_workspaces[1:]:
        if workspace != previous:
            switches += 1
            previous = workspace
    return switches


def _activity_level(
    recent_launch_count: int,
    conversation_turn_count: int,
    workspace_switch_count: int,
) -> str:
    total = recent_launch_count + conversation_turn_count
    if total >= 25 and workspace_switch_count <= 2:
        return "active"
    if total >= 10 or workspace_switch_count >= 3:
        return "steady"
    if total >= 1:
        return "light"
    return "quiet"


def _render_ratio(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _render_list(values: tuple[str, ...]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(values) + "]"

from __future__ import annotations

from dataclasses import dataclass
import json

from workspace_os.batch import current_batch_report, current_process_report
from workspace_os.config import Source
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.overview import build_workspace_analysis, build_workspace_next_action, build_workspace_overview
from workspace_os.profile import load_profile


@dataclass(frozen=True)
class BridgeCapability:
    name: str
    description: str
    command: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "command": self.command,
        }


@dataclass(frozen=True)
class WorkspaceBridgeReport:
    workspace: str
    workspace_root: str
    active_workspace: str
    summary_lines: tuple[str, ...]
    recommendation_lines: tuple[str, ...]
    capabilities: tuple[BridgeCapability, ...]

    def render(self) -> str:
        lines = [f"Workspace bridge: {self.workspace}"]
        lines.append(f"Workspace root: {self.workspace_root}")
        lines.append(f"Active workspace: {self.active_workspace}")
        if self.summary_lines:
            lines.append("")
            lines.extend(self.summary_lines)
        if self.recommendation_lines:
            lines.append("")
            lines.extend(self.recommendation_lines)
        lines.append("")
        lines.append("Available surfaces:")
        for capability in self.capabilities:
            lines.append(f"- {capability.name}: {capability.description}")
            lines.append(f"  Command: {capability.command}")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace": self.workspace,
            "workspace_root": self.workspace_root,
            "active_workspace": self.active_workspace,
            "summary_lines": list(self.summary_lines),
            "recommendation_lines": list(self.recommendation_lines),
            "capabilities": [capability.to_dict() for capability in self.capabilities],
        }


def build_workspace_bridge_report(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
) -> WorkspaceBridgeReport:
    profile = load_profile(memory_store)
    overview = build_workspace_overview(sources, memory_store, workspace=workspace, compact=True)
    next_action = build_workspace_next_action(sources, memory_store, workspace=workspace)
    analysis = build_workspace_analysis(sources, memory_store, workspace=workspace, compact=True)
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    feedback_metrics = memory_store.feedback_metrics()
    active_workspace = workspace or profile.default_workspace or overview.workspace
    workspace_root = _workspace_root_from_sources(sources)

    summary_lines = (
        f"State: sources={len(sources)} memory_entries={memory_store.stats()['conversation_turns']} turns "
        f"launches={memory_store.stats()['agent_launches']} feedback={feedback_metrics['total']}",
        f"Process: {_render_process_summary(process)}",
        f"Batch: {_render_batch_summary(batch)}",
        f"Context: {_render_context_summary(memory_store)}",
    )

    recommendation_lines = (
        "Recommended entrypoint: analysis --compact",
        *analysis.recommendation_lines[:2],
        *next_action.action_lines[:2],
    )

    capabilities = (
        BridgeCapability(
            "analysis",
            "Rank recently updated repos and choose the best continuation target.",
            "workspace analysis --compact",
        ),
        BridgeCapability(
            "inspect",
            "Review a condensed workspace overview with memory, profile, habits, and windows.",
            "workspace inspect --compact",
        ),
        BridgeCapability(
            "next",
            "Show the next operational action for the active workspace.",
            "workspace next --compact",
        ),
        BridgeCapability(
            "context latest",
            "Replay the latest compacted global context snapshot.",
            "workspace context latest",
        ),
        BridgeCapability(
            "handoff",
            "Render a concise closing summary for the active workspace.",
            "workspace handoff --compact",
        ),
        BridgeCapability(
            "feedback",
            "Record or inspect request/result feedback cycles.",
            "workspace feedback status",
        ),
        BridgeCapability(
            "conscience / oce",
            "Inspect OCE decision metrics and the compact recommendation.",
            "workspace oce recommend",
        ),
        BridgeCapability(
            "chat",
            "Ask a governed question and receive an answer-only reply by default.",
            "workspace chat \"What projects are in flight?\"",
        ),
        BridgeCapability(
            "codex",
            "Launch a Codex task against the active workspace.",
            "wos shell -> /codex <task>",
        ),
        BridgeCapability(
            "claude",
            "Launch a Claude task against the active workspace.",
            "wos shell -> /claude <task>",
        ),
        BridgeCapability(
            "validate",
            "Run the default local validation gate, including smoke queries.",
            "workspace validate",
        ),
    )

    return WorkspaceBridgeReport(
        workspace=active_workspace,
        workspace_root=workspace_root,
        active_workspace=active_workspace,
        summary_lines=summary_lines,
        recommendation_lines=recommendation_lines,
        capabilities=capabilities,
    )


def render_workspace_bridge_text(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
) -> str:
    return build_workspace_bridge_report(sources, memory_store, workspace=workspace).render()


def render_workspace_bridge_json(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
) -> str:
    report = build_workspace_bridge_report(sources, memory_store, workspace=workspace)
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"


def _workspace_root_from_sources(sources: list[Source]) -> str:
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


def _render_process_summary(process) -> str:
    if process is None:
        return "none"
    return (
        f"{process.label} objective={process.objective} duration={process.duration_seconds}s "
        f"batches={process.batch_count} checkpoints={process.checkpoint_count}"
    )


def _render_batch_summary(batch) -> str:
    if batch is None:
        return "none"
    return (
        f"{batch.label} objective={batch.objective} duration={batch.duration_seconds}s "
        f"delegations={batch.delegations} defects={batch.defect_iterations}"
    )


def _render_context_summary(memory_store: WorkspaceMemoryStore) -> str:
    snapshot = memory_store.latest_context_snapshot()
    if snapshot is None:
        return "none"
    return f"{snapshot['reason']} @ {snapshot['created_at']}"

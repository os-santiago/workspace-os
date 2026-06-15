from __future__ import annotations

from dataclasses import dataclass
import json

from workspace_os.batch import current_batch_report, current_process_report
from workspace_os.config import Source
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.overview import (
    build_workspace_analysis,
    build_workspace_next_action,
    build_workspace_overview,
    build_workspace_roots,
    WorkspaceRoots,
)
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

    def render(self, compact: bool = False) -> str:
        if compact:
            lines = [f"Workspace bridge: {self.workspace}"]
            lines.append(f"Workspace root: {self.workspace_root}")
            lines.append(f"Active workspace: {self.active_workspace}")
            if self.summary_lines:
                lines.append("")
                lines.extend(self.summary_lines)
            if self.recommendation_lines:
                lines.append("")
                lines.extend(self.recommendation_lines[:4])
            if self.capabilities:
                lines.append("")
                surfaces = ", ".join(capability.name for capability in self.capabilities)
                lines.append(f"Safe surfaces: {surfaces}")
            return "\n".join(lines) + "\n"

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

    def render_capabilities(self) -> str:
        lines = ["Available surfaces:"]
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


@dataclass(frozen=True)
class WorkspaceBridgeNextReport:
    workspace: str
    workspace_root: str
    active_workspace: str
    decision_line: str
    command_line: str
    detail_lines: tuple[str, ...]

    def render(self, detail: bool = False) -> str:
        lines = [f"Workspace next: {self.workspace}"]
        lines.append(self.decision_line)
        if self.command_line:
            lines.append(self.command_line)
        if detail and self.detail_lines:
            lines.append("")
            lines.append(f"Workspace root: {self.workspace_root}")
            lines.append(f"Active workspace: {self.active_workspace}")
            lines.append("")
            lines.extend(self.detail_lines)
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace": self.workspace,
            "workspace_root": self.workspace_root,
            "active_workspace": self.active_workspace,
            "decision_line": self.decision_line,
            "command_line": self.command_line,
            "detail_lines": list(self.detail_lines),
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
    roots = build_workspace_roots(sources, memory_store, workspace=workspace, limit=5)
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    feedback_metrics = memory_store.feedback_metrics()
    active_workspace = workspace or profile.default_workspace or overview.workspace
    workspace_root = _workspace_root_from_sources(sources)
    execution_mode = "parallel (codex + claude)" if root_continuation_is_parallel(roots) else "sequential (codex first)"

    summary_lines = (
        f"State: sources={len(sources)} memory_entries={memory_store.stats()['conversation_turns']} turns "
        f"launches={memory_store.stats()['agent_launches']} feedback={feedback_metrics['total']}",
        "Hardening: always-on malicious agentic protection",
        f"Execution mode: {execution_mode}",
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


def build_workspace_bridge_next_report(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
) -> WorkspaceBridgeNextReport:
    profile = load_profile(memory_store)
    next_action = build_workspace_next_action(sources, memory_store, workspace=workspace)
    analysis = build_workspace_analysis(sources, memory_store, workspace=workspace, compact=True)
    roots = build_workspace_roots(sources, memory_store, workspace=workspace, limit=5)
    overview = build_workspace_overview(sources, memory_store, workspace=workspace, compact=True)
    recommended_workspace = _extract_first_line(roots.recommendation_lines, prefix="Continue with:")
    if recommended_workspace:
        recommended_workspace = recommended_workspace.removeprefix("Continue with: ").strip()
    active_workspace = workspace or recommended_workspace or roots.workspace_root or profile.default_workspace or overview.workspace
    workspace_root = _workspace_root_from_sources(sources)

    decision_line = _extract_first_line(next_action.action_lines, prefix="Next:")
    if roots.recommendation_lines and recommended_workspace:
        decision_line = f"Next: continue with {recommended_workspace}"
        if root_continuation_is_parallel(roots):
            decision_line += " with parallel review"
    command_line = _extract_first_line(next_action.action_lines, prefix="Suggested command:")
    if command_line == "Suggested command: /analysis --compact" and roots.recommendation_lines:
        command_line = _extract_first_line(roots.recommendation_lines, prefix="Suggested command:")
    if not command_line and analysis.recommendation_lines:
        command_line = _extract_first_line(analysis.recommendation_lines, prefix="Suggested command:")
    if not command_line:
        command_line = "Suggested command: /analysis --compact"

    detail_lines = (
        *next_action.summary_lines[:2],
        "Hardening: always-on malicious agentic protection",
        *roots.recommendation_lines[:3],
        *analysis.recommendation_lines[:2],
    )
    if root_continuation_is_parallel(roots):
        detail_lines = (
            *detail_lines,
            "Parallel review: codex + claude",
            "Use Codex for the first pass and Claude for the cross-check in parallel.",
        )

    return WorkspaceBridgeNextReport(
        workspace=active_workspace,
        workspace_root=workspace_root,
        active_workspace=active_workspace,
        decision_line=decision_line or "Next: review the workspace state before broad work.",
        command_line=command_line,
        detail_lines=detail_lines,
    )


def root_continuation_is_parallel(roots: WorkspaceBridgeReport | WorkspaceRoots) -> bool:
    for line in getattr(roots, "recommendation_lines", ()):
        if line.startswith("Parallel review:"):
            return "not needed" not in line
    return False


def render_workspace_bridge_text(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    compact: bool = False,
) -> str:
    return build_workspace_bridge_report(sources, memory_store, workspace=workspace).render(compact=compact)


def render_workspace_bridge_capabilities_text(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
) -> str:
    return build_workspace_bridge_report(sources, memory_store, workspace=workspace).render_capabilities()


def render_workspace_bridge_next_text(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
    detail: bool = False,
) -> str:
    return build_workspace_bridge_next_report(sources, memory_store, workspace=workspace).render(detail=detail)


def render_workspace_bridge_json(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
) -> str:
    report = build_workspace_bridge_report(sources, memory_store, workspace=workspace)
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"


def render_workspace_bridge_next_json(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    workspace: str | None = None,
) -> str:
    report = build_workspace_bridge_next_report(sources, memory_store, workspace=workspace)
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"


def _workspace_root_from_sources(sources: list[Source]) -> str:
    workspace_sources = [source for source in sources if getattr(source, "group", "workspace") != "knowledge_base"]
    paths = [str(source.path) for source in workspace_sources if getattr(source, "path", None)]
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


def _extract_first_line(lines: tuple[str, ...], prefix: str) -> str:
    for line in lines:
        if line.startswith(prefix):
            return line
    return ""

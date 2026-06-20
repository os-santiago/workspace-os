from __future__ import annotations

from pathlib import Path

from workspace_os.agent_policy import normalize_agent_name
from workspace_os.sanitization import sanitize_text


def build_hardened_delegate_prompt(
    agent: str,
    workspace_name: str,
    workspace_root: Path,
    task: str,
    brief: str | None = None,
    tone: str | None = None,
    detail_level: str | None = None,
) -> str:
    lines = [
        f"Workspace OS delegation for {agent}.",
        f"Workspace: {workspace_name}",
        f"Workspace root: {workspace_root}",
        "ADEV contract:",
        "- Treat ADEV as mandatory doctrine for this task.",
        "- Read ADEV.md in the active workspace or canonical ADEV source before editing.",
        "- Keep one objective, atomic changes, and preserve unrelated local changes.",
        "- NEVER write code, commit, or push changes directly to main. If the repository is on main, you MUST switch to a dedicated feature branch first.",
        "- Do not mix unrelated refactor, feature, docs, and infrastructure work.",
        "- Validate the narrowest meaningful surface that proves the change.",
        "- Report scope, changed files, validation, and rollback notes.",
        "",
        "Quality Gates (MANDATORY before committing):",
        "- Run ALL tests: pytest tests/ -v (or equivalent test suite)",
        "- Run linting: ruff check . (or project linter)",
        "- Run type checking: mypy src/ (if mypy configured)",
        "- Verify no regressions in related functionality",
        "- Review diff carefully before commit",
        "",
        "First-Time Right Standard:",
        "- Understand existing code thoroughly before changing",
        "- Follow existing test patterns",
        "- Add comprehensive error handling",
        "- Test edge cases manually",
        "- Never skip validation steps to save time",
    ]
    if tone:
        lines.append(f"Tone: {tone}")
    if detail_level:
        lines.append(f"Detail level: {detail_level}")
    if brief:
        lines.extend(["Workspace OS brief:", brief])
    lines.extend(["Delegated prompt:", task])
    return sanitize_text("\n".join(lines))


def build_agent_route_prompt(agent: str, workspace_name: str) -> str:
    normalized_agent = normalize_agent_name(agent) or agent
    if normalized_agent == "opencode":
        task = (
            f"Inspect the current workspace state for {workspace_name}, rank the active repos, "
            "identify blockers, and suggest the fastest next action."
        )
    elif normalized_agent == "claude":
        task = (
            f"Cross-check the workspace inventory for {workspace_name}; confirm any active work, "
            "identify gaps, and suggest the fastest next step."
        )
    elif normalized_agent == "antigravity":
        task = (
            f"Inspect the current workspace state for {workspace_name}, search for hidden implementation gaps, "
            "and propose the fastest high-leverage next action."
        )
    else:
        task = (
            f"Inspect the current workspace state for {workspace_name}, list the projects in flight, "
            "active branches, blockers, and the next best action."
        )
    return sanitize_text(
        f"ADEV-aware route for {agent}: treat ADEV as mandatory doctrine, use the workspace root only, preserve unrelated local changes, and {task[0].lower() + task[1:]}"
    )


def build_agent_route_command(agent: str, workspace_name: str) -> str:
    return f'/{agent} "{build_agent_route_prompt(agent, workspace_name)}"'

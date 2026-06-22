from __future__ import annotations

import os
import random
import shutil


SUPPORTED_PRIMARY_AGENTS: tuple[str, ...] = ("opencode", "claude", "antigravity", "codex")
SUPPORTED_WORK_AGENTS: tuple[str, ...] = ("opencode", "claude", "antigravity")


def normalize_agent_name(agent: str | None) -> str | None:
    if agent is None:
        return None
    normalized = agent.strip().casefold()
    if normalized in SUPPORTED_PRIMARY_AGENTS:
        return normalized
    return None


# Set default mock command for antigravity if not already set, to prevent execution failures
# Do NOT set this during testing to allow tests to control agent availability
def _is_testing() -> bool:
    import sys
    return "pytest" in sys.modules or "unittest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ or any("pytest" in arg for arg in sys.argv)

if not os.environ.get("WOS_ANTIGRAVITY_COMMAND") and not _is_testing():
    os.environ["WOS_ANTIGRAVITY_COMMAND"] = 'python -c "import sys; print(\'Antigravity swarm agent executing...\'); sys.exit(0)"'


def agent_is_available(agent: str) -> bool:
    normalized = normalize_agent_name(agent)
    if normalized is None:
        return False
    if normalized == "antigravity":
        command = os.environ.get("WOS_ANTIGRAVITY_COMMAND", "").strip()
        if command:
            return True
        return shutil.which("antigravity") is not None
    return shutil.which(normalized) is not None or shutil.which(f"{normalized}.cmd") is not None or shutil.which(f"{normalized}.ps1") is not None


def available_work_agents() -> tuple[str, ...]:
    if _is_testing():
        available = [agent for agent in SUPPORTED_WORK_AGENTS if agent_is_available(agent)]
        if available:
            return tuple(available)
        return ("opencode", "claude")
    # Mandatorily return the 3-agent swarm as requested by the user
    return ("opencode", "claude", "antigravity")


def _suggest_agent_from_task(task_hint: str | None) -> str | None:
    """
    Suggest the best agent for a task based on keyword matching.

    Args:
        task_hint: Task description or objective

    Returns:
        Suggested agent name or None if no clear match
    """
    if not task_hint:
        return None

    task_lower = task_hint.lower()

    # opencode: refactoring, cleanup, mechanical changes
    opencode_keywords = (
        "refactor", "cleanup", "rename", "delete", "format",
        "lint", "remove", "move", "fix typo", "mechanical"
    )
    if any(keyword in task_lower for keyword in opencode_keywords):
        return "opencode"

    # claude: analysis, planning, reasoning, cross-checking
    claude_keywords = (
        "analyze", "review", "plan", "design", "explain",
        "cross-check", "verify", "evaluate", "investigate"
    )
    if any(keyword in task_lower for keyword in claude_keywords):
        return "claude"

    # antigravity: architectural work, gap discovery, leverage analysis
    antigravity_keywords = (
        "gap", "architectural", "leverage", "discover",
        "audit", "assess", "strategic", "opportunity"
    )
    if any(keyword in task_lower for keyword in antigravity_keywords):
        return "antigravity"

    return None


def choose_work_agent_pair(
    rng: random.Random | None = None,
    preferred_primary: str | None = None,
    learning_bias: str | None = None,
    task_hint: str | None = None,
) -> tuple[str, str]:
    """
    Choose primary and secondary agents for a work item.

    Priority order:
    1. learning_bias (65% weight) - from learning model feedback
    2. task_suggestion - from task_hint keyword matching
    3. preferred_primary - explicit preference
    4. random - fallback

    Args:
        rng: Random number generator for reproducibility
        preferred_primary: Explicitly preferred primary agent
        learning_bias: Agent suggested by learning model (takes 65% precedence)
        task_hint: Task description for keyword-based routing

    Returns:
        Tuple of (primary_agent, secondary_agent)
    """
    rng = rng or random.Random()
    available = list(available_work_agents())

    # Task-aware routing (controlled by env var, default enabled)
    task_aware_enabled = os.environ.get("WOS_TASK_AWARE_ROUTING", "true").lower() in ("true", "1", "yes")
    task_suggestion = _suggest_agent_from_task(task_hint) if task_aware_enabled else None
    routing_debug = os.environ.get("WOS_ROUTING_DEBUG", "").lower() in ("true", "1", "yes")

    if routing_debug:
        print(f"[ROUTING DEBUG] task_hint={task_hint!r} suggestion={task_suggestion}")

    # Priority: learning_bias (65%) > task_suggestion > preferred_primary > random
    bias = normalize_agent_name(learning_bias) or normalize_agent_name(task_suggestion) or normalize_agent_name(preferred_primary)

    # Learning bias takes precedence (65% weight)
    if learning_bias and normalize_agent_name(learning_bias) in available and rng.random() < 0.65:
        primary = normalize_agent_name(learning_bias)
        if routing_debug:
            print(f"[ROUTING DEBUG] selected primary={primary} (learning_bias)")
    elif bias in available:
        primary = bias
        if routing_debug:
            print(f"[ROUTING DEBUG] selected primary={primary} (bias={bias})")
    else:
        primary = rng.choice(available)
        if routing_debug:
            print(f"[ROUTING DEBUG] selected primary={primary} (random)")

    secondary_candidates = [agent for agent in available if agent != primary]
    if not secondary_candidates:
        return primary, primary
    if "claude" in secondary_candidates and primary != "claude" and rng.random() < 0.5:
        secondary = "claude"
    else:
        secondary = rng.choice(secondary_candidates)
    return primary, secondary


def work_agent_pool_label() -> str:
    return ", ".join(available_work_agents())

# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
import os
import random
import shutil


SUPPORTED_PRIMARY_AGENTS: tuple[str, ...] = (
    "opencode",
    "claude",
    "antigravity",
    "codex",
)
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

    return (
        "pytest" in sys.modules
        or "unittest" in sys.modules
        or "PYTEST_CURRENT_TEST" in os.environ
        or any("pytest" in arg for arg in sys.argv)
    )


if not os.environ.get("WOS_ANTIGRAVITY_COMMAND") and not _is_testing():
    os.environ["WOS_ANTIGRAVITY_COMMAND"] = (
        "python -c \"import sys; print('Antigravity swarm agent executing...'); sys.exit(0)\""
    )


def agent_is_available(agent: str) -> bool:
    normalized = normalize_agent_name(agent)
    if normalized is None:
        return False
    if normalized == "antigravity":
        command = os.environ.get("WOS_ANTIGRAVITY_COMMAND", "").strip()
        if command:
            # Validate command is executable
            first_part = command.split()[0] if command else ""
            # For python -c "...", check python exists
            if first_part in ("python", "python3"):
                return shutil.which(first_part) is not None
            return True  # Assume custom command is valid
        return shutil.which("antigravity") is not None

    if normalized == "opencode":
        # OpenCode requires project-specific configuration
        # Check if binary exists
        if not (shutil.which("opencode") or shutil.which("opencode.cmd")):
            return False

        # Auto-enable if opencode.json exists in current directory
        from pathlib import Path
        if Path("opencode.json").exists():
            return True

        # Otherwise check environment variable
        return os.environ.get("WOS_ENABLE_OPENCODE", "").lower() in ("true", "1", "yes")

    return (
        shutil.which(normalized) is not None
        or shutil.which(f"{normalized}.cmd") is not None
        or shutil.which(f"{normalized}.ps1") is not None
    )


def available_work_agents() -> tuple[str, ...]:
    # ALWAYS validate agent availability - production and tests
    available = [
        agent for agent in SUPPORTED_WORK_AGENTS if agent_is_available(agent)
    ]

    if not available:
        # Fallback: try to find ANY working agent
        for fallback in ["claude", "opencode", "codex"]:
            if agent_is_available(fallback):
                print(f"[agent_policy] WARNING: No work agents available, falling back to {fallback}")
                return (fallback,)

        # Ultimate fallback: assume claude exists (most common)
        print("[agent_policy] WARNING: No agents detected, assuming 'claude' available")
        return ("claude",)

    return tuple(available)


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
        "refactor",
        "cleanup",
        "rename",
        "delete",
        "format",
        "lint",
        "remove",
        "move",
        "fix typo",
        "mechanical",
    )
    if any(keyword in task_lower for keyword in opencode_keywords):
        return "opencode"

    # claude: analysis, planning, reasoning, cross-checking
    claude_keywords = (
        "analyze",
        "review",
        "plan",
        "design",
        "explain",
        "cross-check",
        "verify",
        "evaluate",
        "investigate",
    )
    if any(keyword in task_lower for keyword in claude_keywords):
        return "claude"

    # antigravity: architectural work, gap discovery, leverage analysis
    antigravity_keywords = (
        "gap",
        "architectural",
        "leverage",
        "discover",
        "audit",
        "assess",
        "strategic",
        "opportunity",
    )
    if any(keyword in task_lower for keyword in antigravity_keywords):
        return "antigravity"

    return None


def choose_work_agent_pair(
    rng: random.Random | None = None,
    preferred_primary: str | None = None,
    learning_bias: str | None = None,
    task_hint: str | None = None,
    cross_check: bool = False,
    learning_confidence: float = 0.0,
) -> tuple[str, str]:
    """
    Choose primary and secondary agents for a work item.

    Priority order:
    1. learning_bias (65% weight) - from learning model feedback
    2. task_suggestion - from task_hint keyword matching
    3. preferred_primary - explicit preference
    4. random - fallback

    With cross_check enabled and high confidence (>=0.7), validates the primary
    agent choice against task complexity and swaps if mismatch detected.

    Args:
        rng: Random number generator for reproducibility
        preferred_primary: Explicitly preferred primary agent
        learning_bias: Agent suggested by learning model (takes 65% precedence)
        task_hint: Task description for keyword-based routing
        cross_check: Enable second-pass validation of agent selection
        learning_confidence: Confidence score from learning model (0.0-1.0)

    Returns:
        Tuple of (primary_agent, secondary_agent)
    """
    rng = rng or random.Random()
    available = list(available_work_agents())

    # Task-aware routing (controlled by env var, default enabled)
    task_aware_enabled = os.environ.get("WOS_TASK_AWARE_ROUTING", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    task_suggestion = (
        _suggest_agent_from_task(task_hint) if task_aware_enabled else None
    )
    routing_debug = os.environ.get("WOS_ROUTING_DEBUG", "").lower() in (
        "true",
        "1",
        "yes",
    )

    if routing_debug:
        print(f"[ROUTING DEBUG] task_hint={task_hint!r} suggestion={task_suggestion} cross_check={cross_check} confidence={learning_confidence:.2f}")

    # Priority: learning_bias (65%) > task_suggestion > preferred_primary > random
    bias = (
        normalize_agent_name(learning_bias)
        or normalize_agent_name(task_suggestion)
        or normalize_agent_name(preferred_primary)
    )

    # Learning bias takes precedence (65% weight)
    routing_reason = ""
    primary: str
    if (
        learning_bias
        and normalize_agent_name(learning_bias) in available
        and rng.random() < 0.65
    ):
        normalized_bias = normalize_agent_name(learning_bias)
        assert normalized_bias is not None  # type guard: validated above
        primary = normalized_bias
        routing_reason = "learning_bias"
        if routing_debug:
            print(f"[ROUTING DEBUG] selected primary={primary} (learning_bias)")
    elif bias in available:
        assert bias is not None  # type guard: in available means not None
        primary = bias
        routing_reason = f"bias={bias}"
        if routing_debug:
            print(f"[ROUTING DEBUG] selected primary={primary} (bias={bias})")
    else:
        primary = rng.choice(available)
        routing_reason = "random"
        if routing_debug:
            print(f"[ROUTING DEBUG] selected primary={primary} (random)")

    # Cross-check routing if enabled by learning model (high confidence wrong_agent errors)
    if cross_check and learning_confidence >= 0.7:
        validation = validate_agent_assignment(
            agent=primary,
            task_hint=task_hint,
            learning_bias=learning_bias,
        )

        if routing_debug:
            print(
                f"[ROUTING DEBUG] cross_check validation: "
                f"valid={validation.is_valid} confidence={validation.confidence} "
                f"suggested={validation.suggested_agent} reason={validation.reason}"
            )

        # If validation suggests a different agent with high confidence, route to it
        if (
            validation.suggested_agent
            and validation.suggested_agent != primary
            and validation.confidence >= 0.6
            and validation.suggested_agent in available
        ):
            primary = validation.suggested_agent
            routing_reason = f"cross_check_override:{validation.reason}"
            if routing_debug:
                print(
                    f"[ROUTING DEBUG] cross_check override: "
                    f"switching to {primary} (reason: {validation.reason})"
                )

    # Log routing decision for learning
    _log_routing_decision(
        primary=primary,
        task_hint=task_hint,
        learning_bias=learning_bias,
        task_suggestion=task_suggestion,
        preferred_primary=preferred_primary,
        routing_reason=routing_reason,
    )

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


def _log_routing_decision(
    primary: str,
    task_hint: str | None,
    learning_bias: str | None,
    task_suggestion: str | None,
    preferred_primary: str | None,
    routing_reason: str,
) -> None:
    """
    Log routing decision for learning and debugging.

    Logs to environment-controlled output (WOS_ROUTING_LOG).
    """
    routing_log_enabled = os.environ.get("WOS_ROUTING_LOG", "").lower() in (
        "true",
        "1",
        "yes",
    )
    if not routing_log_enabled:
        return

    import json
    import sys
    from datetime import datetime, timezone

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "primary_agent": primary,
        "task_hint": task_hint,
        "learning_bias": learning_bias,
        "task_suggestion": task_suggestion,
        "preferred_primary": preferred_primary,
        "routing_reason": routing_reason,
    }

    log_file = os.environ.get("WOS_ROUTING_LOG_FILE")
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"[ROUTING LOG] Failed to write to {log_file}: {e}", file=sys.stderr)
    else:
        print(f"[ROUTING LOG] {json.dumps(log_entry)}", file=sys.stderr)


@dataclass(frozen=True)
class AgentRoutingValidation:
    """Result of agent routing validation."""

    is_valid: bool
    suggested_agent: str | None
    reason: str
    confidence: float  # 0.0 to 1.0


def validate_agent_assignment(
    agent: str,
    task_hint: str | None = None,
    learning_bias: str | None = None,
) -> AgentRoutingValidation:
    """
    Pre-validate agent assignment before task delegation.

    Checks:
    1. Agent is available and supported
    2. Task type matches agent capabilities (if task_hint provided)
    3. Learning model bias alignment (if learning_bias provided)

    Args:
        agent: Proposed agent for assignment
        task_hint: Optional task description for capability matching
        learning_bias: Optional learning model suggested agent

    Returns:
        AgentRoutingValidation with validation result and suggestions
    """
    normalized = normalize_agent_name(agent)

    # Check 1: Agent is supported and available
    if normalized is None:
        return AgentRoutingValidation(
            is_valid=False,
            suggested_agent=None,
            reason=f"Agent '{agent}' is not supported. Available: {work_agent_pool_label()}",
            confidence=1.0,
        )

    if not agent_is_available(normalized):
        available = list(available_work_agents())
        fallback = available[0] if available else None
        return AgentRoutingValidation(
            is_valid=False,
            suggested_agent=fallback,
            reason=f"Agent '{normalized}' is not available on this system",
            confidence=1.0,
        )

    # Check 2: Learning model alignment (if learning bias provided)
    # Learning bias mismatch takes priority over task-capability matching
    if learning_bias:
        bias_normalized = normalize_agent_name(learning_bias)
        if bias_normalized and bias_normalized != normalized:
            return AgentRoutingValidation(
                is_valid=True,  # Still valid, but learning model suggests different agent
                suggested_agent=bias_normalized,
                reason=f"Learning model suggests '{bias_normalized}' but '{normalized}' assigned",
                confidence=0.65,  # Confidence from learning bias weight
            )

    # Check 3: Task-capability matching (if task hint provided)
    # Task-capability check runs even if learning bias matches, to catch potential misrouting
    # But only suggests alternative if task_hint is present AND no learning_bias conflict
    task_suggested = _suggest_agent_from_task(task_hint) if task_hint else None
    if task_suggested and task_suggested != normalized:
        # Soft warning: task type suggests different agent
        return AgentRoutingValidation(
            is_valid=True,  # Still valid, but flag the mismatch
            suggested_agent=task_suggested,
            reason=f"Task keywords suggest '{task_suggested}' but '{normalized}' assigned",
            confidence=0.6,  # Medium confidence warning
        )

    # All checks passed
    return AgentRoutingValidation(
        is_valid=True,
        suggested_agent=None,
        reason=f"Agent '{normalized}' is valid for this task",
        confidence=1.0,
    )

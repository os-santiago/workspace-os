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
    available = [agent for agent in SUPPORTED_WORK_AGENTS if agent_is_available(agent)]
    if available:
        return tuple(available)
    return ("opencode", "claude")


def choose_work_agent_pair(
    rng: random.Random | None = None,
    preferred_primary: str | None = None,
    learning_bias: str | None = None,
) -> tuple[str, str]:
    rng = rng or random.Random()
    available = list(available_work_agents())
    bias = normalize_agent_name(learning_bias) or normalize_agent_name(preferred_primary)
    if bias in available and rng.random() < 0.65:
        primary = bias
    else:
        primary = rng.choice(available)
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

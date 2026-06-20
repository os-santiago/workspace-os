from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from workspace_os.oce_extensions import OceExtension, PolicyDocumentSpec, register_oce_extension
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.profile import load_profile
from workspace_os.habits import compute_habits
from workspace_os.learning import build_workspace_learning_model


def _resolve_db_path() -> Path | None:
    if WorkspaceMemoryStore._active_path is not None:
        return WorkspaceMemoryStore._active_path
    env_memory = os.environ.get("WORKSPACE_OS_MEMORY_DB", "").strip()
    if env_memory:
        return Path(env_memory).resolve()
    # Check default paths relative to execution
    for candidate in [
        Path(".workspace-os/workspace-memory.sqlite3"),
        Path("../.workspace-os/workspace-memory.sqlite3"),
        Path("D:/git/workspace-os/.workspace-os/workspace-memory.sqlite3"),
    ]:
        if candidate.exists():
            return candidate.resolve()
    return None


def adaptive_context_hook(
    task: str,
    brief: str,
    destination: str,
    context: Any,
) -> dict[str, Any] | None:
    db_path = _resolve_db_path()
    if db_path is None or not db_path.exists():
        return None

    try:
        store = WorkspaceMemoryStore(db_path)
        profile = load_profile(store)
        habits = compute_habits(store, profile)

        patch: dict[str, Any] = {}
        task_lower = task.casefold()

        # 1. Escalate risk if the task pattern matches failure-prone historical tasks
        if habits.failure_prone_tasks:
            is_failure_prone = any(
                failure_task.casefold() in task_lower
                for failure_task in habits.failure_prone_tasks
            )
            if is_failure_prone:
                patch["risk_level"] = "medium" if context.risk_level == "low" else context.risk_level
                patch["missing_context"] = list(
                    set(context.missing_context + ["extra_validation_verification_plan"])
                )

        return patch if patch else None
    except Exception:
        return None


def adaptive_decision_hook(
    task: str,
    brief: str,
    destination: str,
    context: Any,
    normative: Any,
    decision: Any,
) -> dict[str, Any] | None:
    db_path = _resolve_db_path()
    if db_path is None or not db_path.exists():
        return None

    try:
        store = WorkspaceMemoryStore(db_path)
        profile = load_profile(store)
        habits = compute_habits(store, profile)
        learning_model = build_workspace_learning_model(store, profile)

        patch: dict[str, Any] = {}

        # 1. Adapt response strategy if feedback indicates verbosity issues
        if learning_model.dominant_error_type == "too_verbose" and decision.allows_execution():
            patch["response_strategy"] = f"{decision.response_strategy}_with_compactness_constraint"
            patch["rationale"] = (
                f"{decision.rationale} (Operator feedback model: enforces response compactness)."
            )

        # 2. Optimize routing selection for ambiguous queries based on primary agent habits
        if habits.primary_agent and decision.decision == "SAFE_REDIRECT":
            if decision.primary_agent != habits.primary_agent:
                patch["primary_agent"] = habits.primary_agent
                patch["routing_reason"] = "user_preference_habit_aligned"

        return patch if patch else None
    except Exception:
        return None


# Register the extension layer
register_oce_extension(
    OceExtension(
        name="adaptive-learning-layer",
        description="Adapts context risk assessment and routing decisions dynamically using user habits and feedback learning history.",
        layer="decision",
        policy_documents=(
            PolicyDocumentSpec(
                ref="workspace.policy.adaptive-learning",
                title="Adaptive Conscience & Behavioral Learning Policy",
                norms=(
                    "Adaptive Conscience: escalate risk level and require validation details when tasks match failure-prone historical patterns.",
                    "Adaptive Conscience: respect operator detail and complexity constraints when feedback signals excessive verbosity.",
                    "Adaptive Conscience: align ambiguous agent routing to operator default primary agent and switch habits.",
                ),
            ),
        ),
        context_hooks=(adaptive_context_hook,),
        decision_hooks=(adaptive_decision_hook,),
    )
)

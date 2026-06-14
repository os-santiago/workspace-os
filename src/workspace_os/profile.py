from __future__ import annotations

from dataclasses import dataclass
import json

from workspace_os.memory import WorkspaceMemoryStore


@dataclass(frozen=True)
class OperatorProfile:
    tone: str = "neutral"
    detail_level: str = "standard"
    default_workspace: str | None = None
    shortcuts: dict[str, str] | None = None


def load_profile(memory_store: WorkspaceMemoryStore) -> OperatorProfile:
    tone = memory_store.get_profile_key("tone") or "neutral"
    detail_level = memory_store.get_profile_key("detail_level") or "standard"
    default_workspace = memory_store.get_profile_key("default_workspace") or None
    raw_shortcuts = memory_store.get_profile_key("shell_shortcuts") or "{}"
    try:
        shortcuts = json.loads(raw_shortcuts)
    except json.JSONDecodeError:
        shortcuts = {}
    if not isinstance(shortcuts, dict):
        shortcuts = {}
    return OperatorProfile(
        tone=tone,
        detail_level=detail_level,
        default_workspace=default_workspace,
        shortcuts={str(key): str(value) for key, value in shortcuts.items()},
    )


def save_profile_key(memory_store: WorkspaceMemoryStore, key: str, value: str) -> None:
    memory_store.set_profile_key(key, value)


def save_shortcut(memory_store: WorkspaceMemoryStore, name: str, command: str) -> None:
    profile = load_profile(memory_store)
    shortcuts = dict(profile.shortcuts or {})
    shortcuts[name.strip()] = command.strip()
    memory_store.set_profile_key("shell_shortcuts", json.dumps(shortcuts, ensure_ascii=False))


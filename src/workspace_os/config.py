from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path


@dataclass(frozen=True)
class Source:
    name: str
    type: str
    responsibility: str
    path: Path
    search: bool = True
    required: bool = True
    group: str = "workspace"


def load_sources(config_path: Path) -> list[Source]:
    resolved_config = config_path.expanduser().resolve()
    payload = _load_payload(resolved_config)

    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("Source registry must contain a 'sources' list.")

    sources: list[Source] = []
    workspace_root = load_workspace_root(resolved_config)
    knowledge_base_root = load_knowledge_base_root(resolved_config)
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict):
            raise ValueError(f"Source entry #{index + 1} must be an object.")

        name = _required_string(raw, "name", index)
        source_type = _required_string(raw, "type", index)
        responsibility = _required_string(raw, "responsibility", index)
        raw_path = _required_string(raw, "path", index)
        group = raw.get("group", "workspace")
        if not isinstance(group, str) or not group.strip():
            raise ValueError(f"Source '{name}' field 'group' must be a non-empty string.")
        group = group.strip()
        if group not in {"workspace", "knowledge_base"}:
            raise ValueError(f"Source '{name}' field 'group' must be one of: workspace, knowledge_base.")
        search = raw.get("search", True)
        if not isinstance(search, bool):
            raise ValueError(f"Source '{name}' field 'search' must be boolean.")
        required = raw.get("required", True)
        if not isinstance(required, bool):
            raise ValueError(f"Source '{name}' field 'required' must be boolean.")

        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            base = knowledge_base_root if group == "knowledge_base" else workspace_root
            path = base / path

        sources.append(
            Source(
                name=name,
                type=source_type,
                responsibility=responsibility,
                path=path.resolve(),
                search=search,
                required=required,
                group=group,
            )
        )

    return sources


def load_workspace_root(config_path: Path) -> Path:
    resolved_config = config_path.expanduser().resolve()
    payload = _load_payload(resolved_config)

    raw_root = payload.get("workspace_root")
    if isinstance(raw_root, str) and raw_root.strip():
        root = Path(raw_root).expanduser()
        if not root.is_absolute():
            root = resolved_config.parent / root
        return root.resolve()

    env_root = os.environ.get("WORKSPACE_OS_GIT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()

    return resolved_config.parent.resolve()


def load_knowledge_base_root(config_path: Path) -> Path:
    resolved_config = config_path.expanduser().resolve()
    payload = _load_payload(resolved_config)

    raw_root = payload.get("knowledge_base_root")
    if isinstance(raw_root, str) and raw_root.strip():
        root = Path(raw_root).expanduser()
        if not root.is_absolute():
            root = resolved_config.parent / root
        return root.resolve()

    env_root = os.environ.get("WORKSPACE_OS_KB_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()

    workspace_root = load_workspace_root(resolved_config)
    return (workspace_root.parent / "kb").resolve()


def load_oce_extension_modules(config_path: Path) -> list[str]:
    resolved_config = config_path.expanduser().resolve()
    payload = _load_payload(resolved_config)

    raw_modules = payload.get("oce_extensions", [])
    if raw_modules is None:
        return []
    if not isinstance(raw_modules, list):
        raise ValueError("Workspace config must contain an 'oce_extensions' list when present.")

    modules: list[str] = []
    for index, raw in enumerate(raw_modules):
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"OCE extension entry #{index + 1} must be a non-empty string.")
        modules.append(raw.strip())
    return modules


def load_workspace_memory_path(config_path: Path) -> Path:
    resolved_config = config_path.expanduser().resolve()
    workspace_root = load_workspace_root(resolved_config)
    payload = _load_payload(resolved_config)

    raw_memory = payload.get("memory_db")
    if isinstance(raw_memory, str) and raw_memory.strip():
        memory_path = Path(raw_memory).expanduser()
        if not memory_path.is_absolute():
            memory_path = workspace_root / memory_path
        return memory_path.resolve()

    env_memory = os.environ.get("WORKSPACE_OS_MEMORY_DB", "").strip()
    if env_memory:
        memory_path = Path(env_memory).expanduser()
        if not memory_path.is_absolute():
            memory_path = workspace_root / memory_path
        return memory_path.resolve()

    return (workspace_root / ".workspace-os" / "workspace-memory.sqlite3").resolve()


def load_allowed_commands(config_path: Path) -> list[str]:
    """Load the list of allowed commands from config.

    Returns a list of command patterns that agents can execute without permission prompts.
    If no allowed_commands is specified in config, returns a safe default whitelist.
    """
    resolved_config = config_path.expanduser().resolve()
    payload = _load_payload(resolved_config)

    raw_commands = payload.get("allowed_commands")
    if raw_commands is None:
        # Safe default whitelist for common read-only and safe commands
        return _get_default_allowed_commands()

    if not isinstance(raw_commands, list):
        raise ValueError("Config field 'allowed_commands' must be a list.")

    commands: list[str] = []
    for index, raw in enumerate(raw_commands):
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"Allowed command entry #{index + 1} must be a non-empty string.")
        commands.append(raw.strip())

    return commands


def _get_default_allowed_commands() -> list[str]:
    """Return a curated list of safe, common commands for agent execution."""
    return [
        # Git read-only operations
        "git status",
        "git log",
        "git diff",
        "git show",
        "git branch",
        "git remote",
        "git ls-files",
        "git blame",
        # File operations (read-only)
        "ls",
        "cat",
        "find",
        "grep",
        "rg",
        "head",
        "tail",
        "wc",
        # Development tools (read-only)
        "npm list",
        "pip list",
        "python --version",
        "node --version",
        "pytest --collect-only",
        # Build/test (safe, non-destructive)
        "pytest",
        "ruff check",
        "mypy",
        "black --check",
    ]


def _required_string(raw: dict[str, object], field: str, index: int) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Source entry #{index + 1} must define non-empty '{field}'.")
    return value.strip()


def _load_payload(config_path: Path) -> dict[str, object]:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Workspace config must be a JSON object.")
    return payload

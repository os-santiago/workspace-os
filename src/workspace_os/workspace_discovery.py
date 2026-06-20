from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import configparser
import json
import os


@dataclass(frozen=True)
class DiscoveredWorkspace:
    name: str
    path: Path
    workspace_type: str  # git, docker, python, node, etc.
    remote_url: str | None = None
    branch: str | None = None
    is_dirty: bool = False
    last_modified: str | None = None
    metadata: dict[str, str] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "type": self.workspace_type,
            "remote_url": self.remote_url,
            "branch": self.branch,
            "is_dirty": self.is_dirty,
            "last_modified": self.last_modified,
            "metadata": self.metadata or {},
        }


def discover_workspaces_in_root(root: Path, max_depth: int = 3) -> Iterator[DiscoveredWorkspace]:
    """
    Discover workspaces (git repos, project directories) under the given root.

    Args:
        root: Root directory to scan
        max_depth: Maximum directory depth to scan (default: 3)

    Yields:
        DiscoveredWorkspace instances for each found workspace
    """
    if not root.exists() or not root.is_dir():
        return

    for item in _scan_directory(root, current_depth=0, max_depth=max_depth):
        yield item


def _scan_directory(path: Path, current_depth: int, max_depth: int) -> Iterator[DiscoveredWorkspace]:
    if current_depth > max_depth:
        return

    # Check if this is a git repository
    git_dir = path / ".git"
    if git_dir.exists():
        workspace = _discover_git_workspace(path)
        if workspace:
            yield workspace
        # Don't descend into git repos
        return

    # Check for other workspace indicators
    if _is_workspace_directory(path):
        workspace = _discover_generic_workspace(path)
        if workspace:
            yield workspace
        # Still descend to find nested workspaces

    # Descend into subdirectories
    try:
        for child in path.iterdir():
            if child.is_dir() and not child.name.startswith(".") and child.name not in {"node_modules", "venv", "__pycache__", "target", "build", "dist"}:
                yield from _scan_directory(child, current_depth + 1, max_depth)
    except PermissionError:
        pass


def _discover_git_workspace(path: Path) -> DiscoveredWorkspace | None:
    try:
        # Read git config for remote URL
        git_config = path / ".git" / "config"
        remote_url = None
        if git_config.exists():
            parser = configparser.ConfigParser()
            parser.read(git_config)
            for section in parser.sections():
                if section.startswith('remote "'):
                    remote_url = parser.get(section, "url", fallback=None)
                    break

        # Get current branch
        head_file = path / ".git" / "HEAD"
        branch = None
        if head_file.exists():
            head_content = head_file.read_text().strip()
            if head_content.startswith("ref: refs/heads/"):
                branch = head_content[len("ref: refs/heads/"):]

        # Check if dirty (has uncommitted changes)
        is_dirty = False
        index_file = path / ".git" / "index"
        if index_file.exists():
            # Simple heuristic: if index was modified recently, likely dirty
            # More accurate would be running git status, but that's expensive
            is_dirty = _has_uncommitted_changes(path)

        return DiscoveredWorkspace(
            name=path.name,
            path=path,
            workspace_type="git",
            remote_url=remote_url,
            branch=branch,
            is_dirty=is_dirty,
            last_modified=_get_last_modified(path),
            metadata={"git_dir": str(path / ".git")},
        )
    except Exception:
        return None


def _discover_generic_workspace(path: Path) -> DiscoveredWorkspace | None:
    workspace_type = _detect_workspace_type(path)
    if not workspace_type:
        return None

    return DiscoveredWorkspace(
        name=path.name,
        path=path,
        workspace_type=workspace_type,
        last_modified=_get_last_modified(path),
    )


def _is_workspace_directory(path: Path) -> bool:
    """Check if a directory contains workspace indicators."""
    indicators = {
        "package.json",  # Node.js
        "pyproject.toml",  # Python
        "Cargo.toml",  # Rust
        "go.mod",  # Go
        "pom.xml",  # Maven
        "build.gradle",  # Gradle
        "docker-compose.yml",  # Docker
        ".project",  # Eclipse
    }
    return any((path / indicator).exists() for indicator in indicators)


def _detect_workspace_type(path: Path) -> str | None:
    """Detect the type of workspace based on project files."""
    if (path / "package.json").exists():
        return "node"
    if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
        return "python"
    if (path / "Cargo.toml").exists():
        return "rust"
    if (path / "go.mod").exists():
        return "go"
    if (path / "pom.xml").exists():
        return "maven"
    if (path / "build.gradle").exists():
        return "gradle"
    if (path / "docker-compose.yml").exists():
        return "docker"
    return None


def _has_uncommitted_changes(path: Path) -> bool:
    """Check if a git repo has uncommitted changes (simple heuristic)."""
    # Check for untracked files or modified index
    # This is a simplified check; full accuracy requires git status
    try:
        # If there are any files in the working tree modified recently
        import subprocess
        result = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def _get_last_modified(path: Path) -> str | None:
    """Get the last modification time of a directory."""
    try:
        from datetime import datetime, timezone
        stat = path.stat()
        dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def filter_workspaces_by_type(workspaces: Iterator[DiscoveredWorkspace], workspace_type: str) -> Iterator[DiscoveredWorkspace]:
    """Filter discovered workspaces by type."""
    return (ws for ws in workspaces if ws.workspace_type == workspace_type)


def filter_workspaces_by_activity(workspaces: Iterator[DiscoveredWorkspace], days: int = 30) -> Iterator[DiscoveredWorkspace]:
    """Filter workspaces modified within the last N days."""
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    for ws in workspaces:
        if ws.last_modified:
            try:
                modified = datetime.fromisoformat(ws.last_modified)
                if modified >= cutoff:
                    yield ws
            except Exception:
                continue


def cache_workspace_discovery(root: Path, cache_path: Path, max_depth: int = 3) -> int:
    """
    Discover workspaces and cache the results for faster subsequent lookups.

    Args:
        root: Root directory to scan
        cache_path: Path to write the cache file
        max_depth: Maximum directory depth to scan

    Returns:
        Number of workspaces discovered and cached
    """
    workspaces = list(discover_workspaces_in_root(root, max_depth=max_depth))
    cache_data = {
        "root": str(root),
        "scanned_at": _get_now_iso(),
        "workspaces": [ws.to_dict() for ws in workspaces],
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)

    return len(workspaces)


def load_workspace_cache(cache_path: Path, max_age_hours: int = 24) -> list[DiscoveredWorkspace] | None:
    """
    Load workspace discovery results from cache if fresh enough.

    Args:
        cache_path: Path to the cache file
        max_age_hours: Maximum age of cache in hours (default: 24)

    Returns:
        List of discovered workspaces if cache is valid, None otherwise
    """
    if not cache_path.exists():
        return None

    try:
        from datetime import datetime, timedelta, timezone

        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        scanned_at = datetime.fromisoformat(cache_data["scanned_at"])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        if scanned_at < cutoff:
            return None

        return [
            DiscoveredWorkspace(
                name=ws["name"],
                path=Path(ws["path"]),
                workspace_type=ws["type"],
                remote_url=ws.get("remote_url"),
                branch=ws.get("branch"),
                is_dirty=ws.get("is_dirty", False),
                last_modified=ws.get("last_modified"),
                metadata=ws.get("metadata"),
            )
            for ws in cache_data["workspaces"]
        ]
    except Exception:
        return None


def _get_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

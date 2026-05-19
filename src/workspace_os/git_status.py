from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from workspace_os.config import Source


@dataclass(frozen=True)
class GitStatus:
    source: Source
    exists: bool
    is_git_repo: bool
    branch: str | None = None
    dirty_count: int = 0
    untracked_count: int = 0
    ahead: int = 0
    behind: int = 0
    error: str | None = None

    @property
    def state(self) -> str:
        if not self.exists:
            return "missing"
        if not self.is_git_repo:
            return "not-git"
        if self.error:
            return "error"
        if self.dirty_count or self.untracked_count:
            return "dirty"
        return "clean"


def inspect_source(source: Source) -> GitStatus:
    if not source.path.exists():
        return GitStatus(source=source, exists=False, is_git_repo=False)

    if not _is_git_repo(source.path):
        return GitStatus(source=source, exists=True, is_git_repo=False)

    try:
        branch = _run_git(source.path, "branch", "--show-current").strip()
        porcelain = _run_git(source.path, "status", "--porcelain=v1").splitlines()
        ahead, behind = _upstream_divergence(source.path)
    except subprocess.CalledProcessError as exc:
        return GitStatus(
            source=source,
            exists=True,
            is_git_repo=True,
            error=(exc.stderr or exc.stdout or str(exc)).strip(),
        )

    dirty_count = 0
    untracked_count = 0
    for line in porcelain:
        if line.startswith("??"):
            untracked_count += 1
        else:
            dirty_count += 1

    return GitStatus(
        source=source,
        exists=True,
        is_git_repo=True,
        branch=branch or "detached",
        dirty_count=dirty_count,
        untracked_count=untracked_count,
        ahead=ahead,
        behind=behind,
    )


def _is_git_repo(path: Path) -> bool:
    try:
        output = _run_git(path, "rev-parse", "--is-inside-work-tree").strip()
    except subprocess.CalledProcessError:
        return False
    return output == "true"


def _upstream_divergence(path: Path) -> tuple[int, int]:
    try:
        upstream = _run_git(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
    except subprocess.CalledProcessError:
        return 0, 0

    output = _run_git(path, "rev-list", "--left-right", "--count", f"HEAD...{upstream}").strip()
    parts = output.split()
    if len(parts) != 2:
        return 0, 0
    return int(parts[0]), int(parts[1])


def _run_git(path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout

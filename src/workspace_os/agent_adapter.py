# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import time
from dataclasses import dataclass
import os
import shlex

from workspace_os.agent_policy import normalize_agent_name
from workspace_os.delegation import build_hardened_delegate_prompt
from workspace_os.memory import WorkspaceMemoryStore


@dataclass(frozen=True)
class AgentExecutionResult:
    agent: str
    command: tuple[str, ...]
    returncode: int
    duration_seconds: float


def build_agent_command(agent: str, workspace_root: Path, prompt: str, extra_args: list[str] | None = None) -> list[str]:
    args = list(extra_args or [])
    normalized_agent = normalize_agent_name(agent) or agent
    if normalized_agent == "opencode":
        # OpenCode - enable autonomous mode for WOS
        return [
            "opencode",
            "run",
            "--model",
            "opencode/deepseek-v4-flash-free",
            "--dir",
            str(workspace_root),
            "--auto-approve",  # Enable unattended execution
            *args,
            prompt,
        ]
    if normalized_agent == "codex":
        return [
            "codex",
            "exec",
            "--cd",
            str(workspace_root),
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "on-request",
            *args,
            prompt,
        ]
    if normalized_agent == "claude":
        # Enable unattended execution for WOS cycles
        # Comprehensive SDLC command whitelist
        allowed_tools = [
            # Git operations
            "Bash(git *)",
            "Bash(gh *)",

            # File operations
            "Bash(ls *)",
            "Bash(cat *)",
            "Bash(head *)",
            "Bash(tail *)",
            "Bash(find *)",
            "Bash(grep *)",
            "Bash(wc *)",
            "Bash(diff *)",
            "Bash(sort *)",
            "Bash(uniq *)",

            # Directory operations
            "Bash(cd *)",
            "Bash(pwd *)",
            "Bash(mkdir *)",
            "Bash(tree *)",

            # Text processing
            "Bash(sed *)",
            "Bash(awk *)",
            "Bash(cut *)",

            # Package managers
            "Bash(npm *)",
            "Bash(yarn *)",
            "Bash(pip *)",
            "Bash(poetry *)",
            "Bash(cargo *)",
            "Bash(go *)",

            # Build tools
            "Bash(make *)",
            "Bash(cmake *)",
            "Bash(mvn *)",
            "Bash(gradle *)",

            # Testing
            "Bash(pytest *)",
            "Bash(jest *)",
            "Bash(mocha *)",
            "Bash(cargo test *)",
            "Bash(go test *)",

            # Linting/Formatting
            "Bash(eslint *)",
            "Bash(prettier *)",
            "Bash(black *)",
            "Bash(ruff *)",
            "Bash(mypy *)",
            "Bash(pylint *)",

            # File editing tools
            "Edit",
            "Write",
            "Read",
            "Glob",
            "Grep",
            "NotebookEdit",

            # Process management
            "Bash(ps *)",
            "Bash(kill *)",
            "Bash(pkill *)",

            # Network/API (safe read-only)
            "Bash(curl *)",
            "Bash(wget *)",

            # Docker (if needed)
            "Bash(docker ps *)",
            "Bash(docker logs *)",
            "Bash(docker inspect *)",

            # System info
            "Bash(which *)",
            "Bash(env *)",
            "Bash(echo *)",
            "Bash(printenv *)",
        ]
        return [
            "claude",
            "--add-dir",
            str(workspace_root),
            "--allowedTools",
            " ".join(allowed_tools),
            "-p",
            *args,
            prompt,
        ]
    if normalized_agent == "antigravity":
        template = os.environ.get("WOS_ANTIGRAVITY_COMMAND", "").strip()
        if template:
            expanded = template.format(
                workspace_root=str(workspace_root),
                prompt=prompt.replace('"', '\\"'),
                workspace=workspace_root.name,
            )
            return shlex.split(expanded)
        return [
            "antigravity",
            "run",
            "--workspace",
            str(workspace_root),
            "--prompt",
            prompt,
        ]
    raise ValueError("Allowed agents are opencode, codex, claude and antigravity.")


def launch_agent(
    agent: str,
    workspace_name: str,
    task: str,
    prompt: str,
    workspace_root: Path,
    memory_store: WorkspaceMemoryStore,
    launcher: object | None = None,
) -> int:
    hardened_prompt = build_hardened_delegate_prompt(agent, workspace_name, workspace_root, prompt)
    command = build_agent_command(agent, workspace_root, hardened_prompt)
    start_process = launcher or _launch_process

    log_dir = Path("C:/Users/sergi/.openclaw/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{task}.log"

    pid = start_process(_prepare_command(command), workspace_root, log_file)
    memory_store.record_agent_launch(agent, task, workspace_name)
    return pid


def run_agent(
    agent: str,
    workspace_name: str,
    task: str,
    prompt: str,
    workspace_root: Path,
    memory_store: WorkspaceMemoryStore,
    launcher: object | None = None,
) -> AgentExecutionResult:
    hardened_prompt = build_hardened_delegate_prompt(agent, workspace_name, workspace_root, prompt)
    command = build_agent_command(agent, workspace_root, hardened_prompt)
    start_process = launcher or _run_process

    log_dir = Path("C:/Users/sergi/.openclaw/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{task}.log"

    # Enhanced observability: Log agent start
    print(f"[agent] START {agent} | task={task} | log={log_file}")
    started_at = time.perf_counter()

    completed = start_process(_prepare_command(command), workspace_root, log_file)
    duration_seconds = max(0.0, time.perf_counter() - started_at)

    # Enhanced observability: Log agent completion with status
    status = "✓" if completed == 0 else "✗"
    print(f"[agent] {status} END {agent} | task={task} | duration={duration_seconds:.1f}s | exit={completed}")

    memory_store.record_agent_launch(agent, task, workspace_name)
    return AgentExecutionResult(agent=agent, command=tuple(command), returncode=int(completed), duration_seconds=duration_seconds)


def _launch_process(command: list[str], cwd: Path, log_file: Path | None = None) -> int:
    command = _prepare_command(command)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    stdout = stderr = subprocess.DEVNULL
    if log_file:
        try:
            f = open(log_file, "w", encoding="utf-8")
            stdout = stderr = f
        except Exception:
            pass

    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        creationflags=creationflags,
    )
    return process.pid


def _run_process(command: list[str], cwd: Path, log_file: Path | None = None) -> int:
    command = _prepare_command(command)

    stdout = stderr = subprocess.DEVNULL
    f = None
    if log_file:
        try:
            f = open(log_file, "w", encoding="utf-8")
            stdout = stderr = f
        except Exception:
            pass

    completed = subprocess.run(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        check=False,
    )
    if f:
        f.close()
    return completed.returncode


def _prepare_command(command: list[str]) -> list[str]:
    if not command:
        return command
    executable = shutil.which(command[0]) or command[0]
    executable_path = Path(executable)
    suffix = executable_path.suffix.lower()
    if suffix in {".cmd", ".bat"}:
        return ["cmd.exe", "/c", executable, *command[1:]]
    return [executable, *command[1:]]

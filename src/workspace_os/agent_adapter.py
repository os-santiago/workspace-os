from __future__ import annotations

from pathlib import Path
import subprocess
import time
from dataclasses import dataclass

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
    if agent == "opencode":
        return [
            "opencode",
            "run",
            "--model",
            "opencode/deepseek-v4-flash-free",
            "--dir",
            str(workspace_root),
            "--dangerously-skip-permissions",
            "--prompt",
            *args,
            prompt,
        ]
    if agent == "codex":
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
    if agent == "claude":
        return [
            "claude",
            "--allow-dangerously-skip-permissions",
            "--add-dir",
            str(workspace_root),
            "-p",
            *args,
            prompt,
        ]
    raise ValueError("Allowed agents are opencode, codex and claude.")


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
    pid = start_process(command, workspace_root)
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
    started_at = time.perf_counter()
    completed = start_process(command, workspace_root)
    duration_seconds = max(0.0, time.perf_counter() - started_at)
    memory_store.record_agent_launch(agent, task, workspace_name)
    return AgentExecutionResult(agent=agent, command=tuple(command), returncode=int(completed), duration_seconds=duration_seconds)


def _launch_process(command: list[str], cwd: Path) -> int:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return process.pid


def _run_process(command: list[str], cwd: Path) -> int:
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode

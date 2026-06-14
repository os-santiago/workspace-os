from __future__ import annotations

from pathlib import Path
import subprocess

from workspace_os.memory import WorkspaceMemoryStore


def build_agent_command(agent: str, workspace_root: Path, prompt: str, extra_args: list[str] | None = None) -> list[str]:
    args = list(extra_args or [])
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
    raise ValueError("Allowed agents are codex and claude.")


def launch_agent(
    agent: str,
    workspace_name: str,
    task: str,
    prompt: str,
    workspace_root: Path,
    memory_store: WorkspaceMemoryStore,
    launcher: object | None = None,
) -> int:
    command = build_agent_command(agent, workspace_root, prompt)
    start_process = launcher or _launch_process
    pid = start_process(command, workspace_root)
    memory_store.record_agent_launch(agent, task, workspace_name)
    return pid


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

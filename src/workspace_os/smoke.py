from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
import subprocess
import tempfile

from workspace_os.batch import start_batch, start_process
from workspace_os.cli import main
from workspace_os.config import Source
from workspace_os.conversation import build_workspace_reply
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.shell import WorkspaceShell


@dataclass(frozen=True)
class SmokeCheckResult:
    name: str
    passed: bool
    detail: str


def run_smoke_regression_checks() -> list[SmokeCheckResult]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_root = root / "workspace-os"
        source_root.mkdir()
        _init_git_repo(source_root)

        config = root / "workspace.json"
        memory = root / "memory.sqlite3"
        config.write_text(
            """
{
  "workspace_root": ".",
  "memory_db": "memory.sqlite3",
  "sources": [
    {
      "name": "workspace-os",
      "type": "product",
      "responsibility": "Workspace OS.",
      "path": "workspace-os",
      "search": true
    }
  ]
}
""".strip(),
            encoding="utf-8",
        )

        store = WorkspaceMemoryStore(memory)
        store.ensure_schema()
        start_process(store, "process-1", "smoke query flow", started_at="2026-06-14T10:00:00+00:00")
        start_batch(store, "batch-1", "smoke query batch", started_at="2026-06-14T10:05:00+00:00")
        store.record_decision(
            "hash-1",
            "medium",
            "SAFE_REDIRECT",
            ["missing_workspace"],
            primary_agent="codex",
            secondary_agent="claude",
            routing_reason="workspace_inventory_first",
        )

        source = Source("workspace-os", "product", "Workspace OS.", source_root)
        results: list[SmokeCheckResult] = []
        results.extend(_run_chat_checks(source, store))
        results.extend(_run_cli_checks(config))
        results.extend(_run_shell_checks(source, memory))
        return results


def _run_chat_checks(source: Source, store: WorkspaceMemoryStore) -> list[SmokeCheckResult]:
    cases = [
        (
            "chat:hola",
            "hola",
            [
                "Hola. Soy WOS",
            ],
        ),
        (
            "chat:app-overview",
            "que hace esta aplicacion?",
            [
                "Workspace OS is your local workspace control plane.",
                "routes ambiguous work through OCE",
                "/oce",
            ],
        ),
        (
            "chat:projects",
            "que proyectos tenemos en curso?",
            [
                "Workspace status:",
                "Workspace root:",
                "Projects under root:",
                "Next step: record the first process checkpoint",
                "Primary route: /codex",
                "Optional cross-check: /claude",
            ],
        ),
        (
            "chat:repetition",
            "respondes siempre lo mismo?",
            [
                "No. I now answer by intent instead of repeating the same fallback.",
                "route it to Codex first",
            ],
        ),
        (
            "chat:next",
            "what should we do next?",
            [
                "Primary route: /codex",
                "Optional cross-check: /claude",
            ],
        ),
    ]

    results: list[SmokeCheckResult] = []
    for name, message, expectations in cases:
        reply = build_workspace_reply(
            [source],
            message,
            memory_store=store,
            session_id="smoke",
            tone="terse",
            detail_level="minimal",
        )
        missing = [expectation for expectation in expectations if expectation not in reply.reply]
        if missing:
            results.append(
                SmokeCheckResult(
                    name,
                    False,
                    f"Missing expected fragments: {', '.join(missing)}",
                )
            )
            continue
        results.append(SmokeCheckResult(name, True, "Expected operational guidance present."))
    return results


def _run_cli_checks(config: Path) -> list[SmokeCheckResult]:
    results: list[SmokeCheckResult] = []
    for name, argv, expectations in [
        (
            "cli:next",
            ["--config", str(config), "next"],
            ["Workspace next action:", "Suggested command:"],
        ),
        (
            "cli:oce-status",
            ["--config", str(config), "oce", "status"],
            ["OCE report", "recommended_next_action"],
        ),
    ]:
        rendered, exit_code = _capture_main(argv)
        if exit_code != 0:
            results.append(SmokeCheckResult(name, False, f"Command failed with exit code {exit_code}."))
            continue
        missing = [expectation for expectation in expectations if expectation not in rendered]
        if missing:
            results.append(
                SmokeCheckResult(
                    name,
                    False,
                    f"Missing expected fragments: {', '.join(missing)}",
                )
            )
            continue
        results.append(SmokeCheckResult(name, True, "Command surface returned expected output."))
    return results


def _run_shell_checks(source: Source, memory: Path) -> list[SmokeCheckResult]:
    shell = WorkspaceShell([source], memory)
    with StringIO() as buffer:
        with redirect_stdout(buffer):
            shell.do_next("")
            shell.do_oce("status 5")
            shell.default("que proyectos tenemos en curso?")
        rendered = buffer.getvalue()
    expectations = [
        ("shell:next", "Workspace next action:"),
        ("shell:oce", "OCE report"),
        ("shell:reply", "Primary route: /codex"),
        ("shell:route", "Optional cross-check: /claude"),
    ]
    results: list[SmokeCheckResult] = []
    for name, expectation in expectations:
        if expectation not in rendered:
            results.append(SmokeCheckResult(name, False, f"Missing expected fragment: {expectation}"))
            continue
        results.append(SmokeCheckResult(name, True, "Shell surface returned expected output."))
    return results


def _capture_main(argv: list[str]) -> tuple[str, int]:
    with StringIO() as buffer:
        with redirect_stdout(buffer):
            exit_code = main(argv)
        return buffer.getvalue(), exit_code


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "workspace@example.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Workspace"], cwd=path, check=True, capture_output=True)
    (path / ".gitignore").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)

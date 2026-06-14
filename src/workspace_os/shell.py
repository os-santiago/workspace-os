from __future__ import annotations

import cmd
from pathlib import Path
import shlex
import sys

from workspace_os.capture import build_capture_draft, write_capture
from workspace_os.classification import classify_content
from workspace_os.config import Source
from workspace_os.conversation import build_workspace_reply
from workspace_os.context_pack import build_context_pack
from workspace_os.git_status import inspect_source
from workspace_os.housekeeping import find_temporary_artifacts
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.promotion import build_promotion_proposal
from workspace_os.sanitization import sanitize_text
from workspace_os.search import search_sources
from workspace_os.validation import validate_workspace, validation_failed


class WorkspaceShell(cmd.Cmd):
    intro = "Workspace OS shell. Type /help for commands, /exit to leave."
    ruler = "-"

    def __init__(self, sources: list[Source], memory_path: Path, session_id: str = "shell"):
        super().__init__()
        self.sources = sources
        self.memory_store = WorkspaceMemoryStore(memory_path)
        self.memory_store.ensure_schema()
        self.session_id = session_id
        self.active_workspace: str | None = None
        self.prompt = self._render_prompt()

    def parseline(self, line: str):
        stripped = self._normalize_line(line)
        if stripped.startswith("/"):
            stripped = stripped[1:]
        return super().parseline(stripped)

    def precmd(self, line: str) -> str:
        stripped = self._normalize_line(line)
        if stripped.startswith("/"):
            return stripped[1:]
        return stripped

    def default(self, line: str) -> None:
        message = line.strip()
        if not message:
            return
        reply = build_workspace_reply(
            self._selected_sources(),
            message,
            memory_store=self.memory_store,
            session_id=self.session_id,
        )
        print(reply.reply)
        self.prompt = self._render_prompt()

    def do_help(self, arg: str) -> None:
        print(
            "\n".join(
                [
                    "Workspace OS shell commands:",
                    "/ws <name>          switch active workspace",
                    "/workspaces         list configured workspaces",
                    "/status             show active workspace status",
                    "/search <query>     search configured sources",
                    "/context <topic>    build governed context pack",
                    "/classify <text>    classify content destination",
                    "/validate           validate workspace health",
                    "/capture <type>     capture session/incident/decision/daily notes",
                    "/promote <target>   promote rule to ADEV/kb",
                    "/memory [query]     search persistent memory",
                    "/exit               exit shell",
                    "",
                    "Free text is treated as a chat message and recorded in memory.",
                ]
            )
        )

    def do_exit(self, arg: str) -> bool:
        return True

    def do_ws(self, arg: str) -> None:
        name = arg.strip()
        if not name:
            self._print_workspaces()
            return
        if not any(source.name == name for source in self.sources):
            print(f"Unknown workspace: {name}")
            return
        self.active_workspace = name
        self.prompt = self._render_prompt()
        print(f"active workspace={name}")

    def do_workspaces(self, arg: str) -> None:
        self._print_workspaces()

    def do_status(self, arg: str) -> None:
        self._print_status()

    def do_search(self, arg: str) -> None:
        query = arg.strip()
        if not query:
            print("Usage: /search <query>")
            return
        matches = search_sources(self._selected_sources(), query, max_results=20)
        for match in matches:
            print(f"{match.source_name}:{match.path}:{match.line_number}: {sanitize_text(match.line)}")
        if not matches:
            print("No matches found.")

    def do_context(self, arg: str) -> None:
        topic = arg.strip()
        if not topic:
            print("Usage: /context <topic>")
            return
        pack = build_context_pack(
            sources=self.sources,
            topic=topic,
            memory_path=self.memory_store.path,
        )
        print(pack.render_markdown(), end="")

    def do_classify(self, arg: str) -> None:
        value = arg.strip()
        if not value:
            print("Usage: /classify <text>")
            return
        classification = classify_content(value)
        print(f"target={classification.target}")
        print(f"confidence={classification.confidence}")
        print(f"reason={classification.reason}")

    def do_validate(self, arg: str) -> None:
        results = validate_workspace(self.sources)
        for result in results:
            state = "PASS" if result.passed else "FAIL"
            print(f"{state} {result.name}: {result.detail}")
        if validation_failed(results):
            print("validation_failed=true")

    def do_capture(self, arg: str) -> None:
        parts = shlex.split(arg)
        if len(parts) < 2:
            print("Usage: /capture <type> <title> | /capture <type> --title <title>")
            return
        capture_type = parts[0]
        title = " ".join(parts[1:]).strip()
        try:
            draft = build_capture_draft(self.sources, capture_type, title, "")
        except (OSError, ValueError) as exc:
            print(f"error: {exc}")
            return
        print("dry_run=true")
        print(f"target={draft.source_name}:{draft.relative_path}")
        print("")
        print(draft.content, end="")

    def do_promote(self, arg: str) -> None:
        parts = shlex.split(arg)
        if len(parts) < 2:
            print("Usage: /promote <target> <rule>")
            return
        target = parts[0]
        rule = " ".join(parts[1:]).strip()
        try:
            proposal = build_promotion_proposal(
                sources=self.sources,
                target=target,
                rule=rule,
                evidence="workspace-shell",
            )
        except ValueError as exc:
            print(f"error: {exc}")
            return
        print(proposal.render_markdown(), end="")

    def do_memory(self, arg: str) -> None:
        query = arg.strip()
        hits = self.memory_store.search(query, limit=10) if query else self.memory_store.recent(limit=10)
        for hit in hits:
            print(hit.render())
        if not hits:
            print("No memory entries found.")

    def do_chat(self, arg: str) -> None:
        message = arg.strip()
        if not message:
            print("Usage: /chat <message>")
            return
        reply = build_workspace_reply(
            self._selected_sources(),
            message,
            memory_store=self.memory_store,
            session_id=self.session_id,
        )
        print(reply.reply)

    def _print_workspaces(self) -> None:
        for source in self.sources:
            marker = "*" if source.name == self.active_workspace else " "
            print(f"{marker} {source.name:16} {source.type:10} {source.path}")

    def _print_status(self) -> None:
        for status in [inspect_source(source) for source in self._selected_sources()]:
            source = status.source
            print(
                f"{source.name:16} {source.type:10} {status.state:8} "
                f"branch={status.branch} changes={status.dirty_count} "
                f"untracked={status.untracked_count} ahead={status.ahead} behind={status.behind}"
            )

    def _selected_sources(self) -> list[Source]:
        if not self.active_workspace:
            return self.sources
        return [source for source in self.sources if source.name == self.active_workspace]

    def _render_prompt(self) -> str:
        active = self.active_workspace or "all"
        return f"workspace[{active}]> "

    def _normalize_line(self, line: str) -> str:
        return line.lstrip("\ufeff").strip()

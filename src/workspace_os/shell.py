from __future__ import annotations

import cmd
from pathlib import Path
import shlex

from workspace_os.agent_adapter import launch_agent
from workspace_os.batch import current_batch_report, start_batch, stop_batch
from workspace_os.capture import build_capture_draft
from workspace_os.classification import classify_content
from workspace_os.config import Source
from workspace_os.conversation import build_workspace_reply
from workspace_os.context_pack import build_context_pack
from workspace_os.git_status import inspect_source
from workspace_os.habits import compute_habits
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.promotion import build_promotion_proposal
from workspace_os.profile import load_profile, save_profile_key, save_shortcut
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
        self.profile = load_profile(self.memory_store)
        self.habits = compute_habits(self.memory_store, self.profile)
        self.session_id = session_id
        self.active_workspace: str | None = self.profile.default_workspace
        if self.active_workspace and not any(source.name == self.active_workspace for source in self.sources):
            self.active_workspace = None
        self.active_batch = self.memory_store.active_batch()
        self.intro = (
            f"Workspace OS shell. {self.habits.render_summary()}\n"
            f"{self._render_batch_banner()}"
            "Type /help for commands, /exit to leave."
        )
        self.prompt = self._render_prompt()

    def parseline(self, line: str):
        stripped = self._normalize_line(line)
        if stripped.startswith("/"):
            stripped = stripped[1:]
        return super().parseline(stripped)

    def precmd(self, line: str) -> str:
        return self._expand_alias(self._normalize_line(line))

    def default(self, line: str) -> None:
        message = line.strip()
        if not message:
            return
        reply = build_workspace_reply(
            self._selected_sources(),
            message,
            memory_store=self.memory_store,
            session_id=self.session_id,
            tone=self.profile.tone,
            detail_level=self.profile.detail_level,
        )
        print(reply.reply)
        self.habits = compute_habits(self.memory_store, self.profile)
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
                    "/profile [k v]      get or set profile values",
                    "/habits             show inferred operator habits",
                    "/batch ...          start, stop, report, status, or list batches",
                    "/alias ...          save, list, or invoke shortcuts",
                    "/codex <task>       launch codex with the active workspace",
                    "/claude <task>      launch claude with the active workspace",
                    "/launches           show recent agent launches",
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

    def do_profile(self, arg: str) -> None:
        parts = shlex.split(arg)
        if not parts:
            self._print_profile()
            return
        if len(parts) < 2:
            print("Usage: /profile <key> <value>")
            return
        key = parts[0].strip()
        value = " ".join(parts[1:]).strip()
        if key not in {"tone", "detail_level", "default_workspace"}:
            print("Supported keys: tone, detail_level, default_workspace")
            return
        save_profile_key(self.memory_store, key, value)
        self.profile = load_profile(self.memory_store)
        self.habits = compute_habits(self.memory_store, self.profile)
        if key == "default_workspace":
            self.active_workspace = value or None
            if self.active_workspace and not any(source.name == self.active_workspace for source in self.sources):
                self.active_workspace = None
        self.prompt = self._render_prompt()
        print(f"saved profile {key}")

    def do_alias(self, arg: str) -> None:
        parts = shlex.split(arg)
        if not parts:
            self._print_aliases()
            return
        if len(parts) == 1:
            alias = parts[0]
            command = self.profile.shortcuts.get(alias)
            if command is None:
                print("No alias found.")
                return
            print(f"{alias}={command}")
            return
        alias = parts[0]
        command = " ".join(parts[1:])
        save_shortcut(self.memory_store, alias, command)
        self.profile = load_profile(self.memory_store)
        self.habits = compute_habits(self.memory_store, self.profile)
        print(f"saved alias {alias}")

    def do_habits(self, arg: str) -> None:
        habits = compute_habits(self.memory_store, self.profile)
        print(habits.render_full(), end="")

    def do_batch(self, arg: str) -> None:
        parts = shlex.split(arg)
        if not parts:
            self._print_batch_status()
            return
        command = parts[0].casefold()
        if command == "start":
            if len(parts) < 3:
                print("Usage: /batch start <label> <objective>")
                return
            label = parts[1]
            objective = " ".join(parts[2:]).strip()
            try:
                batch_id = start_batch(self.memory_store, label, objective)
            except ValueError as exc:
                print(f"error: {exc}")
                return
            self.active_batch = self.memory_store.active_batch()
            print(f"batch_started={batch_id}")
            return
        if command == "stop":
            report = stop_batch(self.memory_store)
            self.active_batch = self.memory_store.active_batch()
            if report is None:
                print("No active batch found.")
                return
            print(report.render(), end="")
            return
        if command == "report":
            batch_id = int(parts[1]) if len(parts) > 1 else None
            report = current_batch_report(self.memory_store, batch_id=batch_id)
            if report is None:
                print("No batch found.")
                return
            print(report.render(), end="")
            return
        if command == "status":
            self._print_batch_status()
            return
        if command == "history":
            self._print_batch_history()
            return
        print("Usage: /batch <start|stop|report|status|history>")

    def do_codex(self, arg: str) -> None:
        self._launch_agent("codex", arg)

    def do_claude(self, arg: str) -> None:
        self._launch_agent("claude", arg)

    def do_launches(self, arg: str) -> None:
        launches = self.memory_store.recent_launches(limit=10)
        for launch in launches:
            print(
                f"- {launch['agent']} {launch['workspace'] or 'all'}: {launch['task']} "
                f"({launch['launched_at']})"
            )
        if not launches:
            print("No agent launches found.")

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
            tone=self.profile.tone,
            detail_level=self.profile.detail_level,
        )
        print(reply.reply)
        self.habits = compute_habits(self.memory_store, self.profile)

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

    def _print_profile(self) -> None:
        print(f"tone={self.profile.tone}")
        print(f"detail_level={self.profile.detail_level}")
        print(f"default_workspace={self.profile.default_workspace or ''}")

    def _print_aliases(self) -> None:
        if not self.profile.shortcuts:
            print("No aliases saved.")
            return
        for name, command in sorted(self.profile.shortcuts.items()):
            print(f"{name}={command}")

    def _launch_agent(self, agent: str, arg: str) -> None:
        task = arg.strip()
        if not task:
            print(f"Usage: /{agent} <task>")
            return
        workspace = self._active_workspace_source()
        if workspace is None:
            print("No active workspace selected.")
            return
        prompt = self._build_agent_prompt(agent, task)
        try:
            pid = launch_agent(
                agent=agent,
                workspace_name=workspace.name,
                task=task,
                prompt=prompt,
                workspace_root=workspace.path,
                memory_store=self.memory_store,
            )
        except (OSError, ValueError) as exc:
            print(f"error: {exc}")
            return
        self.habits = compute_habits(self.memory_store, self.profile)
        print(f"launched={agent}:{pid}")

    def _build_agent_prompt(self, agent: str, task: str) -> str:
        return "\n".join(
            [
                f"Workspace OS shell delegation for {agent}.",
                f"Active workspace: {self.active_workspace or 'all'}",
                f"Tone: {self.profile.tone}",
                f"Detail level: {self.profile.detail_level}",
                "Follow ADEV rules and preserve unrelated local changes.",
                "Use the selected workspace only.",
                "",
                "Task:",
                task,
            ]
        )

    def _active_workspace_source(self) -> Source | None:
        if self.active_workspace:
            for source in self.sources:
                if source.name == self.active_workspace:
                    return source
        return self.sources[0] if self.sources else None

    def _selected_sources(self) -> list[Source]:
        if not self.active_workspace:
            return self.sources
        return [source for source in self.sources if source.name == self.active_workspace]

    def _render_prompt(self) -> str:
        active = self.active_workspace or "all"
        return f"workspace[{active}]> "

    def _render_batch_banner(self) -> str:
        if self.active_batch is None:
            return "Batch: none\n"
        batch = self.active_batch
        return (
            "Batch: "
            f"{batch['label']} | objective={batch['objective']} | started={batch['started_at']}\n"
        )

    def _print_batch_status(self) -> None:
        report = current_batch_report(self.memory_store)
        if report is None:
            print("No active batch found.")
            return
        print(report.render(), end="")

    def _print_batch_history(self) -> None:
        batches = self.memory_store.batch_history(limit=5)
        for batch in batches:
            print(
                f"- {batch['id']} {batch['label']}: {batch['objective']} "
                f"({batch['started_at']} -> {batch['ended_at'] or 'active'})"
            )
        if not batches:
            print("No batches found.")

    def _normalize_line(self, line: str) -> str:
        return line.lstrip("\ufeff").strip()

    def _expand_alias(self, line: str) -> str:
        if not line:
            return line
        parts = shlex.split(line)
        if not parts:
            return line
        replacement = self.profile.shortcuts.get(parts[0])
        if not replacement:
            return line
        remainder = " ".join(parts[1:])
        return f"{replacement} {remainder}".strip()

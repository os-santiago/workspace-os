from __future__ import annotations

import argparse
from pathlib import Path
import sys

from workspace_os.capture import build_capture_draft, write_capture
from workspace_os.classification import classify_content
from workspace_os.config import Source, load_sources, load_workspace_memory_path
from workspace_os.conversation import build_workspace_reply
from workspace_os.context_pack import build_context_pack
from workspace_os.git_status import inspect_source
from workspace_os.housekeeping import find_temporary_artifacts
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.promotion import build_promotion_proposal
from workspace_os.sanitization import sanitize_text
from workspace_os.search import search_sources
from workspace_os.shell import WorkspaceShell
from workspace_os.validation import validate_workspace, validation_failed
from workspace_os.web_server import serve_web_app


DEFAULT_CONFIG = Path("config/workspace.sources.example.json")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        sources = load_sources(args.config)
        memory_path = load_workspace_memory_path(args.config)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "status":
        return _status(sources)
    if args.command == "search":
        return _search(sources, args.query, args.source_type, args.max_results)
    if args.command == "housekeeping":
        return _housekeeping(sources, args.max_results)
    if args.command == "context":
        return _context(sources, memory_path, args.topic, args.max_matches, args.max_doctrine_lines)
    if args.command == "classify":
        return _classify(args.value, args.path)
    if args.command == "validate":
        return _validate(sources, args.skip_housekeeping)
    if args.command == "capture":
        return _capture(sources, args.capture_type, args.title, args.text, args.file, args.write)
    if args.command == "promote":
        return _promote(sources, args.target, args.rule, args.evidence, args.max_matches)
    if args.command == "chat":
        return _chat(sources, memory_path, args.message, args.session_id, args.interactive)
    if args.command == "memory":
        return _memory(memory_path, args.memory_command, args)
    if args.command == "shell":
        return _shell(sources, memory_path, args.session_id)
    if args.command == "web":
        return _web(args.config, args.host, args.port)

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workspace", description="Workspace OS local controller.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to the workspace source registry.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Report source repository status without mutation.")

    search_parser = subparsers.add_parser("search", help="Search configured workspace sources.")
    search_parser.add_argument("query", help="Text to search for.")
    search_parser.add_argument("--source-type", help="Limit search to a source type.")
    search_parser.add_argument("--max-results", type=int, default=100, help="Maximum matches to print.")

    housekeeping_parser = subparsers.add_parser(
        "housekeeping",
        help="Report temporary artifacts without deleting files.",
    )
    housekeeping_parser.add_argument("--max-results", type=int, default=100, help="Maximum findings to print.")

    context_parser = subparsers.add_parser(
        "context",
        help="Build a governed Markdown context pack for an agent task.",
    )
    context_parser.add_argument("topic", help="Task topic used to search existing knowledge.")
    context_parser.add_argument("--max-matches", type=int, default=20, help="Maximum knowledge matches to include.")
    context_parser.add_argument(
        "--max-doctrine-lines",
        type=int,
        default=80,
        help="Maximum lines to include from the doctrine source.",
    )

    classify_parser = subparsers.add_parser(
        "classify",
        help="Classify text or a file path into the workspace responsibility model.",
    )
    classify_parser.add_argument("value", help="Text or file path to classify.")
    classify_parser.add_argument("--path", action="store_true", help="Treat value as a file path.")

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate workspace configuration and source health.",
    )
    validate_parser.add_argument(
        "--skip-housekeeping",
        action="store_true",
        help="Skip temporary artifact checks.",
    )

    capture_parser = subparsers.add_parser(
        "capture",
        help="Create a sanitized knowledge capture draft.",
    )
    capture_parser.add_argument("--type", dest="capture_type", required=True, help="Capture type.")
    capture_parser.add_argument("--title", required=True, help="Capture title.")
    capture_input = capture_parser.add_mutually_exclusive_group(required=True)
    capture_input.add_argument("--text", help="Capture body text.")
    capture_input.add_argument("--file", type=Path, help="Read capture body from a text file.")
    capture_parser.add_argument("--write", action="store_true", help="Write to the configured evidence source.")

    promote_parser = subparsers.add_parser(
        "promote",
        help="Generate a non-mutating promotion proposal.",
    )
    promote_parser.add_argument("--to", dest="target", required=True, help="Promotion target.")
    promote_parser.add_argument("--rule", required=True, help="Proposed reusable rule or learning.")
    promote_parser.add_argument("--evidence", required=True, help="Evidence reference supporting the rule.")
    promote_parser.add_argument("--max-matches", type=int, default=10, help="Maximum related matches to include.")

    chat_parser = subparsers.add_parser(
        "chat",
        help="Open a terminal conversation that records memory and returns governed replies.",
    )
    chat_parser.add_argument("message", nargs="?", help="Single message to process without entering interactive mode.")
    chat_parser.add_argument("--session-id", default="default", help="Memory session identifier.")
    chat_parser.add_argument(
        "--interactive",
        action="store_true",
        help="Force interactive mode even when a single message is provided.",
    )

    memory_parser = subparsers.add_parser(
        "memory",
        help="Inspect or seed the persistent workspace memory store.",
    )
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)

    memory_status = memory_subparsers.add_parser("status", help="Show memory store location and row counts.")
    memory_status.add_argument("--limit", type=int, default=5, help="Reserved for future memory summaries.")

    preference_parser = memory_subparsers.add_parser("preference", help="Read or write operator preferences.")
    preference_subparsers = preference_parser.add_subparsers(dest="preference_command", required=True)
    preference_set = preference_subparsers.add_parser("set", help="Store a preference key/value pair.")
    preference_set.add_argument("key", help="Preference key.")
    preference_set.add_argument("value", help="Preference value.")
    preference_get = preference_subparsers.add_parser("get", help="Read a preference by key.")
    preference_get.add_argument("key", help="Preference key.")

    lesson_parser = memory_subparsers.add_parser("lesson", help="Store reusable lessons.")
    lesson_subparsers = lesson_parser.add_subparsers(dest="lesson_command", required=True)
    lesson_add = lesson_subparsers.add_parser("add", help="Add a reusable lesson.")
    lesson_add.add_argument("--category", required=True, help="Lesson category.")
    lesson_add.add_argument("--rule", required=True, help="Lesson or rule text.")
    lesson_add.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Evidence reference supporting the lesson. Repeat for multiple references.",
    )
    lesson_add.add_argument("--confidence", type=float, default=0.7, help="Confidence between 0 and 1.")

    outcome_parser = memory_subparsers.add_parser("outcome", help="Store task outcomes.")
    outcome_subparsers = outcome_parser.add_subparsers(dest="outcome_command", required=True)
    outcome_add = outcome_subparsers.add_parser("add", help="Add a task outcome.")
    outcome_add.add_argument("--task-type", required=True, help="Task type.")
    outcome_add.add_argument("--context-hash", required=True, help="Stable context hash.")
    outcome_add.add_argument("--outcome", required=True, choices=["success", "failure", "partial"], help="Outcome.")
    outcome_add.add_argument("--evidence-ref", help="Optional evidence reference.")

    shell_parser = subparsers.add_parser(
        "shell",
        help="Open the terminal-first Workspace OS shell.",
    )
    shell_parser.add_argument("--session-id", default="shell", help="Memory session identifier.")

    web_parser = subparsers.add_parser(
        "web",
        help="Run the local Workspace OS web pilot.",
    )
    web_parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    web_parser.add_argument("--port", type=int, default=8765, help="Bind port.")

    return parser


def _status(sources: list[Source]) -> int:
    for status in [inspect_source(source) for source in sources]:
        source = status.source
        if status.state == "missing":
            print(f"{source.name:16} {source.type:10} missing    {source.path}")
            continue
        if status.state == "not-git":
            print(f"{source.name:16} {source.type:10} not-git    {source.path}")
            continue
        if status.state == "error":
            print(f"{source.name:16} {source.type:10} error      {status.error}")
            continue

        divergence = ""
        if status.ahead or status.behind:
            divergence = f" ahead={status.ahead} behind={status.behind}"

        print(
            f"{source.name:16} {source.type:10} {status.state:8} "
            f"branch={status.branch} changes={status.dirty_count} "
            f"untracked={status.untracked_count}{divergence}"
        )
    return 0


def _search(sources: list[Source], query: str, source_type: str | None, max_results: int) -> int:
    matches = search_sources(
        sources=sources,
        query=query,
        source_type=source_type,
        max_results=max_results,
    )
    for match in matches:
        print(f"{match.source_name}:{match.path}:{match.line_number}: {sanitize_text(match.line)}")
    if not matches:
        print("No matches found.")
    return 0


def _housekeeping(sources: list[Source], max_results: int) -> int:
    findings = find_temporary_artifacts(sources=sources, max_results=max_results)
    for finding in findings:
        print(f"{finding.source_name}:{finding.path}: matches {finding.pattern}")
    if not findings:
        print("No temporary artifacts found.")
    return 0


def _context(
    sources: list[Source],
    memory_path: Path,
    topic: str,
    max_matches: int,
    max_doctrine_lines: int,
) -> int:
    pack = build_context_pack(
        sources=sources,
        topic=topic,
        max_matches=max_matches,
        max_doctrine_lines=max_doctrine_lines,
        memory_path=memory_path,
    )
    print(pack.render_markdown(), end="")
    return 0


def _classify(value: str, is_path: bool) -> int:
    classification = classify_content(value, is_path=is_path)
    print(f"target={classification.target}")
    print(f"confidence={classification.confidence}")
    print(f"reason={classification.reason}")
    return 0


def _validate(sources: list[Source], skip_housekeeping: bool) -> int:
    results = validate_workspace(sources=sources, include_housekeeping=not skip_housekeeping)
    for result in results:
        state = "PASS" if result.passed else "FAIL"
        print(f"{state} {result.name}: {result.detail}")
    return 1 if validation_failed(results) else 0


def _capture(
    sources: list[Source],
    capture_type: str,
    title: str,
    text: str | None,
    file_path: Path | None,
    write: bool,
) -> int:
    try:
        body = _read_capture_body(text, file_path)
        draft = build_capture_draft(sources, capture_type, title, body)
        if write:
            write_capture(draft)
            print(f"written={draft.source_name}:{draft.relative_path}")
            return 0
        print(f"dry_run=true")
        print(f"target={draft.source_name}:{draft.relative_path}")
        print("")
        print(draft.content, end="")
        return 0
    except (OSError, ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _read_capture_body(text: str | None, file_path: Path | None) -> str:
    if text is not None:
        return text
    if file_path is None:
        raise ValueError("Capture requires text or file input.")
    return file_path.read_text(encoding="utf-8")


def _promote(sources: list[Source], target: str, rule: str, evidence: str, max_matches: int) -> int:
    try:
        proposal = build_promotion_proposal(
            sources=sources,
            target=target,
            rule=rule,
            evidence=evidence,
            max_matches=max_matches,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(proposal.render_markdown(), end="")
    return 0


def _chat(sources: list[Source], memory_path: Path, message: str | None, session_id: str, interactive: bool) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()

    if message and not interactive:
        reply = build_workspace_reply(sources, message, memory_store=store, session_id=session_id)
        print(reply.reply)
        return 0

    print("Workspace OS chat. Type `exit` to leave.")
    while True:
        try:
            prompt = input("> ").strip()
        except EOFError:
            break
        if not prompt:
            continue
        if prompt.casefold() in {"exit", "quit"}:
            break
        reply = build_workspace_reply(sources, prompt, memory_store=store, session_id=session_id)
        print(reply.reply)
        print("")
    return 0


def _memory(memory_path: Path, command: str, args: argparse.Namespace) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()

    if command == "status":
        print(f"path={memory_path}")
        for name, count in store.stats().items():
            print(f"{name}={count}")
        return 0

    if command == "preference":
        if args.preference_command == "set":
            store.record_preference(args.key, args.value)
            print(f"saved preference {args.key}")
            return 0
        if args.preference_command == "get":
            value = store.get_preference(args.key)
            if value is None:
                print("No preference found.")
                return 0
            print(f"{args.key}={value}")
            return 0

    if command == "lesson" and args.lesson_command == "add":
        store.record_lesson(args.category, args.rule, args.evidence, args.confidence)
        print(f"saved lesson {args.category}")
        return 0

    if command == "outcome" and args.outcome_command == "add":
        store.record_task_outcome(args.task_type, args.context_hash, args.outcome, args.evidence_ref)
        print(f"saved outcome {args.task_type}")
        return 0

    print("error: unsupported memory command", file=sys.stderr)
    return 2


def _shell(sources: list[Source], memory_path: Path, session_id: str) -> int:
    shell = WorkspaceShell(sources=sources, memory_path=memory_path, session_id=session_id)
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("")
    return 0


def _web(config_path: Path, host: str, port: int) -> int:
    serve_web_app(config_path=config_path, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

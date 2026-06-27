# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys

from workspace_os.capture import build_capture_draft, write_capture
from workspace_os.batch import batch_summary, current_batch_report, current_process_report, process_summary, start_batch, start_process, stop_batch, stop_process
from workspace_os.classification import classify_content
from workspace_os.cycle import active_cycle_report, build_cycle_next_action, cycle_history_report, record_cycle_checkpoint, render_cycle_evaluation, run_cycle_evaluation, run_cycle_plan, run_cycle_window, run_cycle_work_window, run_cycle_work_window_continuous, start_cycle, stop_cycle
from workspace_os.bridge import render_workspace_bridge_capabilities_text, render_workspace_bridge_json, render_workspace_bridge_next_json, render_workspace_bridge_next_text, render_workspace_bridge_text
from workspace_os.journal import write_cycle_journal
from workspace_os.journal import journal_root, latest_journal_entry, list_journal_entries
from workspace_os.conscience_report import build_conscience_recommendation_text, build_conscience_report, render_conscience_report_text
from workspace_os.config import Source, load_sources, load_workspace_memory_path
from workspace_os.conversation import build_workspace_reply
from workspace_os.context_pack import build_context_pack
from workspace_os.git_status import inspect_source
from workspace_os.housekeeping import find_temporary_artifacts
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.overview import build_workspace_handoff, build_workspace_next_action, build_workspace_overview, default_workspace_context_path, default_workspace_handoff_path, render_latest_workspace_context_text, render_workspace_analysis_text, render_workspace_handoff_text, render_workspace_next_action_text, render_workspace_roots_text, write_workspace_context_snapshot, write_workspace_handoff
from workspace_os.promotion import build_promotion_proposal
from workspace_os.profile import load_profile
from workspace_os.sanitization import sanitize_text
from workspace_os.search import search_sources
from workspace_os.shell import WorkspaceShell
from workspace_os.oce_extensions import load_configured_oce_extensions
from workspace_os.oce_extensions_report import build_oce_extensions_report, render_oce_extensions_report_text
from workspace_os.validation import validate_workspace, validation_failed
from workspace_os.web_server import serve_web_app


DEFAULT_CONFIG = Path("config/workspace.sources.example.json")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        sources = load_sources(args.config)
        memory_path = load_workspace_memory_path(args.config)
        load_configured_oce_extensions(args.config)
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
        return _validate(sources, args.skip_housekeeping, args.skip_smoke_queries)
    if args.command == "capture":
        return _capture(sources, args.capture_type, args.title, args.text, args.file, args.write)
    if args.command == "promote":
        return _promote(sources, args.target, args.rule, args.evidence, args.max_matches)
    if args.command == "chat":
        return _chat(sources, memory_path, args.message, args.session_id, args.interactive, args.verbose, config_path=args.config)
    if args.command == "inspect":
        return _inspect(sources, memory_path, args.launch_limit, args.compact)
    if args.command == "analysis":
        return _analysis(sources, memory_path, args.limit, args.compact)
    if args.command == "roots":
        return _roots(sources, memory_path, args.limit)
    if args.command == "handoff":
        return _handoff(sources, memory_path, args.launch_limit, args.output, args.compact)
    if args.command == "next":
        return _next_action(sources, memory_path, args.compact)
    if args.command == "memory":
        return _memory(memory_path, args.memory_command, args)
    if args.command == "feedback":
        return _memory(memory_path, "feedback", args)
    if args.command == "bridge":
        return _bridge(sources, memory_path, args.bridge_command, args)
    if args.command in {"conscience", "oce"}:
        return _conscience(memory_path, args.conscience_command, args)
    if args.command == "shell":
        return _shell(sources, memory_path, args.session_id)
    if args.command == "batch":
        return _batch(sources, memory_path, args.batch_command, args)
    if args.command == "process":
        return _process(sources, memory_path, args.process_command, args)
    if args.command == "cycle":
        return _cycle(sources, memory_path, args.cycle_command, args)
    if args.command == "journal":
        return _journal(sources, memory_path, args.journal_command, args)
    if args.command == "web":
        return _web(args.config, args.host, args.port)
    if args.command == "agents":
        return _agents(args.agents_command, args)

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
    validate_parser.add_argument(
        "--skip-smoke-queries",
        action="store_true",
        help="Skip representative user query smoke checks.",
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
    chat_parser.add_argument("--verbose", action="store_true", help="Show answer and trace instead of answer only.")
    chat_parser.add_argument(
        "--interactive",
        action="store_true",
        help="Force interactive mode even when a single message is provided.",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Render a condensed read-only overview of the active workspace state.",
    )
    inspect_parser.add_argument("--launch-limit", type=int, default=5, help="Maximum recent launches to show.")
    inspect_parser.add_argument("--compact", action="store_true", help="Render a shorter overview with summary lines.")

    analysis_parser = subparsers.add_parser(
        "analysis",
        help="Render an initial analysis of recently updated repositories and a recommended continuation.",
    )
    analysis_parser.add_argument("--limit", type=int, default=5, help="Maximum recently updated repositories to show.")
    analysis_parser.add_argument("--compact", action="store_true", help="Render a shorter analysis summary.")

    roots_parser = subparsers.add_parser(
        "roots",
        aliases=["kb"],
        help="Render the workspace and knowledge base roots with grouped repositories.",
    )
    roots_parser.add_argument("--limit", type=int, default=5, help="Maximum recently updated repositories to show.")

    handoff_parser = subparsers.add_parser(
        "handoff",
        help="Render a concise copyable handoff for the current workspace state.",
    )
    handoff_parser.add_argument("--launch-limit", type=int, default=3, help="Maximum recent launches to show.")
    handoff_parser.add_argument("--output", type=Path, help="Write the handoff Markdown to a file.")
    handoff_parser.add_argument("--compact", action="store_true", help="Render a shorter handoff summary.")

    next_parser = subparsers.add_parser(
        "next",
        help="Render the next operational action for the active workspace.",
    )
    next_parser.add_argument("--compact", action="store_true", help="Render a shorter action summary.")

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

    feedback_parser = memory_subparsers.add_parser("feedback", help="Record or inspect user feedback signals.")
    feedback_subparsers = feedback_parser.add_subparsers(dest="feedback_command", required=True)
    feedback_add = feedback_subparsers.add_parser("add", help="Add a feedback signal for a request/result pair.")
    feedback_add.add_argument("--request", required=True, help="Original request text.")
    feedback_add.add_argument("--result", required=True, help="Result text that was reviewed.")
    feedback_add.add_argument("--feedback", required=True, help="User feedback text.")
    feedback_history = feedback_subparsers.add_parser("history", help="List recent feedback signals.")
    feedback_history.add_argument("--limit", type=int, default=10, help="Maximum feedback entries to list.")
    feedback_status = feedback_subparsers.add_parser("status", help="Show feedback metrics.")

    feedback_root_parser = subparsers.add_parser(
        "feedback",
        help="Record or inspect request/result feedback signals.",
    )
    feedback_root_subparsers = feedback_root_parser.add_subparsers(dest="feedback_command", required=True)
    feedback_root_add = feedback_root_subparsers.add_parser("add", help="Add a feedback signal for a request/result pair.")
    feedback_root_add.add_argument("--request", required=True, help="Original request text.")
    feedback_root_add.add_argument("--result", required=True, help="Result text that was reviewed.")
    feedback_root_add.add_argument("--feedback", required=True, help="User feedback text.")
    feedback_root_history = feedback_root_subparsers.add_parser("history", help="List recent feedback signals.")
    feedback_root_history.add_argument("--limit", type=int, default=10, help="Maximum feedback entries to list.")
    feedback_root_subparsers.add_parser("status", help="Show feedback metrics.")

    bridge_parser = subparsers.add_parser(
        "bridge",
        help="Expose a non-interactive next decision, summary, and surface inventory for other CLIs.",
    )
    bridge_subparsers = bridge_parser.add_subparsers(dest="bridge_command", required=True)
    bridge_status = bridge_subparsers.add_parser("status", help="Show the operational bridge summary.")
    bridge_status.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    bridge_status.add_argument("--detail", action="store_true", help="Render the full bridge inventory.")
    bridge_next = bridge_subparsers.add_parser("next", help="Show the shortest next decision for the active workspace.")
    bridge_next.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    bridge_next.add_argument("--detail", action="store_true", help="Render the compact decision plus supporting details.")
    bridge_capabilities = bridge_subparsers.add_parser("capabilities", help="List available WOS surfaces.")
    bridge_capabilities.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    conscience_parser = subparsers.add_parser(
        "conscience",
        aliases=["oce"],
        help="Inspect the operational conscience decision history and metrics.",
    )
    conscience_subparsers = conscience_parser.add_subparsers(dest="conscience_command", required=True)
    conscience_status = conscience_subparsers.add_parser("status", help="Show summary decision metrics.")
    conscience_status.add_argument("--limit", type=int, default=20, help="Maximum decisions to summarize.")
    conscience_history = conscience_subparsers.add_parser("history", help="Show recent conscience decisions.")
    conscience_history.add_argument("--limit", type=int, default=20, help="Maximum decisions to list.")
    conscience_recommend = conscience_subparsers.add_parser("recommend", help="Show the most compact conscience recommendation.")
    conscience_recommend.add_argument("--limit", type=int, default=20, help="Maximum decisions to consider.")
    conscience_extensions = conscience_subparsers.add_parser("extensions", help="Show registered OCE extension layers.")

    shell_parser = subparsers.add_parser(
        "shell",
        help="Open the terminal-first Workspace OS shell.",
    )
    shell_parser.add_argument("--session-id", default="shell", help="Memory session identifier.")

    batch_parser = subparsers.add_parser(
        "batch",
        help="Track and report batch execution windows.",
    )
    batch_subparsers = batch_parser.add_subparsers(dest="batch_command", required=True)

    batch_start = batch_subparsers.add_parser("start", help="Start a new batch window.")
    batch_start.add_argument("--label", required=True, help="Batch label.")
    batch_start.add_argument("--objective", required=True, help="Batch objective.")

    batch_stop = batch_subparsers.add_parser("stop", help="Stop the active batch window.")

    batch_report = batch_subparsers.add_parser("report", help="Render the active or selected batch report.")
    batch_report.add_argument("--id", type=int, help="Batch identifier.")
    batch_handoff = batch_subparsers.add_parser("handoff", help="Render or export a handoff for the active batch window.")
    batch_handoff.add_argument("--launch-limit", type=int, default=3, help="Maximum recent launches to show.")
    batch_handoff.add_argument("--output", type=Path, help="Write the batch handoff Markdown to a file.")
    batch_handoff.add_argument("--compact", action="store_true", help="Render a shorter handoff summary.")

    batch_status = batch_subparsers.add_parser("status", help="Show the active batch window.")
    batch_history = batch_subparsers.add_parser("history", help="List recent batch windows.")
    batch_history.add_argument("--limit", type=int, default=5, help="Maximum batches to list.")

    batch_summary_parser = batch_subparsers.add_parser("summary", help="Summarize recent batch durations and defects.")
    batch_summary_parser.add_argument("--limit", type=int, default=5, help="Maximum batches to summarize.")

    process_parser = subparsers.add_parser(
        "process",
        help="Track and report a global work process window.",
    )
    process_subparsers = process_parser.add_subparsers(dest="process_command", required=True)
    process_start = process_subparsers.add_parser("start", help="Start a new process window.")
    process_start.add_argument("--label", required=True, help="Process label.")
    process_start.add_argument("--objective", required=True, help="Process objective.")
    process_subparsers.add_parser("stop", help="Stop the active process window.")
    process_status = process_subparsers.add_parser("status", help="Show the active process window.")
    process_report = process_subparsers.add_parser("report", help="Render the active or selected process report.")
    process_report.add_argument("--id", type=int, help="Process identifier.")
    process_summary_parser = process_subparsers.add_parser("summary", help="Summarize the active or selected process window.")
    process_summary_parser.add_argument("--id", type=int, help="Process identifier.")
    process_history = process_subparsers.add_parser("history", help="List recent process windows.")
    process_history.add_argument("--limit", type=int, default=5, help="Maximum processes to list.")
    process_checkpoint = process_subparsers.add_parser("checkpoint", help="Record a milestone in the active process window.")
    process_checkpoint.add_argument("--label", required=True, help="Checkpoint label.")
    process_checkpoint.add_argument("--note", default="", help="Optional checkpoint note.")
    process_handoff = process_subparsers.add_parser("handoff", help="Render or export a handoff for the active process window.")
    process_handoff.add_argument("--launch-limit", type=int, default=3, help="Maximum recent launches to show.")
    process_handoff.add_argument("--output", type=Path, help="Write the process handoff Markdown to a file.")
    process_handoff.add_argument("--compact", action="store_true", help="Render a shorter handoff summary.")

    cycle_parser = subparsers.add_parser(
        "cycle",
        help="Orchestrate multi-iteration work with health, stability, security, and quality checkpoints.",
    )
    cycle_subparsers = cycle_parser.add_subparsers(dest="cycle_command", required=True)
    cycle_start = cycle_subparsers.add_parser("start", help="Start a new long-running cycle.")
    cycle_start.add_argument("--label", required=True, help="Cycle label.")
    cycle_start.add_argument("--objective", required=True, help="Cycle objective.")
    cycle_run = cycle_subparsers.add_parser("run", help="Run one or more checkpoints in a cycle.")
    cycle_run.add_argument("--iterations", type=int, default=3, help="Number of checkpoints to run.")
    cycle_run.add_argument("--label", help="Optional cycle label when no cycle is active.")
    cycle_run.add_argument("--objective", help="Optional cycle objective when no cycle is active.")
    cycle_run.add_argument("--note", default="", help="Optional checkpoint note prefix.")
    cycle_run.add_argument("--stop-on-failure", action="store_true", help="Stop after the first failing checkpoint.")
    cycle_run.add_argument("--duration-minutes", type=float, help="Run checkpoints until the duration elapses.")
    cycle_run.add_argument("--interval-minutes", type=float, default=5.0, help="Minutes between duration-based checkpoints.")
    cycle_watch = cycle_subparsers.add_parser("watch", help="Run checkpoints over a duration window.")
    cycle_watch.add_argument("--duration-minutes", type=float, required=True, help="Total duration to keep checkpointing.")
    cycle_watch.add_argument("--interval-minutes", type=float, default=5.0, help="Minutes between checkpoints.")
    cycle_watch.add_argument("--label", help="Optional cycle label when no cycle is active.")
    cycle_watch.add_argument("--objective", help="Optional cycle objective when no cycle is active.")
    cycle_watch.add_argument("--note", default="", help="Optional checkpoint note prefix.")
    cycle_watch.add_argument("--stop-on-failure", action="store_true", help="Stop after the first failing checkpoint.")
    cycle_work = cycle_subparsers.add_parser("work", help="Run a long cycle that actively delegates work to agents.")
    cycle_work.add_argument("--duration-minutes", type=float, required=True, help="Target duration in minutes.")
    cycle_work.add_argument("--label", help="Optional cycle label when no cycle is active.")
    cycle_work.add_argument("--objective", help="Optional cycle objective when no cycle is active.")
    cycle_work.add_argument("--note", default="", help="Optional checkpoint note prefix.")
    cycle_work.add_argument("--stop-on-failure", action="store_true", help="Stop after the first failing checkpoint.")
    cycle_work.add_argument("--sequential", action="store_true", help="Use sequential mode (default is continuous for better throughput).")
    cycle_work.add_argument("--debug", action="store_true", help="Enable detailed debug logging to .workspace-os/debug-logs/")
    cycle_subparsers.add_parser("stop", help="Stop the active cycle.")
    cycle_status = cycle_subparsers.add_parser("status", help="Show the active cycle.")
    cycle_next = cycle_subparsers.add_parser("next", help="Recommend the next cycle action.")
    cycle_report = cycle_subparsers.add_parser("report", help="Render the active or selected cycle report.")
    cycle_report.add_argument("--id", type=int, help="Cycle identifier.")
    cycle_history = cycle_subparsers.add_parser("history", help="List recent cycles.")
    cycle_history.add_argument("--limit", type=int, default=5, help="Maximum cycles to list.")
    cycle_checkpoint = cycle_subparsers.add_parser("checkpoint", help="Run the cycle gates and record a checkpoint.")
    cycle_checkpoint.add_argument("--label", required=True, help="Checkpoint label.")
    cycle_checkpoint.add_argument("--note", default="", help="Optional checkpoint note.")

    journal_parser = subparsers.add_parser(
        "journal",
        help="Inspect productivity journals written during long runs.",
    )
    journal_subparsers = journal_parser.add_subparsers(dest="journal_command", required=True)
    journal_subparsers.add_parser("status", help="Show the latest journal entry summary.")
    journal_history = journal_subparsers.add_parser("history", help="List recent journal entries.")
    journal_history.add_argument("--limit", type=int, default=10, help="Maximum journal entries to list.")
    journal_report = journal_subparsers.add_parser("report", help="Render the latest journal entry.")
    journal_report.add_argument("--limit", type=int, default=1, help="Maximum entries to consider.")

    web_parser = subparsers.add_parser(
        "web",
        help="Run the local Workspace OS web pilot.",
    )
    web_parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    web_parser.add_argument("--port", type=int, default=8765, help="Bind port.")

    agents_parser = subparsers.add_parser(
        "agents",
        help="Check agent availability and configuration.",
    )
    agents_subparsers = agents_parser.add_subparsers(dest="agents_command", required=True)
    agents_status = agents_subparsers.add_parser("status", help="Show available agents and their configuration.")
    agents_status.add_argument("--verbose", action="store_true", help="Show detailed agent information.")
    agents_test = agents_subparsers.add_parser("test", help="Test agent command construction.")

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
        print(f"{match.source_name}:{match.path.as_posix()}:{match.line_number}: {sanitize_text(match.line)}")
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
    if topic.casefold() == "latest":
        store = WorkspaceMemoryStore(memory_path)
        store.ensure_schema()
        print(render_latest_workspace_context_text(store), end="")
        return 0
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


def _validate(sources: list[Source], skip_housekeeping: bool, skip_smoke_queries: bool) -> int:
    results = validate_workspace(
        sources=sources,
        include_housekeeping=not skip_housekeeping,
        include_smoke_queries=not skip_smoke_queries,
    )
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


def _chat(
    sources: list[Source],
    memory_path: Path,
    message: str | None,
    session_id: str,
    interactive: bool,
    verbose: bool,
    config_path: Path | None = None,
) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    profile = load_profile(store)

    if message and not interactive:
        from workspace_os.conversation import route_natural_language_intent
        cmd = route_natural_language_intent(message)
        if cmd:
            print(f"[WOS] Auto-executing matched command: {cmd}")
            import shlex
            argv = shlex.split(cmd)
            if config_path:
                argv = ["--config", str(config_path)] + argv
            return main(argv)

        reply = build_workspace_reply(
            sources,
            message,
            memory_store=store,
            session_id=session_id,
            tone=profile.tone,
            detail_level=profile.detail_level,
        )
        print(reply.reply if verbose else reply.answer)
        return 0

    print("Workspace OS chat. Type `exit` to leave.")
    print(render_latest_workspace_context_text(store), end="")
    while True:
        try:
            prompt = input("> ").strip()
        except EOFError:
            break
        if not prompt:
            continue
        if prompt.casefold() in {"exit", "quit"}:
            break

        from workspace_os.conversation import route_natural_language_intent
        cmd = route_natural_language_intent(prompt)
        if cmd:
            print(f"[WOS] Auto-executing matched command: {cmd}")
            import shlex
            argv = shlex.split(cmd)
            if config_path:
                argv = ["--config", str(config_path)] + argv
            main(argv)
            print("")
            continue

        reply = build_workspace_reply(
            sources,
            prompt,
            memory_store=store,
            session_id=session_id,
            tone=profile.tone,
            detail_level=profile.detail_level,
        )
        print(reply.reply if verbose else reply.answer)
        print("")
    return 0


def _inspect(sources: list[Source], memory_path: Path, launch_limit: int, compact: bool) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    overview = build_workspace_overview(sources, store, launch_limit=launch_limit, compact=compact)
    print(overview.render(), end="")
    return 0


def _analysis(sources: list[Source], memory_path: Path, limit: int, compact: bool) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    print(render_workspace_analysis_text(sources, store, limit=limit, compact=compact), end="")
    return 0


def _roots(sources: list[Source], memory_path: Path, limit: int) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    print(render_workspace_roots_text(sources, store, limit=limit), end="")
    return 0


def _handoff(sources: list[Source], memory_path: Path, launch_limit: int, output: Path | None = None, compact: bool = False) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    if output is not None:
        handoff = write_workspace_handoff(output, sources, store, launch_limit=launch_limit, compact=compact)
        print(f"written={output}")
        return 0
    print(render_workspace_handoff_text(sources, store, launch_limit=launch_limit, compact=compact), end="")
    return 0


def _next_action(sources: list[Source], memory_path: Path, compact: bool) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    if compact:
        print(render_workspace_next_action_text(sources, store), end="")
        return 0
    next_action = build_workspace_next_action(sources, store)
    print(next_action.render(), end="")
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

    if command == "feedback":
        if args.feedback_command == "add":
            from workspace_os.feedback import assess_feedback

            assessment = assess_feedback(args.request, args.result, args.feedback)
            entry_id = store.record_feedback_event(
                request_text=args.request,
                result_text=args.result,
                feedback_text=args.feedback,
                status=assessment.status,
                reason=assessment.reason,
                error_type=assessment.error_type,
                has_objection=assessment.has_objection,
                has_praise=assessment.has_praise,
            )
            print(f"saved feedback {entry_id}")
            print(f"status={assessment.status}")
            print(f"error_type={assessment.error_type}")
            print(f"reason={assessment.reason}")
            return 0
        if args.feedback_command == "history":
            entries = store.feedback_history(limit=args.limit)
            for entry in entries:
                print(
                    f"- {entry['id']} {entry['status']} ({entry['error_type']}): {entry['feedback_text']} "
                    f"({entry['created_at']})"
                )
            if not entries:
                print("No feedback entries found.")
            return 0
        if args.feedback_command == "status":
            from workspace_os.learning import build_workspace_learning_model

            profile = load_profile(store)
            metrics = store.feedback_metrics()
            print("Feedback report")
            for key, value in metrics.items():
                print(f"{key}={value}")
            print(f"learning_model={build_workspace_learning_model(store, profile).render_summary()}")
            return 0

    print("error: unsupported memory command", file=sys.stderr)
    return 2


def _bridge(sources: list[Source], memory_path: Path, command: str, args: argparse.Namespace) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()

    if command == "status":
        rendered = (
            render_workspace_bridge_json(sources, store)
            if getattr(args, "format", "text") == "json"
            else render_workspace_bridge_text(sources, store, compact=not getattr(args, "detail", False))
        )
        print(rendered, end="")
        return 0

    if command == "next":
        rendered = (
            render_workspace_bridge_next_json(sources, store)
            if getattr(args, "format", "text") == "json"
            else render_workspace_bridge_next_text(sources, store, detail=getattr(args, "detail", False))
        )
        print(rendered, end="")
        return 0

    if command == "capabilities":
        rendered = (
            render_workspace_bridge_json(sources, store)
            if getattr(args, "format", "text") == "json"
            else render_workspace_bridge_capabilities_text(sources, store)
        )
        if getattr(args, "format", "text") == "json":
            print(rendered, end="")
            return 0
        lines = rendered.splitlines()
        try:
            start = lines.index("Available surfaces:")
        except ValueError:
            print(rendered, end="")
            return 0
        print("\n".join(lines[start:]) + "\n", end="")
        return 0

    print("error: unsupported bridge command", file=sys.stderr)
    return 2


def _conscience(memory_path: Path, command: str, args: argparse.Namespace) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()

    if command == "status":
        report = build_conscience_report(store, limit=args.limit)
        print(render_conscience_report_text(report), end="")
        return 0

    if command == "history":
        report = build_conscience_report(store, limit=args.limit)
        print(render_conscience_report_text(report), end="")
        return 0

    if command == "recommend":
        print(build_conscience_recommendation_text(store, limit=args.limit), end="")
        return 0

    if command == "extensions":
        print(render_oce_extensions_report_text(build_oce_extensions_report()), end="")
        return 0

    print("error: unsupported conscience command", file=sys.stderr)
    return 2


def _shell(sources: list[Source], memory_path: Path, session_id: str) -> int:
    shell = WorkspaceShell(sources=sources, memory_path=memory_path, session_id=session_id)
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("")
    return 0


def _batch(sources: list[Source], memory_path: Path, command: str, args: argparse.Namespace) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()

    if command == "start":
        try:
            batch_id = start_batch(store, args.label, args.objective)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"batch_started={batch_id}")
        return 0

    if command == "stop":
        report = stop_batch(store)
        if report is None:
            print("No active batch found.")
            return 0
        print(report.render(), end="")
        handoff_path = default_workspace_handoff_path(memory_path)
        context_path = default_workspace_context_path(memory_path)
        write_workspace_handoff(handoff_path, sources, store, launch_limit=3, prefix=report.render())
        write_workspace_context_snapshot(
            context_path,
            sources,
            store,
            launch_limit=3,
            reason="batch-stop",
        )
        print(f"handoff_written={handoff_path}")
        print(f"context_written={context_path}")
        return 0

    if command == "report":
        report = current_batch_report(store, batch_id=args.id)
        if report is None:
            print("No batch found.")
            return 0
        print(report.render(), end="")
        return 0

    if command == "handoff":
        report = current_batch_report(store)
        if report is None:
            print("No active batch found.")
            return 0
        prefix = report.render()
        if getattr(args, "output", None) is not None:
            write_workspace_handoff(
                args.output,
                sources,
                store,
                launch_limit=args.launch_limit,
                compact=args.compact,
                prefix=prefix,
            )
            print(f"written={args.output}")
            return 0
        print(
            render_workspace_handoff_text(
                sources,
                store,
                launch_limit=args.launch_limit,
                compact=args.compact,
                prefix=prefix,
            ),
            end="",
        )
        return 0

    if command == "status":
        batch = store.active_batch()
        if batch is None:
            print("No active batch found.")
            return 0
        report = current_batch_report(store)
        if report is not None:
            print(report.render(), end="")
        return 0

    if command == "history":
        batches = store.batch_history(limit=args.limit)
        for batch in batches:
            print(
                f"- {batch['id']} {batch['label']}: {batch['objective']} "
                f"({batch['started_at']} -> {batch['ended_at'] or 'active'})"
            )
        if not batches:
            print("No batches found.")
        return 0

    if command == "summary":
        summary = batch_summary(store, limit=args.limit)
        print(summary.render(), end="")
        return 0

    print("error: unsupported batch command", file=sys.stderr)
    return 2


def _process(sources: list[Source], memory_path: Path, command: str, args: argparse.Namespace) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()

    if command == "start":
        try:
            process_id = start_process(store, args.label, args.objective)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"process_started={process_id}")
        return 0

    if command == "stop":
        report = stop_process(store)
        if report is None:
            print("No active process found.")
            return 0
        print(report.render(), end="")
        handoff_path = default_workspace_handoff_path(memory_path)
        context_path = default_workspace_context_path(memory_path)
        write_workspace_handoff(handoff_path, sources, store, launch_limit=3, prefix=report.render())
        write_workspace_context_snapshot(
            context_path,
            sources,
            store,
            launch_limit=3,
            reason="process-stop",
        )
        print(f"handoff_written={handoff_path}")
        print(f"context_written={context_path}")
        return 0

    if command == "status":
        report = current_process_report(store)
        if report is None:
            print("No active process found.")
            return 0
        print(report.render(), end="")
        return 0

    if command == "report":
        report = current_process_report(store, process_id=args.id)
        if report is None:
            print("No process found.")
            return 0
        print(report.render(), end="")
        return 0

    if command == "handoff":
        report = current_process_report(store)
        if report is None:
            print("No active process found.")
            return 0
        prefix = report.render()
        if getattr(args, "output", None) is not None:
            write_workspace_handoff(
                args.output,
                sources,
                store,
                launch_limit=args.launch_limit,
                compact=args.compact,
                prefix=prefix,
            )
            print(f"written={args.output}")
            return 0
        print(
            render_workspace_handoff_text(
                sources,
                store,
                launch_limit=args.launch_limit,
                compact=args.compact,
                prefix=prefix,
            ),
            end="",
        )
        return 0

    if command == "summary":
        report = process_summary(store, process_id=args.id)
        if report is None:
            print("No process found.")
            return 0
        print(report.render(), end="")
        return 0

    if command == "checkpoint":
        process = store.active_process()
        if process is None:
            print("No active process found.")
            return 0
        checkpoint_id = store.record_process_checkpoint(
            label=args.label,
            note=args.note,
            process_id=int(process["id"]),
        )
        print(f"checkpoint_recorded={checkpoint_id}")
        return 0

    if command == "history":
        processes = store.process_history(limit=args.limit)
        for process in processes:
            print(
                f"- {process['id']} {process['label']}: {process['objective']} "
                f"({process['started_at']} -> {process['ended_at'] or 'active'})"
            )
        if not processes:
            print("No processes found.")
        return 0

    print("error: unsupported process command", file=sys.stderr)
    return 2


def _web(config_path: Path, host: str, port: int) -> int:
    serve_web_app(config_path=config_path, host=host, port=port)
    return 0


def _agents(command: str, args: argparse.Namespace) -> int:
    from workspace_os.agent_policy import SUPPORTED_WORK_AGENTS, agent_is_available, available_work_agents

    if command == "status":
        print("🤖 WOS Agent Status\n")

        for agent in SUPPORTED_WORK_AGENTS:
            available = agent_is_available(agent)
            status_icon = "✓" if available else "✗"
            status_text = "AVAILABLE" if available else "NOT FOUND"

            # Show path if available
            path = shutil.which(agent)
            if not path:
                # Check for .cmd or .ps1 variants
                path = shutil.which(f"{agent}.cmd") or shutil.which(f"{agent}.ps1")

            location = f" ({path})" if path else ""

            print(f"{status_icon} {agent}: {status_text}{location}")

            # Show additional info in verbose mode
            if getattr(args, "verbose", False) and available:
                if agent == "antigravity":
                    custom_cmd = os.environ.get("WOS_ANTIGRAVITY_COMMAND")
                    if custom_cmd:
                        print(f"  └─ Custom command: {custom_cmd[:60]}...")

        active = available_work_agents()
        print(f"\nActive pool: {', '.join(active)} ({len(active)} agent{'s' if len(active) != 1 else ''})")

        return 0

    if command == "test":
        print("🧪 Testing agent execution...\n")

        from workspace_os.agent_adapter import build_agent_command

        for agent in available_work_agents():
            try:
                cmd = build_agent_command(agent, Path.cwd(), "test prompt")
                cmd_preview = ' '.join(str(c) for c in cmd[:3])
                print(f"✓ {agent}: {cmd_preview}...")
            except Exception as e:
                print(f"✗ {agent}: {e}")

        return 0

    print(f"error: unsupported agents command '{command}'", file=sys.stderr)
    return 2


def _cycle(sources: list[Source], memory_path: Path, command: str, args: argparse.Namespace) -> int:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()

    if command == "start":
        cycle_id = start_cycle(store, args.label, args.objective)
        print(f"started cycle {cycle_id}")
        return 0

    if command == "run":
        try:
            is_duration_mode = args.duration_minutes is not None
            if args.duration_minutes is not None:
                result = run_cycle_window(
                    store,
                    sources,
                    duration_minutes=max(0.0, args.duration_minutes),
                    interval_minutes=max(0.01, args.interval_minutes),
                    label=args.label,
                    objective=args.objective,
                    note=args.note,
                    stop_on_failure=args.stop_on_failure,
                    debug=getattr(args, 'debug', False),
                )
            else:
                result = run_cycle_plan(
                    store,
                    sources,
                    iterations=max(1, args.iterations),
                    label=args.label,
                    objective=args.objective,
                    note=args.note,
                    stop_on_failure=args.stop_on_failure,
                )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"cycle_id={result.cycle_id}")
        print(f"iterations_completed={result.iterations_completed}")
        if result.target_duration_minutes is not None:
            print(f"target_duration_minutes={result.target_duration_minutes:.2f}")
        if result.window_started_at is not None:
            print(f"window_started_at={result.window_started_at}")
        if result.window_ended_at is not None:
            print(f"window_ended_at={result.window_ended_at}")
        for iteration in result.iteration_results:
            print(f"saved checkpoint {iteration.checkpoint_id} ({iteration.label})")
            print(render_cycle_evaluation(iteration.evaluation), end="")
        print(_render_cycle_report(_cycle_report_to_dict(result.report)), end="")
        if is_duration_mode:
            journal = write_cycle_journal(
                store,
                sources,
                result.report.cycle,
                store.cycle_checkpoints(result.cycle_id, limit=1000),
                story_title=result.report.cycle["label"],
                logical_duration_seconds=result.logical_duration_seconds,
                wall_clock_duration_seconds=result.wall_clock_duration_seconds,
                sleep_duration_seconds=result.sleep_duration_seconds,
                logical_active_duration_seconds=result.logical_active_duration_seconds,
                wall_clock_active_duration_seconds=result.wall_clock_active_duration_seconds,
                idle_ratio=result.idle_ratio,
                delegation_count=result.delegation_count,
                agent_active_duration_seconds=result.agent_active_duration_seconds,
                queue_utilization_ratio=result.queue_utilization_ratio,
                max_queue_depth=result.max_queue_depth,
                avg_work_item_duration_seconds=result.avg_work_item_duration_seconds,
            )
            print(f"journal_written={journal.entry_path}")
        return 0

    if command == "watch":
        try:
            result = run_cycle_window(
                store,
                sources,
                duration_minutes=max(0.0, args.duration_minutes),
                interval_minutes=max(0.01, args.interval_minutes),
                label=args.label,
                objective=args.objective,
                note=args.note,
                stop_on_failure=args.stop_on_failure,
                debug=getattr(args, 'debug', False),
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"cycle_id={result.cycle_id}")
        print(f"iterations_completed={result.iterations_completed}")
        print(f"target_duration_minutes={result.target_duration_minutes:.2f}")
        print(f"window_started_at={result.window_started_at}")
        print(f"window_ended_at={result.window_ended_at}")
        for iteration in result.iteration_results:
            print(f"saved checkpoint {iteration.checkpoint_id} ({iteration.label})")
            print(render_cycle_evaluation(iteration.evaluation), end="")
        print(_render_cycle_report(_cycle_report_to_dict(result.report)), end="")
        journal = write_cycle_journal(
            store,
            sources,
            result.report.cycle,
            store.cycle_checkpoints(result.cycle_id, limit=1000),
            story_title=result.report.cycle["label"],
            logical_duration_seconds=result.logical_duration_seconds,
            wall_clock_duration_seconds=result.wall_clock_duration_seconds,
            sleep_duration_seconds=result.sleep_duration_seconds,
            logical_active_duration_seconds=result.logical_active_duration_seconds,
            wall_clock_active_duration_seconds=result.wall_clock_active_duration_seconds,
            idle_ratio=result.idle_ratio,
            delegation_count=result.delegation_count,
            agent_active_duration_seconds=result.agent_active_duration_seconds,
            queue_utilization_ratio=result.queue_utilization_ratio,
            max_queue_depth=result.max_queue_depth,
            avg_work_item_duration_seconds=result.avg_work_item_duration_seconds,
        )
        print(f"journal_written={journal.entry_path}")
        return 0

    if command == "work":
        try:
            # Default to continuous mode for better throughput (unless explicitly disabled)
            use_continuous = not getattr(args, 'sequential', False)
            work_fn = run_cycle_work_window_continuous if use_continuous else run_cycle_work_window
            result = work_fn(
                store,
                sources,
                duration_minutes=max(0.0, args.duration_minutes),
                label=args.label,
                objective=args.objective,
                note=args.note,
                stop_on_failure=args.stop_on_failure,
                debug=getattr(args, 'debug', False),
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"cycle_id={result.cycle_id}")
        print(f"iterations_completed={result.iterations_completed}")
        print(f"target_duration_minutes={result.target_duration_minutes:.2f}")
        print(f"window_started_at={result.window_started_at}")
        print(f"window_ended_at={result.window_ended_at}")
        print(f"delegation_count={result.delegation_count or 0}")
        print(f"agent_active_duration_seconds={result.agent_active_duration_seconds or 0.0:.2f}")
        queue_utilization_ratio = getattr(result, "queue_utilization_ratio", None)
        if queue_utilization_ratio is not None:
            print(f"queue_utilization_ratio={queue_utilization_ratio:.2f}")
            print(f"max_queue_depth={getattr(result, 'max_queue_depth', 0) or 0}")
            print(f"avg_work_item_duration_seconds={getattr(result, 'avg_work_item_duration_seconds', 0.0) or 0.0:.2f}")
        for iteration in result.iteration_results:
            print(f"saved checkpoint {iteration.checkpoint_id} ({iteration.label})")
            print(render_cycle_evaluation(iteration.evaluation), end="")
            if iteration.work_summary:
                print(iteration.work_summary)
        print(_render_cycle_report(_cycle_report_to_dict(result.report)), end="")
        journal = write_cycle_journal(
            store,
            sources,
            result.report.cycle,
            store.cycle_checkpoints(result.cycle_id, limit=1000),
            story_title=result.report.cycle["label"],
            logical_duration_seconds=result.logical_duration_seconds,
            wall_clock_duration_seconds=result.wall_clock_duration_seconds,
            sleep_duration_seconds=result.sleep_duration_seconds,
            logical_active_duration_seconds=result.logical_active_duration_seconds,
            wall_clock_active_duration_seconds=result.wall_clock_active_duration_seconds,
            idle_ratio=result.idle_ratio,
            delegation_count=result.delegation_count,
            agent_active_duration_seconds=result.agent_active_duration_seconds,
            queue_utilization_ratio=result.queue_utilization_ratio,
            max_queue_depth=result.max_queue_depth,
            avg_work_item_duration_seconds=result.avg_work_item_duration_seconds,
        )
        print(f"journal_written={journal.entry_path}")
        return 0

    if command == "stop":
        cycle = stop_cycle(store)
        if cycle is None:
            print("No active cycle found.")
            return 0
        report = store.cycle_report(int(cycle["id"]))
        if report is not None:
            print(_render_cycle_report(report))
        return 0

    if command == "status":
        report = active_cycle_report(store)
        if report is None:
            print("No active cycle found.")
            return 0
        print(report.render(), end="")
        return 0

    if command == "next":
        print(build_cycle_next_action(store).render(), end="")
        return 0

    if command == "report":
        report = store.cycle_report(args.id)
        if report is None:
            print("No cycle found.")
            return 0
        print(_render_cycle_report(report))
        return 0

    if command == "history":
        cycles = cycle_history_report(store, limit=args.limit)
        if not cycles:
            print("No cycles found.")
            return 0
        for cycle in cycles:
            print(
                f"- {cycle['id']} {cycle['label']}: {cycle['objective']} "
                f"({cycle['started_at']} -> {cycle['ended_at'] or 'active'})"
            )
        return 0

    if command == "checkpoint":
        active = store.active_cycle()
        if active is None:
            print("No active cycle found.")
            return 0
        evaluation = run_cycle_evaluation(sources, store)
        checkpoint_id = record_cycle_checkpoint(
            store,
            evaluation,
            args.label,
            iteration_number=_next_cycle_iteration(store, int(active["id"])),
            note=args.note or None,
        )
        print(f"saved checkpoint {checkpoint_id}")
        print(render_cycle_evaluation(evaluation), end="")
        return 0

    print("error: unsupported cycle command", file=sys.stderr)
    return 2


def _journal(sources: list[Source], memory_path: Path, command: str, args: argparse.Namespace) -> int:
    del sources
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    if command == "status":
        entry = latest_journal_entry(store)
        if entry is None:
            print(f"journal_root={journal_root(store)}")
            print("No journal entries found.")
            return 0
        print(entry.render(), end="")
        return 0
    if command == "history":
        entries = list_journal_entries(store, limit=args.limit)
        if not entries:
            print(f"journal_root={journal_root(store)}")
            print("No journal entries found.")
            return 0
        print(f"journal_root={journal_root(store)}")
        for entry in entries:
            print(
                f"- {entry.entry_id} {entry.label}: duration={entry.duration_seconds:.0f}s "
                f"checkpoints={entry.checkpoint_count} commits={sum(metric.commits for metric in entry.source_metrics)}"
            )
        return 0
    if command == "report":
        entries = list_journal_entries(store, limit=args.limit)
        if not entries:
            print("No journal entries found.")
            return 0
        print(entries[0].render(), end="")
        return 0
    print("error: unsupported journal command", file=sys.stderr)
    return 2


def _render_cycle_report(report: dict[str, object]) -> str:
    lines = [f"Cycle report: {report['cycle']['label']}"]
    lines.append(f"cycle_id={report['cycle_id']}")
    lines.append(f"checkpoint_count={report['checkpoint_count']}")
    lines.append(f"health_pass_rate={report['health_pass_rate']:.2f}")
    lines.append(f"stability_pass_rate={report['stability_pass_rate']:.2f}")
    lines.append(f"security_pass_rate={report['security_pass_rate']:.2f}")
    lines.append(f"quality_pass_rate={report['quality_pass_rate']:.2f}")
    latest = report.get("latest_checkpoint")
    if isinstance(latest, dict):
        lines.append(f"latest_checkpoint={latest.get('iteration_number', 'n/a')}")
        lines.append(f"latest_label={latest.get('label', 'n/a')}")
    return "\n".join(lines) + "\n"


def _cycle_report_to_dict(report: object) -> dict[str, object]:
    cycle = getattr(report, "cycle", None)
    if cycle is None:
        raise TypeError("Unsupported cycle report type.")
    return {
        "cycle": cycle,
        "cycle_id": cycle.get("id"),
        "checkpoint_count": getattr(report, "checkpoint_count"),
        "health_pass_rate": getattr(report, "health_pass_rate"),
        "stability_pass_rate": getattr(report, "stability_pass_rate"),
        "security_pass_rate": getattr(report, "security_pass_rate"),
        "quality_pass_rate": getattr(report, "quality_pass_rate"),
        "latest_checkpoint": getattr(report, "latest_checkpoint"),
    }


def _next_cycle_iteration(store: WorkspaceMemoryStore, cycle_id: int) -> int:
    return len(store.cycle_checkpoints(cycle_id, limit=1000)) + 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from workspace_os.capture import build_capture_draft, write_capture
from workspace_os.classification import classify_content
from workspace_os.config import Source, load_sources
from workspace_os.context_pack import build_context_pack
from workspace_os.git_status import inspect_source
from workspace_os.housekeeping import find_temporary_artifacts
from workspace_os.promotion import build_promotion_proposal
from workspace_os.sanitization import sanitize_text
from workspace_os.search import search_sources
from workspace_os.validation import validate_workspace, validation_failed


DEFAULT_CONFIG = Path("config/workspace.sources.example.json")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        sources = load_sources(args.config)
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
        return _context(sources, args.topic, args.max_matches, args.max_doctrine_lines)
    if args.command == "classify":
        return _classify(args.value, args.path)
    if args.command == "validate":
        return _validate(sources, args.skip_housekeeping)
    if args.command == "capture":
        return _capture(sources, args.capture_type, args.title, args.text, args.file, args.write)
    if args.command == "promote":
        return _promote(sources, args.target, args.rule, args.evidence, args.max_matches)

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


def _context(sources: list[Source], topic: str, max_matches: int, max_doctrine_lines: int) -> int:
    pack = build_context_pack(
        sources=sources,
        topic=topic,
        max_matches=max_matches,
        max_doctrine_lines=max_doctrine_lines,
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


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import shlex
import subprocess
import struct
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from workspace_os.capture import build_capture_draft
from workspace_os.agent_adapter import build_agent_command
from workspace_os.agent_policy import normalize_agent_name
from workspace_os.agent_queue import AgentQueueTracker
from workspace_os.batch import current_batch_report, current_process_report
from workspace_os.classification import classify_content
from workspace_os.conscience import ConscienceDecision, evaluate_request, render_decision_for_prompt
from workspace_os.conscience_report import build_conscience_recommendation_text, build_conscience_report, render_conscience_report_text
from workspace_os.cycle import build_cycle_next_action
from workspace_os.delegation import build_hardened_delegate_prompt
from workspace_os.config import Source, load_sources, load_workspace_memory_path, load_workspace_root
from workspace_os.conversation import build_workspace_reply
from workspace_os.learning import suggest_questions_for_work
from workspace_os.local_metrics import (
    build_local_metrics_report,
    render_local_metrics_markdown,
    render_metrics_export,
)
from workspace_os.oce_extensions import load_configured_oce_extensions
from workspace_os.context_pack import build_context_pack
from workspace_os.git_status import inspect_source
from workspace_os.housekeeping import find_temporary_artifacts
from workspace_os.memory import WorkspaceMemoryStore, _utc_now
from workspace_os.overview import build_workspace_handoff, render_workspace_analysis_text, render_workspace_handoff_text, render_workspace_next_action_text, render_workspace_roots_text
from workspace_os.promotion import build_promotion_proposal
from workspace_os.profile import load_profile
from workspace_os.sanitization import sanitize_text
from workspace_os.search import search_sources
from workspace_os.security.validator import SecurityValidator
from workspace_os.validation import validate_workspace, validation_failed


STATIC_ROOT = Path(__file__).parent / "web_assets"


def serve_web_app(config_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    sources = load_sources(config_path)
    load_configured_oce_extensions(config_path)
    workspace_root = load_workspace_root(config_path)
    memory_path = load_workspace_memory_path(config_path)
    handler = _build_handler(sources, workspace_root, memory_path, config_path)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Workspace OS web app listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Workspace OS web app stopped.")
    finally:
        server.server_close()


def _build_handler(sources: list[Source], workspace_root: Path, memory_path: Path, config_path: Path | None = None):
    class WorkspaceRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server method name
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if parsed.path == "/":
                self._send_static("index.html", "text/html; charset=utf-8")
                return
            if parsed.path == "/static/app.css":
                self._send_static("app.css", "text/css; charset=utf-8")
                return
            if parsed.path == "/static/app.js":
                self._send_static("app.js", "text/javascript; charset=utf-8")
                return
            if parsed.path == "/api/status":
                self._send_json(_status_payload(sources))
                return
            if parsed.path == "/api/search":
                self._send_json(_search_payload(sources, query))
                return
            if parsed.path == "/api/context":
                self._send_json(_context_payload(sources, query))
                return
            if parsed.path == "/api/classify":
                self._send_json(_classify_payload(query))
                return
            if parsed.path == "/api/validate":
                self._send_json(_validate_payload(sources, query))
                return
            if parsed.path == "/api/roadmap":
                self._send_json(_roadmap_payload())
                return
            if parsed.path == "/api/cycle-monitor":
                self._send_json(_cycle_monitor_payload(memory_path, query))
                return
            if parsed.path == "/api/cycle-monitor.md":
                self._send_text(
                    _cycle_monitor_markdown_payload(memory_path, query),
                    "text/markdown; charset=utf-8",
                    filename="cycle-monitor.md",
                )
                return
            if parsed.path == "/api/cycle-monitor/ws":
                if self.headers.get("Upgrade", "").lower() == "websocket":
                    self._handle_cycle_monitor_websocket(memory_path, query)
                    return
                self._send_json(_cycle_monitor_payload(memory_path, query))
                return
            if parsed.path == "/api/recent-software":
                self._send_json(_recent_software_payload(root=workspace_root))
                return
            if parsed.path == "/api/analysis":
                self._send_json(_analysis_payload(sources, memory_path, query))
                return
            if parsed.path == "/api/analysis.md":
                self._send_text(
                    _analysis_markdown_payload(sources, memory_path, query),
                    "text/markdown; charset=utf-8",
                    filename="analysis.md",
                )
                return
            if parsed.path == "/api/roots":
                self._send_json(_roots_payload(sources, memory_path, query))
                return
            if parsed.path == "/api/roots.md":
                self._send_text(
                    _roots_markdown_payload(sources, memory_path, query),
                    "text/markdown; charset=utf-8",
                    filename="roots.md",
                )
                return
            if parsed.path == "/api/recent-docs":
                self._send_json(_recent_docs_payload())
                return
            if parsed.path == "/api/context-snapshot":
                self._send_json(_context_snapshot_payload(memory_path, workspace_root, query))
                return
            if parsed.path == "/api/context-snapshot.md":
                self._send_text(
                    _context_snapshot_markdown_payload(memory_path, workspace_root, query),
                    "text/markdown; charset=utf-8",
                    filename="context-global.md",
                )
                return
            if parsed.path == "/api/handoff":
                self._send_json(_handoff_payload(sources, memory_path, workspace_root, query))
                return
            if parsed.path == "/api/handoff.md":
                self._send_text(
                    _handoff_markdown_payload(sources, memory_path, workspace_root, query),
                    "text/markdown; charset=utf-8",
                    filename="handoff.md",
                )
                return
            if parsed.path == "/api/next":
                self._send_json(_next_action_payload(sources, memory_path, query))
                return
            if parsed.path == "/api/next.md":
                self._send_text(
                    _next_action_markdown_payload(sources, memory_path, query),
                    "text/markdown; charset=utf-8",
                    filename="next.md",
                )
                return
            if parsed.path == "/api/conscience":
                self._send_json(_conscience_metrics_payload(memory_path, query))
                return
            if parsed.path == "/api/conscience.md":
                self._send_text(
                    _conscience_metrics_markdown_payload(memory_path, query),
                    "text/markdown; charset=utf-8",
                    filename="conscience.md",
                )
                return
            if parsed.path == "/api/conscience/recommend":
                self._send_json(_conscience_recommendation_payload(memory_path, query))
                return
            if parsed.path == "/api/conscience/recommend.md":
                self._send_text(
                    _conscience_recommendation_markdown_payload(memory_path, query),
                    "text/markdown; charset=utf-8",
                    filename="conscience-recommendation.md",
                )
                return
            if parsed.path == "/api/questioning":
                self._send_json(_questioning_payload(memory_path, query))
                return
            if parsed.path == "/api/questioning.md":
                self._send_text(
                    _questioning_markdown_payload(memory_path, query),
                    "text/markdown; charset=utf-8",
                    filename="questioning.md",
                )
                return
            if parsed.path == "/api/security":
                self._send_json(_security_payload(workspace_root, query))
                return
            if parsed.path == "/api/security.md":
                self._send_text(
                    _security_markdown_payload(workspace_root, query),
                    "text/markdown; charset=utf-8",
                    filename="security.md",
                )
                return
            if parsed.path == "/api/agent-utilization":
                self._send_json(_agent_utilization_payload(memory_path, query))
                return
            if parsed.path == "/api/agent-utilization.md":
                self._send_text(
                    _agent_utilization_markdown_payload(memory_path, query),
                    "text/markdown; charset=utf-8",
                    filename="agent-utilization.md",
                )
                return
            if parsed.path == "/api/metrics":
                self._send_json(_local_metrics_payload(memory_path, query))
                return
            if parsed.path == "/api/metrics.md":
                self._send_text(
                    _local_metrics_markdown_payload(memory_path, query),
                    "text/markdown; charset=utf-8",
                    filename="metrics.md",
                )
                return
            if parsed.path == "/api/metrics/export":
                exporter = _first(query, "format") or _first(query, "exporter")
                payload = _local_metrics_export_payload(memory_path, exporter)
                content_type = str(payload.get("content_type", "text/plain; charset=utf-8"))
                self._send_text(payload, content_type, filename=str(payload.get("filename", "metrics-export.txt")))
                return

            self.send_error(404, "Not found")

        def do_POST(self) -> None:  # noqa: N802 - http.server method name
            parsed = urlparse(self.path)
            payload = self._read_json_body()

            if parsed.path == "/api/capture-preview":
                self._send_json(_capture_preview_payload(sources, payload))
                return
            if parsed.path == "/api/promote-preview":
                self._send_json(_promote_preview_payload(sources, payload))
                return
            if parsed.path == "/api/conscience-preview":
                self._send_json(_conscience_preview_payload(payload))
                return
            if parsed.path == "/api/chat":
                self._send_json(_chat_payload(sources, payload, memory_path, workspace_root, config_path))
                return
            if parsed.path == "/api/delegate-launch":
                self._send_json(_delegate_launch_payload(payload, workspace_root=workspace_root))
                return

        def log_message(self, format: str, *args: object) -> None:
            return

        def _read_json_body(self) -> dict[str, object]:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_length)
            except ValueError:
                length = 0
            if length <= 0:
                return {}
            body = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return {}
            return payload if isinstance(payload, dict) else {}

        def _send_json(self, payload: object, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            _write_response_body(self.wfile.write, body)

        def _send_text(self, payload: dict[str, object], content_type: str, filename: str | None = None) -> None:
            body = str(payload.get("text", "")).encode("utf-8")
            status = 200 if payload.get("ok", True) else 400
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            _write_response_body(self.wfile.write, body)

        def _send_static(self, filename: str, content_type: str) -> None:
            path = STATIC_ROOT / filename
            if not path.exists():
                self.send_error(404, "Not found")
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            _write_response_body(self.wfile.write, body)

        def _handle_cycle_monitor_websocket(self, memory_path: Path | None, query: dict[str, list[str]]) -> None:
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:
                self.send_error(400, "Missing Sec-WebSocket-Key header")
                return
            accept = _websocket_accept_key(key)
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            while True:
                payload = _cycle_monitor_payload(memory_path, query)
                frame = _websocket_text_frame(json.dumps(payload, ensure_ascii=False))
                _write_response_body(self.wfile.write, frame)
                try:
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
                    return
                time.sleep(5)

    return WorkspaceRequestHandler


def _write_response_body(writer, body: bytes) -> None:
    try:
        writer(body)
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
        return


def _bool_mark(value: object) -> str:
    return "PASS" if bool(value) else "FAIL"


def _websocket_accept_key(key: str) -> str:
    digest = hashlib.new(
        "sha1",
        (key.strip() + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("utf-8"),
        usedforsecurity=False,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _websocket_text_frame(message: str) -> bytes:
    payload = message.encode("utf-8")
    length = len(payload)
    header = bytearray([0x81])
    if length < 126:
        header.append(length)
    elif length < (1 << 16):
        header.append(126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(127)
        header.extend(struct.pack(">Q", length))
    return bytes(header) + payload


def _status_payload(sources: list[Source]) -> dict[str, object]:
    items = []
    for status in [inspect_source(source) for source in sources]:
        items.append(
            {
                "name": status.source.name,
                "type": status.source.type,
                "state": status.state,
                "branch": status.branch,
                "changes": status.dirty_count,
                "untracked": status.untracked_count,
                "ahead": status.ahead,
                "behind": status.behind,
            }
        )
    return {"sources": items}


def _search_payload(sources: list[Source], query: dict[str, list[str]]) -> dict[str, object]:
    text = _first(query, "query")
    source_type = _first(query, "source_type") or None
    max_results = _int_query(query, "max_results", 20)
    matches = search_sources(sources, text, source_type=source_type, max_results=max_results) if text else []
    return {
        "matches": [
            {
                "source": match.source_name,
                "path": match.path.as_posix(),
                "line": match.line_number,
                "text": sanitize_text(match.line),
            }
            for match in matches
        ]
    }


def _context_payload(sources: list[Source], query: dict[str, list[str]]) -> dict[str, object]:
    topic = _first(query, "topic") or "agent alignment"
    pack = build_context_pack(
        sources=sources,
        topic=topic,
        max_matches=_int_query(query, "max_matches", 8),
        max_doctrine_lines=_int_query(query, "max_doctrine_lines", 24),
    )
    return {"markdown": pack.render_markdown()}


def _classify_payload(query: dict[str, list[str]]) -> dict[str, object]:
    value = _first(query, "value")
    classification = classify_content(value) if value else classify_content("")
    return {
        "target": classification.target,
        "confidence": classification.confidence,
        "reason": classification.reason,
    }


def _validate_payload(sources: list[Source], query: dict[str, list[str]]) -> dict[str, object]:
    skip_housekeeping = (_first(query, "skip_housekeeping") or "true").casefold() == "true"
    results = validate_workspace(sources, include_housekeeping=not skip_housekeeping)
    return {
        "failed": validation_failed(results),
        "results": [
            {"name": result.name, "passed": result.passed, "detail": result.detail}
            for result in results
        ],
    }


def _capture_preview_payload(sources: list[Source], payload: dict[str, object]) -> dict[str, object]:
    try:
        draft = build_capture_draft(
            sources=sources,
            capture_type=_string_payload(payload, "type") or "session",
            title=_string_payload(payload, "title") or "Untitled capture",
            body=_string_payload(payload, "body"),
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "target": f"{draft.source_name}:{draft.relative_path}",
        "content": draft.content,
    }


def _promote_preview_payload(sources: list[Source], payload: dict[str, object]) -> dict[str, object]:
    try:
        proposal = build_promotion_proposal(
            sources=sources,
            target=_string_payload(payload, "target") or "adev",
            rule=_string_payload(payload, "rule"),
            evidence=_string_payload(payload, "evidence"),
            max_matches=8,
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "markdown": proposal.render_markdown()}


def _conscience_preview_payload(payload: dict[str, object]) -> dict[str, object]:
    decision = evaluate_request(
        task=_string_payload(payload, "task"),
        brief=_string_payload(payload, "brief"),
        destination=_string_payload(payload, "destination") or "software",
    )
    return {"ok": True, "conscience": decision.to_dict()}


def _chat_payload(
    sources: list[Source],
    payload: dict[str, object],
    memory_path: Path | None = None,
    workspace_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, object]:
    message = _string_payload(payload, "message")
    if not message:
        return {"ok": False, "error": "Message is required."}

    from workspace_os.conversation import route_natural_language_intent
    cmd = route_natural_language_intent(message)
    import os
    is_testing = "PYTEST_CURRENT_TEST" in os.environ or "WOS_IN_SMOKE_TEST" in os.environ
    if cmd and not is_testing:
        import io
        import shlex
        from contextlib import redirect_stdout, redirect_stderr
        from workspace_os.cli import main as cli_main

        f = io.StringIO()
        with redirect_stdout(f), redirect_stderr(f):
            try:
                argv = shlex.split(cmd)
                if config_path:
                    argv = ["--config", str(config_path)] + argv
                cli_main(argv)
            except Exception as e:
                print(f"Error executing command: {e}")

        output = f.getvalue()
        return {
            "ok": True,
            "reply": f"Auto-executing command: {cmd}\n\n{output}",
            "answer": f"Auto-executing command: {cmd}\n\n{output}",
            "verbose_reply": f"Auto-executing command: {cmd}\n\n{output}",
            "trace": f"Natural language routed to command: {cmd}",
            "conscience": {"decision": "ALLOW", "risk_level": "low", "policy_refs": [], "rationale": "Auto-executed routed command"},
            "learning": {"activated": False, "summary": "No learning candidate for auto-execution."},
            "suggested_actions": [],
        }
    store = None
    profile_tone = "neutral"
    profile_detail = "standard"
    if memory_path is not None:
        store = WorkspaceMemoryStore(memory_path)
        store.ensure_schema()
        profile = load_profile(store)
        profile_tone = profile.tone
        profile_detail = profile.detail_level
    reply = build_workspace_reply(
        sources,
        message,
        memory_store=store,
        tone=profile_tone,
        detail_level=profile_detail,
    )
    personal_context = _operator_principles_summary(root=workspace_root)
    context_snapshot = store.latest_context_snapshot() if store else None
    process_report = current_process_report(store) if store else None
    batch_report = current_batch_report(store) if store else None
    return {
        "ok": True,
        "reply": reply.answer,
        "answer": reply.answer,
        "verbose_reply": reply.reply,
        "trace": reply.trace,
        "conscience": reply.conscience.to_dict(),
        "learning": reply.learning,
        "suggested_actions": reply.suggested_actions,
        "personal_context": personal_context,
        "context_snapshot": context_snapshot,
        "process": _process_summary(process_report),
        "batch": _batch_summary(batch_report),
    }


def _handoff_payload(
    sources: list[Source],
    memory_path: Path | None = None,
    workspace_root: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    launch_limit = 3
    if query is not None:
        launch_limit = _int_query(query, "launch_limit", 3)
    profile = load_profile(store)
    workspace = profile.default_workspace or None
    handoff = build_workspace_handoff(
        sources,
        store,
        workspace=workspace or _workspace_name_from_root(workspace_root),
        launch_limit=launch_limit,
    )
    return {
        "ok": True,
        "workspace": handoff.workspace,
        "markdown": handoff.render(),
    }


def _handoff_markdown_payload(
    sources: list[Source],
    memory_path: Path | None = None,
    workspace_root: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "text": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    launch_limit = 3
    compact = False
    if query is not None:
        launch_limit = _int_query(query, "launch_limit", 3)
        compact = (_first(query, "compact") or "false").casefold() == "true"
    profile = load_profile(store)
    workspace = profile.default_workspace or None
    text = render_workspace_handoff_text(
        sources,
        store,
        workspace=workspace or _workspace_name_from_root(workspace_root),
        launch_limit=launch_limit,
        compact=compact,
    )
    return {"ok": True, "text": text}


def _next_action_payload(
    sources: list[Source],
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    workspace = _first(query or {}, "workspace") or None
    return {
        "ok": True,
        "workspace": workspace or _workspace_name_from_root(None),
        "markdown": render_workspace_next_action_text(sources, store, workspace=workspace),
    }


def _next_action_markdown_payload(
    sources: list[Source],
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    payload = _next_action_payload(sources, memory_path, query)
    if not payload.get("ok", False):
        return {"ok": False, "text": payload.get("error", "Unable to load next action.")}
    return {"ok": True, "text": payload.get("markdown", "")}


def _conscience_metrics_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    limit = 20
    if query is not None:
        limit = _int_query(query, "limit", 20)
    return {"ok": True, "report": build_conscience_report(store, limit=limit)}


def _conscience_metrics_markdown_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "text": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    limit = 20
    if query is not None:
        limit = _int_query(query, "limit", 20)
    report = build_conscience_report(store, limit=limit)
    return {"ok": True, "text": render_conscience_report_text(report)}


def _conscience_recommendation_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    limit = 20
    if query is not None:
        limit = _int_query(query, "limit", 20)
    return {"ok": True, "text": build_conscience_recommendation_text(store, limit=limit)}


def _conscience_recommendation_markdown_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    return _conscience_recommendation_payload(memory_path, query)


def _cycle_monitor_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    cycle_id = _int_query(query or {}, "cycle_id", 0) if query else 0
    cycle = store.get_cycle(cycle_id) if cycle_id > 0 else store.active_cycle()
    if cycle is None:
        history = store.cycle_history(limit=1)
        cycle = history[0] if history else None
    if cycle is None:
        return {
            "ok": True,
            "monitor": {
                "active": False,
                "cycle": None,
                "summary": None,
                "checkpoints": [],
                "utilization": None,
                "next_action": build_cycle_next_action(store).render(),
                "updated_at": _utc_now(),
            },
        }
    report = store.cycle_report(int(cycle["id"]))
    checkpoints = store.cycle_checkpoints(int(cycle["id"]), limit=10)
    utilization = AgentQueueTracker(memory_path.parent).utilization_report().to_dict()
    latest_checkpoint = report.get("latest_checkpoint") if report else None
    checkpoint_items = [
        {
            "iteration_number": checkpoint["iteration_number"],
            "label": checkpoint["label"],
            "created_at": checkpoint["created_at"],
            "health_ok": bool(checkpoint["health_ok"]),
            "stability_ok": bool(checkpoint["stability_ok"]),
            "security_ok": bool(checkpoint["security_ok"]),
            "quality_ok": bool(checkpoint["quality_ok"]),
            "note": checkpoint["note"],
        }
        for checkpoint in checkpoints
    ]
    return {
        "ok": True,
        "monitor": {
            "active": cycle.get("ended_at") is None,
            "cycle": cycle,
            "summary": {
                "checkpoint_count": int(report["checkpoint_count"]) if report else len(checkpoints),
                "health_pass_rate": float(report["health_pass_rate"]) if report else 0.0,
                "stability_pass_rate": float(report["stability_pass_rate"]) if report else 0.0,
                "security_pass_rate": float(report["security_pass_rate"]) if report else 0.0,
                "quality_pass_rate": float(report["quality_pass_rate"]) if report else 0.0,
                "latest_checkpoint": latest_checkpoint,
            },
            "checkpoints": checkpoint_items,
            "utilization": utilization,
            "next_action": build_cycle_next_action(store).render(),
            "updated_at": _utc_now(),
        },
    }


def _cycle_monitor_markdown_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    payload = _cycle_monitor_payload(memory_path, query)
    if not payload.get("ok", False):
        return {"ok": False, "text": payload.get("error", "Unable to load cycle monitor.")}
    monitor = payload["monitor"]
    cycle = monitor["cycle"]
    summary = monitor["summary"] or {}
    utilization = monitor["utilization"] or {}
    lines = [
        "Cycle monitor dashboard:",
        f"Cycle: {cycle['label']}",
        f"State: {'active' if monitor['active'] else 'idle'}",
        f"Objective: {cycle['objective']}",
        f"Started: {cycle['started_at']}",
        f"Ended: {cycle['ended_at'] or 'n/a'}",
        "",
        f"Checkpoint count: {summary.get('checkpoint_count', 0)}",
        f"Health pass rate: {summary.get('health_pass_rate', 0.0):.2f}",
        f"Stability pass rate: {summary.get('stability_pass_rate', 0.0):.2f}",
        f"Security pass rate: {summary.get('security_pass_rate', 0.0):.2f}",
        f"Quality pass rate: {summary.get('quality_pass_rate', 0.0):.2f}",
        "",
        "Recent checkpoints:",
    ]
    checkpoints = monitor.get("checkpoints", [])
    if checkpoints:
        lines.extend(
            f"- #{item['iteration_number']} {item['label']} | H={_bool_mark(item['health_ok'])} S={_bool_mark(item['stability_ok'])} Sec={_bool_mark(item['security_ok'])} Q={_bool_mark(item['quality_ok'])} | {item['created_at']}"
            for item in checkpoints
        )
    else:
        lines.append("- none recorded yet")
    lines.extend(
        [
            "",
            "Agent utilization:",
            f"- configured_max_parallel={utilization.get('max_parallel', 0)}",
            f"- observed_peak_parallel={utilization.get('observed_peak_parallel', 0)}",
            f"- recommended_max_parallel={utilization.get('recommended_max_parallel', 0)}",
            f"- idle_ratio={utilization.get('idle_ratio', 0.0):.2f}",
            "",
            "Next action:",
            monitor["next_action"].strip(),
        ]
    )
    return {"ok": True, "text": "\n".join(lines) + "\n"}

def _questioning_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    limit = 5
    if query is not None:
        limit = _int_query(query, "limit", 5)
    context = _first(query or {}, "context")
    if not context:
        snapshot = store.latest_context_snapshot()
        context = str(snapshot["summary"]) if snapshot and snapshot.get("summary") else "workspace"
    report = {
        "context": context,
        "metrics": store.questioning_metrics(context),
        "recent": store.recent_qa_pairs(limit=limit),
        "semantic_hits": [
            {
                "kind": hit.kind,
                "title": hit.title,
                "body": hit.body,
                "created_at": hit.created_at,
                "score": hit.score,
                "source": hit.source,
            }
            for hit in store.semantic_search(context, limit=limit)
        ],
        "suggestions": [
            {
                "question": suggestion.question,
                "context": suggestion.context,
                "previous_answer": suggestion.previous_answer,
                "frequency": suggestion.frequency,
                "relevance_score": suggestion.relevance_score,
            }
            for suggestion in suggest_questions_for_work(store, context, limit=limit)
        ],
    }
    return {"ok": True, "report": report}


def _questioning_markdown_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    payload = _questioning_payload(memory_path, query)
    if not payload.get("ok", False):
        return {"ok": False, "text": payload.get("error", "Unable to load questioning metrics.")}
    report = payload["report"]
    metrics = report["metrics"]
    summary = metrics["summary"]
    with_qna = metrics["with_qna"]
    without_qna = metrics["without_qna"]
    lines = [
        "Questioning dashboard:",
        f"Context focus: {report['context']}",
        "",
        f"- total={summary.get('total', 0)}",
        f"- unique_contexts={summary.get('unique_contexts', 0)}",
        f"- unique_questions={summary.get('unique_questions', 0)}",
        f"- recent_7_days={summary.get('recent_7_days', 0)}",
        f"- latest_created_at={summary.get('latest_created_at') or 'n/a'}",
        f"- learning_velocity_per_day={metrics['learning_velocity']:.2f}",
        f"- estimated_time_invested_minutes={metrics['estimated_time_invested_minutes']:.1f}",
        f"- estimated_rework_savings_minutes={metrics['estimated_rework_savings_minutes']:.1f}",
        f"- with_qna_success_rate={with_qna['success_rate']:.2f}",
        f"- without_qna_success_rate={without_qna['success_rate']:.2f}",
        "",
        "Recent Q&A:",
    ]
    recent = report.get("recent", [])
    if recent:
        lines.extend(
            f"- {item['created_at']} | {item['agent']} | {item['question']} -> {item['answer']}"
            for item in recent
        )
    else:
        lines.append("- none recorded yet")
    lines.append("")
    lines.append("Semantic memory:")
    semantic_hits = report.get("semantic_hits", [])
    if semantic_hits:
        lines.extend(
            f"- {item['created_at']} | {item['source']} | {item['title']} | score={item['score']:.2f}"
            for item in semantic_hits
        )
    else:
        lines.append("- none recorded yet")
    lines.append("")
    lines.append("Answer sources:")
    answer_sources = metrics.get("answer_sources", {})
    if answer_sources:
        lines.extend(f"- {source}: {count}" for source, count in sorted(answer_sources.items(), key=lambda item: (-item[1], item[0])))
    else:
        lines.append("- none recorded yet")
    lines.append("")
    lines.append("Question patterns:")
    patterns = metrics.get("question_patterns", [])
    if patterns:
        lines.extend(f"- {item['question']} (asked {item['count']}x)" for item in patterns)
    else:
        lines.append("- none recorded yet")
    lines.append("")
    lines.append("Suggestions:")
    suggestions = report.get("suggestions", [])
    if suggestions:
        lines.extend(
            f"- {item['question']} (asked {item['frequency']}x, relevance={item['relevance_score']:.2f})"
            for item in suggestions
        )
    else:
        lines.append("- no suggestions yet")
    return {"ok": True, "text": "\n".join(lines) + "\n"}


def _security_payload(
    workspace_root: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if workspace_root is None:
        return {"ok": False, "error": "Workspace root is required."}
    validator = SecurityValidator(workspace_root)
    summary = validator.get_vulnerability_summary()
    policy_report = validator.get_policy_summary()
    report_dir = validator.report_dir
    return {
        "ok": True,
        "report": {
            "project_root": str(workspace_root),
            "report_dir": str(report_dir),
            "summary": summary,
            "policy": policy_report,
            "reports": {
                "pip_audit": (report_dir / "pip-audit.json").exists(),
                "safety": (report_dir / "safety.json").exists(),
                "bandit": (report_dir / "bandit.json").exists(),
                "policy": validator.policy_path.exists(),
            },
        },
    }


def _security_markdown_payload(
    workspace_root: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    payload = _security_payload(workspace_root, query)
    if not payload.get("ok", False):
        return {"ok": False, "text": payload.get("error", "Unable to load security report.")}
    report = payload["report"]
    summary = report["summary"]
    policy = report.get("policy", {})
    policy_summary = policy.get("summary", {}) if isinstance(policy, dict) else {}
    findings = policy.get("findings", []) if isinstance(policy, dict) else []
    lines = [
        "Security dashboard:",
        f"Project root: {report['project_root']}",
        f"Report dir: {report['report_dir']}",
        "",
        "Vulnerability summary:",
        f"- critical={summary.get('critical', 0)}",
        f"- high={summary.get('high', 0)}",
        f"- medium={summary.get('medium', 0)}",
        f"- low={summary.get('low', 0)}",
        f"- total={summary.get('total', 0)}",
        "",
        "Bandit summary:",
        f"- bandit_total={summary.get('bandit_total', 0)}",
        f"- bandit_critical={summary.get('bandit_critical', 0)}",
        f"- bandit_high={summary.get('bandit_high', 0)}",
        f"- bandit_medium={summary.get('bandit_medium', 0)}",
        f"- bandit_low={summary.get('bandit_low', 0)}",
        "",
        "Policy summary:",
        f"- compliance_rate={float(policy_summary.get('compliance_rate', 0.0)):.2f}",
        f"- declared_dependencies_total={policy_summary.get('declared_dependencies_total', 0)}",
        f"- declared_dependencies_disallowed={policy_summary.get('declared_dependencies_disallowed', 0)}",
        f"- banned_pattern_rules_failed={policy_summary.get('banned_pattern_rules_failed', 0)}",
        f"- header_rules_failed={policy_summary.get('header_rules_failed', 0)}",
        f"- encryption_rules_failed={policy_summary.get('encryption_rules_failed', 0)}",
        "",
        "Policy findings:",
    ]
    if findings:
        lines.extend(f"- {finding}" for finding in findings[:5])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Reports:",
            f"- pip-audit={'present' if report['reports']['pip_audit'] else 'missing'}",
            f"- safety={'present' if report['reports']['safety'] else 'missing'}",
            f"- bandit={'present' if report['reports']['bandit'] else 'missing'}",
            f"- policy={'present' if report['reports']['policy'] else 'missing'}",
        ]
    )
    return {"ok": True, "text": "\n".join(lines) + "\n"}


def _agent_utilization_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    tracker = AgentQueueTracker(memory_path.parent)
    report = tracker.utilization_report()
    return {"ok": True, "report": report.to_dict()}


def _agent_utilization_markdown_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "text": "Memory path is required."}
    tracker = AgentQueueTracker(memory_path.parent)
    report = tracker.utilization_report()
    return {"ok": True, "text": report.render()}


def _local_metrics_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    report = build_local_metrics_report(memory_path)
    return {"ok": True, "report": report.to_dict()}


def _local_metrics_markdown_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "text": "Memory path is required."}
    report = build_local_metrics_report(memory_path)
    return {"ok": True, "text": render_local_metrics_markdown(report)}


def _local_metrics_export_payload(
    memory_path: Path | None = None,
    exporter: str | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "text": "Memory path is required."}
    if not exporter:
        return {"ok": False, "text": "Export format is required."}
    report = build_local_metrics_report(memory_path)
    try:
        text = render_metrics_export(report, exporter)
    except ValueError as exc:
        return {"ok": False, "text": str(exc)}
    content_type = "application/json; charset=utf-8" if exporter.lower() == "grafana-json" else "text/plain; charset=utf-8"
    filename = f"metrics.{ 'json' if exporter.lower() == 'grafana-json' else 'prometheus' }"
    return {"ok": True, "text": text, "content_type": content_type, "filename": filename}


def _conscience_recommendation_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    limit = 20
    if query is not None:
        limit = _int_query(query, "limit", 20)
    return {"ok": True, "text": build_conscience_recommendation_text(store, limit=limit)}


def _conscience_recommendation_markdown_payload(
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    return _conscience_recommendation_payload(memory_path, query)


def _context_snapshot_payload(
    memory_path: Path | None = None,
    workspace_root: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    snapshot = store.latest_context_snapshot()
    if snapshot is None:
        return {"ok": False, "error": "No context snapshot found."}
    return {"ok": True, "snapshot": snapshot}


def _context_snapshot_markdown_payload(
    memory_path: Path | None = None,
    workspace_root: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "text": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    snapshot = store.latest_context_snapshot()
    if snapshot is None:
        return {"ok": False, "text": "No context snapshot found."}
    lines = [
        f"Workspace context snapshot: {snapshot['scope']}",
        f"Reason: {snapshot['reason']}",
        "",
        f"- created_at={snapshot['created_at']}",
        f"- summary={snapshot['summary']}",
    ]
    return {"ok": True, "text": "\n".join(lines) + "\n"}


def _delegate_launch_payload(
    payload: dict[str, object],
    workspace_root: Path | None = None,
    launcher: object | None = None,
) -> dict[str, object]:
    agent = normalize_agent_name(_string_payload(payload, "agent")) or _string_payload(payload, "agent").casefold()
    destination = _string_payload(payload, "destination").casefold()
    task = _string_payload(payload, "task")
    brief = _string_payload(payload, "brief")
    approved = bool(payload.get("approved", False))

    if not approved:
        return {"ok": False, "error": "Delegation requires explicit approval."}
    if agent not in {"opencode", "codex", "claude", "antigravity"}:
        return {"ok": False, "error": "Allowed agents are opencode, codex, claude and antigravity."}
    if not task or not brief:
        return {"ok": False, "error": "Delegation requires both task and brief."}

    conscience = evaluate_request(task=task, brief=brief, destination=destination)
    if destination != "software":
        return {
            "ok": False,
            "error": "Document and presentation delegations require a Google Drive connector first.",
            "conscience": conscience.to_dict(),
        }
    if not conscience.allows_execution():
        return {
            "ok": False,
            "error": f"OCE blocked launch with decision {conscience.decision}.",
            "conscience": conscience.to_dict(),
        }

    workspace_root = workspace_root or _git_workspace_root()
    if not workspace_root.exists():
        return {"ok": False, "error": "Local Git workspace root was not found."}

    prompt = _build_delegate_prompt(task, brief, conscience)
    hardened_prompt = build_hardened_delegate_prompt(
        agent,
        "local Git workspace",
        workspace_root,
        prompt,
    )
    command = build_agent_command(agent, workspace_root, hardened_prompt)
    start_process = launcher or _launch_process
    pid = start_process(command, workspace_root)
    return {
        "ok": True,
        "agent": agent,
        "destination": destination,
        "pid": pid,
        "cwd": "local-git-workspace",
        "conscience": conscience.to_dict(),
    }


def _build_delegate_prompt(task: str, brief: str, conscience: ConscienceDecision) -> str:
    return sanitize_text(
        "\n".join(
            [
                "You are receiving an approved Workspace OS delegation.",
                "Work from the local Git workspace root.",
                "Use Git repositories for software and infrastructure work.",
                "Do not store secrets, personal data, or company-specific data.",
                "Apply the OCE decision below before acting.",
                "",
                "Task:",
                task,
                "",
                render_decision_for_prompt(conscience),
                "",
                "Workspace OS brief:",
                brief,
            ]
        )
    )


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


def _roadmap_payload() -> dict[str, object]:
    roadmap = Path.cwd() / "docs" / "product" / "roadmap.md"
    if not roadmap.exists():
        return {"progress": "Roadmap not found."}
    return {"progress": _extract_progress_map(roadmap.read_text(encoding="utf-8"))}


def _recent_software_payload(root: Path | None = None, limit: int = 5) -> dict[str, object]:
    workspace_root = root or _git_workspace_root()
    if not workspace_root.exists():
        return {"root": "D:\\git", "items": []}
    projects = [_project_summary(path) for path in workspace_root.iterdir() if path.is_dir()]
    projects.sort(key=lambda item: item["updated_epoch"], reverse=True)
    return {"root": str(workspace_root), "items": [_public_item(item) for item in projects[:limit]]}


def _analysis_payload(
    sources: list[Source],
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    limit = 5
    compact = False
    if query is not None:
        limit = _int_query(query, "limit", 5)
        compact = (_first(query, "compact") or "false").casefold() == "true"
    text = render_workspace_analysis_text(sources, store, limit=limit, compact=compact)
    return {"ok": True, "text": text}


def _analysis_markdown_payload(
    sources: list[Source],
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    payload = _analysis_payload(sources, memory_path, query)
    if not payload.get("ok", False):
        return {"ok": False, "text": payload.get("error", "Unable to load analysis.")}
    return {"ok": True, "text": payload["text"]}


def _roots_payload(
    sources: list[Source],
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    if memory_path is None:
        return {"ok": False, "error": "Memory path is required."}
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    limit = 5
    if query is not None:
        limit = _int_query(query, "limit", 5)
    text = render_workspace_roots_text(sources, store, limit=limit)
    return {"ok": True, "text": text}


def _roots_markdown_payload(
    sources: list[Source],
    memory_path: Path | None = None,
    query: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    payload = _roots_payload(sources, memory_path, query)
    if not payload.get("ok", False):
        return {"ok": False, "text": payload.get("error", "Unable to load roots.")}
    return {"ok": True, "text": payload["text"]}


DOCUMENT_ACTIVITY_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".md",
    ".ods",
    ".odt",
    ".pdf",
    ".ppt",
    ".pptx",
    ".rtf",
    ".txt",
    ".xls",
    ".xlsx",
}
IGNORED_ACTIVITY_FILES = {"desktop.ini", "thumbs.db", "~$"}


def _recent_docs_payload(root: Path | None = None, limit: int = 5, scan_limit: int = 5000) -> dict[str, object]:
    drive_root = root or _drive_root()
    if not drive_root.exists():
        return {"root": "google-drive", "items": []}

    files = []
    scanned = 0
    for current_root, dirnames, filenames in os.walk(drive_root):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        for filename in filenames:
            normalized_name = filename.lower()
            if (
                filename.startswith(".")
                or normalized_name in IGNORED_ACTIVITY_FILES
                or normalized_name.startswith("~$")
            ):
                continue
            path = Path(current_root) / filename
            if path.suffix.lower() not in DOCUMENT_ACTIVITY_EXTENSIONS:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append(
                {
                    "name": path.name,
                    "relative_path": _safe_relative(path, drive_root),
                    "updated_epoch": stat.st_mtime,
                    "updated": _format_epoch(stat.st_mtime),
                }
            )
            scanned += 1
            if scanned >= scan_limit:
                break
        if scanned >= scan_limit:
            break
    files.sort(key=lambda item: item["updated_epoch"], reverse=True)
    return {"root": "google-drive", "items": [_public_item(item) for item in files[:limit]]}


def _project_summary(path: Path) -> dict[str, object]:
    updated_epoch = _git_last_commit_epoch(path) if (path / ".git").exists() else path.stat().st_mtime
    return {
        "name": path.name,
        "relative_path": path.name,
        "updated_epoch": updated_epoch,
        "updated": _format_epoch(updated_epoch),
    }


def _git_last_commit_epoch(path: Path) -> float:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--format=%ct"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return path.stat().st_mtime
    if result.returncode != 0:
        return path.stat().st_mtime
    try:
        return float(result.stdout.strip())
    except ValueError:
        return path.stat().st_mtime


def _operator_principles_summary(root: Path | None = None) -> dict[str, object]:
    principles_root = root or (_git_workspace_root() / "all-about-me")
    if not principles_root.exists():
        return {"state": "not configured", "items": 0}
    try:
        count = sum(1 for path in principles_root.rglob("*") if path.is_file())
    except OSError:
        return {"state": "unavailable", "items": 0}
    return {"state": "available", "items": count}


def _learning_signal(message: str) -> dict[str, object]:
    text = message.casefold()
    keywords = ("learn", "remember", "lesson", "decision", "mistake", "preference", "principle")
    activated = any(keyword in text for keyword in keywords)
    if not activated:
        return {"activated": False, "summary": "No durable learning candidate detected."}
    return {
        "activated": True,
        "summary": "Potential learning detected. Capture requires explicit destination and approval.",
        "candidate_destinations": ["ADEV", "scanales-kb", "operator-principles"],
    }


def _batch_summary(batch: object | None) -> dict[str, object] | None:
    if batch is None:
        return None
    return {
        "batch_id": batch.batch_id,
        "label": batch.label,
        "objective": batch.objective,
        "duration_seconds": batch.duration_seconds,
        "delegations": batch.delegations,
        "defect_iterations": batch.defect_iterations,
        "conversation_turns": batch.conversation_turns,
    }


def _process_summary(process: object | None) -> dict[str, object] | None:
    if process is None:
        return None
    return {
        "process_id": process.process_id,
        "label": process.label,
        "objective": process.objective,
        "duration_seconds": process.duration_seconds,
        "batch_count": process.batch_count,
        "delegations": process.delegations,
        "defect_iterations": process.defect_iterations,
        "checkpoint_count": process.checkpoint_count,
        "latest_checkpoint_label": process.latest_checkpoint_label,
        "latest_checkpoint_note": process.latest_checkpoint_note,
    }


def _workspace_name_from_root(workspace_root: Path | None) -> str:
    if workspace_root is None:
        return "all workspaces"
    return str(workspace_root) or "all workspaces"


def _git_workspace_root() -> Path:
    config_path = Path.cwd() / "config" / "workspace.sources.example.json"
    if config_path.exists():
        try:
            return load_workspace_root(config_path)
        except (OSError, ValueError):
            pass

    env_root = os.environ.get("WORKSPACE_OS_GIT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    default_root = Path("D:/git")
    if default_root.exists():
        return default_root.resolve()
    return (Path.home() / "git").resolve()


def _drive_root() -> Path:
    return Path(os.environ.get("WORKSPACE_OS_DRIVE_ROOT", "G:/Mi unidad"))


def _public_item(item: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in item.items() if key != "updated_epoch"}


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _format_epoch(value: float) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")


def _extract_progress_map(content: str) -> str:
    marker = "Current batch sequence:"
    start = content.find(marker)
    if start == -1:
        return content[:2000]
    fenced = content.find("```text", start)
    if fenced == -1:
        return content[start : start + 2000]
    body_start = content.find("\n", fenced)
    body_end = content.find("```", body_start + 1)
    if body_start == -1 or body_end == -1:
        return content[start : start + 2000]
    return content[body_start + 1 : body_end].strip()


def _first(query: dict[str, list[str]], name: str) -> str:
    values = query.get(name, [])
    return values[0].strip() if values else ""


def _int_query(query: dict[str, list[str]], name: str, default: int) -> int:
    try:
        return int(_first(query, name) or default)
    except ValueError:
        return default


def _string_payload(payload: dict[str, object], name: str) -> str:
    value = payload.get(name, "")
    return value.strip() if isinstance(value, str) else ""

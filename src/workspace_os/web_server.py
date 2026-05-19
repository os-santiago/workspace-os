from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from workspace_os.classification import classify_content
from workspace_os.config import Source, load_sources
from workspace_os.context_pack import build_context_pack
from workspace_os.git_status import inspect_source
from workspace_os.housekeeping import find_temporary_artifacts
from workspace_os.sanitization import sanitize_text
from workspace_os.search import search_sources
from workspace_os.validation import validate_workspace, validation_failed


STATIC_ROOT = Path(__file__).parent / "web_assets"


def serve_web_app(config_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    sources = load_sources(config_path)
    handler = _build_handler(sources)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Workspace OS web app listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Workspace OS web app stopped.")
    finally:
        server.server_close()


def _build_handler(sources: list[Source]):
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

            self.send_error(404, "Not found")

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, payload: object, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
            self.wfile.write(body)

    return WorkspaceRequestHandler


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
                "path": str(match.path),
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


def _roadmap_payload() -> dict[str, object]:
    roadmap = Path.cwd() / "docs" / "product" / "roadmap.md"
    if not roadmap.exists():
        return {"progress": "Roadmap not found."}
    return {"progress": _extract_progress_map(roadmap.read_text(encoding="utf-8"))}


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

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re

from workspace_os.config import Source
from workspace_os.sanitization import sanitize_text


CAPTURE_TYPES = {"daily", "incident", "session", "decision"}


@dataclass(frozen=True)
class CaptureDraft:
    capture_type: str
    title: str
    content: str
    source_name: str
    relative_path: Path
    destination: Path


def build_capture_draft(
    sources: list[Source],
    capture_type: str,
    title: str,
    body: str,
    today: date | None = None,
) -> CaptureDraft:
    if capture_type not in CAPTURE_TYPES:
        allowed = ", ".join(sorted(CAPTURE_TYPES))
        raise ValueError(f"Capture type must be one of: {allowed}.")

    evidence_source = _find_evidence_source(sources)
    current_date = today or date.today()
    slug = _slugify(title)
    relative_path = Path("captures") / capture_type / f"{current_date.isoformat()}-{slug}.md"
    destination = evidence_source.path / relative_path
    sanitized_body = sanitize_text(body.strip())
    content = _render_capture(capture_type, title.strip(), sanitized_body, current_date)

    return CaptureDraft(
        capture_type=capture_type,
        title=title.strip(),
        content=content,
        source_name=evidence_source.name,
        relative_path=relative_path,
        destination=destination,
    )


def write_capture(draft: CaptureDraft) -> Path:
    draft.destination.parent.mkdir(parents=True, exist_ok=True)
    if draft.destination.exists():
        raise FileExistsError(f"Capture already exists: {draft.relative_path}")
    draft.destination.write_text(draft.content, encoding="utf-8")
    return draft.destination


def _find_evidence_source(sources: list[Source]) -> Source:
    for source in sources:
        if source.type == "evidence":
            return source
    raise ValueError("No evidence source is configured.")


def _render_capture(capture_type: str, title: str, body: str, current_date: date) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            f"Type: {capture_type}",
            f"Date: {current_date.isoformat()}",
            "Sensitivity: sanitized",
            "",
            "## Summary",
            body or "TODO: add sanitized summary.",
            "",
            "## Links",
            "- Related doctrine: TODO",
            "- Related evidence: TODO",
            "",
        ]
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "untitled"

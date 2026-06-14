from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from workspace_os.conscience import ConscienceDecision, evaluate_request
from workspace_os.config import Source
from workspace_os.memory import MemoryHit, WorkspaceMemoryStore
from workspace_os.sanitization import sanitize_text
from workspace_os.search import SearchMatch, search_sources


@dataclass(frozen=True)
class WorkspaceReply:
    reply: str
    conscience: ConscienceDecision
    learning: dict[str, object]
    source_matches: list[SearchMatch]
    memory_hits: list[MemoryHit]


def build_workspace_reply(
    sources: list[Source],
    message: str,
    memory_store: WorkspaceMemoryStore | None = None,
    session_id: str = "default",
) -> WorkspaceReply:
    clean_message = message.strip()
    conscience = evaluate_request(clean_message, destination="software")
    source_matches = search_sources(sources, clean_message, max_results=5)
    memory_hits = memory_store.search(clean_message, limit=5) if memory_store else []
    learning = _learning_signal(clean_message, memory_hits)

    if memory_store:
        request_hash = _hash_text(clean_message)
        memory_store.record_turn(session_id=session_id, role="user", message=clean_message)
        memory_store.record_decision(
            request_hash=request_hash,
            risk_level=conscience.risk_level,
            decision=conscience.decision,
            missing_context=conscience.missing_context,
        )

    lines = [
        "Request received.",
        "",
        f"Conscience: {conscience.decision} ({conscience.risk_level})",
        f"Strategy: {conscience.response_strategy}",
        f"Rationale: {conscience.rationale}",
        "",
        f"Learning engine: {'activated' if learning['activated'] else 'standby'}",
        learning["summary"],
    ]

    if memory_hits:
        lines.extend(["", "Memory signals:"])
        lines.extend([hit.render() for hit in memory_hits[:3]])

    if source_matches:
        lines.extend(["", "Related knowledge:"])
        lines.extend(
            [
                f"- {match.source_name}:{match.path}:{match.line_number}: {sanitize_text(match.line)}"
                for match in source_matches[:3]
            ]
        )

    reply = sanitize_text("\n".join(lines))

    if memory_store:
        memory_store.record_turn(session_id=session_id, role="assistant", message=reply)

    return WorkspaceReply(
        reply=reply,
        conscience=conscience,
        learning=learning,
        source_matches=source_matches,
        memory_hits=memory_hits,
    )


def _learning_signal(message: str, memory_hits: list[MemoryHit]) -> dict[str, object]:
    text = message.casefold()
    keywords = ("learn", "remember", "lesson", "decision", "mistake", "preference", "principle")
    activated = any(keyword in text for keyword in keywords) or bool(memory_hits)
    if not activated:
        return {"activated": False, "summary": "No durable learning candidate detected."}
    return {
        "activated": True,
        "summary": "Potential learning detected. Stored turn and context can be reused in later requests.",
        "candidate_destinations": ["workspace-memory", "ADEV", "scanales-kb"],
    }


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()

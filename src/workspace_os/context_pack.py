from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workspace_os.config import Source
from workspace_os.memory import MemoryHit, SemanticMemoryHit, WorkspaceMemoryStore
from workspace_os.git_status import GitStatus, inspect_source
from workspace_os.sanitization import sanitize_text
from workspace_os.search import SearchMatch, search_sources


DEFAULT_DOCTRINE_LINES = 80


@dataclass(frozen=True)
class ContextPack:
    topic: str
    statuses: list[GitStatus]
    doctrine_excerpt: list[str]
    matches: list[SearchMatch]
    memory_hits: list[MemoryHit]
    semantic_hits: list[SemanticMemoryHit]

    def render_markdown(self) -> str:
        sections = [
            "# Workspace OS Agent Context Pack",
            "",
            "## Task Topic",
            sanitize_text(self.topic),
            "",
            "## Required Agent Behavior",
            "- Apply the upstream ADEV doctrine before doing work.",
            "- Inspect repository state before editing and preserve other agents' local work.",
            "- Search existing doctrine and evidence before adding durable content.",
            "- Keep committed content in English.",
            "- Do not store secrets, personal data, company-specific data, or sensitive raw outputs.",
            "- Validate changed files with the narrowest meaningful checks before handoff.",
            "- Remove or consolidate temporary artifacts before completing the task.",
            "",
            "## Source State",
            *self._render_statuses(),
            "",
            "## Doctrine Excerpt",
            *self._render_doctrine_excerpt(),
            "",
            "## Relevant Existing Knowledge",
            *self._render_matches(),
            "",
            "## Recent Memory",
            *self._render_memory_hits(),
            "",
            "## Semantic Memory",
            *self._render_semantic_hits(),
            "",
            "## Handoff Expectations",
            "- Summarize changes, validation, residual risks, and repository state.",
            "- Use a branch and PR for repository changes unless the repository is being initialized.",
        ]
        return "\n".join(sections).rstrip() + "\n"

    def _render_statuses(self) -> list[str]:
        if not self.statuses:
            return ["- No configured sources."]

        lines = []
        for status in self.statuses:
            if not status.exists:
                lines.append(f"- {status.source.name} ({status.source.type}): missing")
                continue
            if not status.is_git_repo:
                lines.append(f"- {status.source.name} ({status.source.type}): not a Git repository")
                continue
            if status.error:
                lines.append(f"- {status.source.name} ({status.source.type}): error")
                continue

            divergence = ""
            if status.ahead or status.behind:
                divergence = f", ahead {status.ahead}, behind {status.behind}"
            lines.append(
                f"- {status.source.name} ({status.source.type}): {status.state}, "
                f"branch {status.branch}, changes {status.dirty_count}, "
                f"untracked {status.untracked_count}{divergence}"
            )
        return lines

    def _render_doctrine_excerpt(self) -> list[str]:
        if not self.doctrine_excerpt:
            return ["No ADEV excerpt found in configured doctrine sources."]
        return [f"> {sanitize_text(line)}" if line else ">" for line in self.doctrine_excerpt]

    def _render_matches(self) -> list[str]:
        if not self.matches:
            return ["No matches found for the task topic."]
        return [
            f"- {match.source_name}:{match.path}:{match.line_number}: {sanitize_text(match.line)}"
            for match in self.matches
        ]

    def _render_memory_hits(self) -> list[str]:
        if not self.memory_hits:
            return ["No memory entries found for the task topic."]
        return [hit.render() for hit in self.memory_hits]

    def _render_semantic_hits(self) -> list[str]:
        if not self.semantic_hits:
            return ["No semantically similar memory entries found for the task topic."]
        return [hit.render() for hit in self.semantic_hits]


def build_context_pack(
    sources: list[Source],
    topic: str,
    max_matches: int = 20,
    max_doctrine_lines: int = DEFAULT_DOCTRINE_LINES,
    memory_path: Path | None = None,
) -> ContextPack:
    statuses = [inspect_source(source) for source in sources]
    doctrine_excerpt = _load_doctrine_excerpt(sources, max_doctrine_lines)
    matches = search_sources(sources=sources, query=topic, max_results=max_matches) if topic.strip() else []
    memory_hits = _load_memory_excerpt(memory_path, topic, max_matches)
    semantic_hits = _load_semantic_memory_excerpt(memory_path, topic, max_matches)
    return ContextPack(
        topic=topic,
        statuses=statuses,
        doctrine_excerpt=doctrine_excerpt,
        matches=matches,
        memory_hits=memory_hits,
        semantic_hits=semantic_hits,
    )


def _load_doctrine_excerpt(sources: list[Source], max_lines: int) -> list[str]:
    for source in sources:
        if source.type != "doctrine":
            continue
        for candidate in _doctrine_candidates(source.path):
            if candidate.exists() and candidate.is_file():
                return _read_first_lines(candidate, max_lines)
    return []


def _doctrine_candidates(root: Path) -> list[Path]:
    return [root / "ADEV.md", root / "README.md"]


def _read_first_lines(path: Path, max_lines: int) -> list[str]:
    lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                lines.append(line.rstrip())
                if len(lines) >= max_lines:
                    break
    except OSError:
        return []
    return lines


def _load_memory_excerpt(memory_path: Path | None, topic: str, max_matches: int) -> list[MemoryHit]:
    if memory_path is None:
        return []
    store = WorkspaceMemoryStore(memory_path)
    if not memory_path.exists():
        return []
    try:
        return store.search(topic, limit=max_matches) if topic.strip() else store.recent(limit=max_matches)
    except OSError:
        return []


def _load_semantic_memory_excerpt(memory_path: Path | None, topic: str, max_matches: int) -> list[SemanticMemoryHit]:
    if memory_path is None or not memory_path.exists() or not topic.strip():
        return []
    store = WorkspaceMemoryStore(memory_path)
    try:
        return store.semantic_search(topic, limit=max_matches)
    except OSError:
        return []

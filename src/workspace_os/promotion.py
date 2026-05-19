from __future__ import annotations

from dataclasses import dataclass

from workspace_os.config import Source
from workspace_os.sanitization import sanitize_text
from workspace_os.search import SearchMatch, search_sources


@dataclass(frozen=True)
class PromotionProposal:
    target: str
    rule: str
    evidence: str
    matches: list[SearchMatch]

    def render_markdown(self) -> str:
        lines = [
            "# Promotion Proposal",
            "",
            f"Target: {self.target}",
            "Mode: proposal-only",
            "",
            "## Proposed Rule",
            sanitize_text(self.rule),
            "",
            "## Evidence Reference",
            sanitize_text(self.evidence),
            "",
            "## Existing Related Content",
            *self._render_matches(),
            "",
            "## Required Follow-up",
            "- Review related content before editing doctrine.",
            "- Apply the change through a dedicated branch and PR.",
            "- Validate the target repository before merge.",
            "- Keep committed content generic, impersonal, and sanitized.",
            "",
        ]
        return "\n".join(lines)

    def _render_matches(self) -> list[str]:
        if not self.matches:
            return ["No related content found."]
        return [
            f"- {match.source_name}:{match.path}:{match.line_number}: {sanitize_text(match.line)}"
            for match in self.matches
        ]


def build_promotion_proposal(
    sources: list[Source],
    target: str,
    rule: str,
    evidence: str,
    max_matches: int = 10,
) -> PromotionProposal:
    if target not in {"adev", "scanales-kb", "homedir", "google"}:
        raise ValueError("Promotion target must be one of: adev, scanales-kb, homedir, google.")
    query = rule.strip() or evidence.strip()
    matches = search_sources(sources, query=query, max_results=max_matches) if query else []
    return PromotionProposal(
        target=target,
        rule=sanitize_text(rule.strip()),
        evidence=sanitize_text(evidence.strip()),
        matches=matches,
    )

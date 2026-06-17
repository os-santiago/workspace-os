from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedbackAssessment:
    status: str
    reason: str
    has_objection: bool
    has_praise: bool
    error_type: str

    def render(self) -> str:
        flags = []
        if self.has_objection:
            flags.append("objection")
        if self.has_praise:
            flags.append("praise")
        flag_text = ", ".join(flags) if flags else "neutral"
        return f"status={self.status} flags={flag_text} error_type={self.error_type} reason={self.reason}"


def assess_feedback(request_text: str, result_text: str, feedback_text: str) -> FeedbackAssessment:
    text = feedback_text.casefold().strip()
    if not text:
        return FeedbackAssessment(
            status="positive",
            reason="No objections or praise were detected.",
            has_objection=False,
            has_praise=False,
            error_type="none",
        )

    objection_markers = (
        "objection",
        "object",
        "not useful",
        "no sirve",
        "not helpful",
        "mal",
        "wrong",
        "incorrect",
        "issue",
        "problem",
        "mejorar",
        "fix",
        "fail",
        "error",
    )
    praise_markers = (
        "great",
        "excellent",
        "good",
        "well done",
        "nice",
        "perfect",
        "great job",
        "excellent work",
        "muy bien",
        "buen trabajo",
        "felicit",
        "thanks",
        "thank you",
        "gracias",
    )

    has_objection = any(marker in text for marker in objection_markers)
    has_praise = any(marker in text for marker in praise_markers)
    error_type = _infer_error_type(request_text, result_text, text, has_objection, has_praise)

    if has_objection:
        return FeedbackAssessment(
            status="questionable",
            reason="An objection or correction was detected in the feedback.",
            has_objection=True,
            has_praise=has_praise,
            error_type=error_type,
        )
    if has_praise:
        return FeedbackAssessment(
            status="over_expectation",
            reason="A congratulatory or positive reinforcement signal was detected.",
            has_objection=False,
            has_praise=True,
            error_type="positive",
        )
    return FeedbackAssessment(
        status="positive",
        reason="No objections were detected and the feedback is treated as positive.",
        has_objection=False,
        has_praise=False,
        error_type="positive",
    )


def _infer_error_type(request_text: str, result_text: str, feedback_text: str, has_objection: bool, has_praise: bool) -> str:
    del request_text
    if has_praise:
        return "positive"
    if not has_objection:
        return "neutral"
    text = f"{feedback_text}\n{result_text}".casefold()
    if any(marker in text for marker in ("verbose", "too long", "long", "much detail", "mucho detalle", "detall", "lengthy")):
        return "too_verbose"
    if any(marker in text for marker in ("wrong agent", "wrong model", "agent equivocado", "wrong route", "incorrect route", "opencode", "codex", "claude")):
        return "wrong_agent"
    if any(marker in text for marker in ("repo", "workspace", "name", "resolv", "resolve", "workspace-os", "repo name")):
        return "missing_repo_resolution"
    if any(marker in text for marker in ("clarif", "ask", "question", "missing context", "falta contexto", "contexto")):
        return "missing_clarification"
    if any(marker in text for marker in ("prefer", "preference", "preferido", "ignore", "ignored")):
        return "ignored_preference"
    return "generic_fallback"

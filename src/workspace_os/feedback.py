from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedbackAssessment:
    status: str
    reason: str
    has_objection: bool
    has_praise: bool

    def render(self) -> str:
        flags = []
        if self.has_objection:
            flags.append("objection")
        if self.has_praise:
            flags.append("praise")
        flag_text = ", ".join(flags) if flags else "neutral"
        return f"status={self.status} flags={flag_text} reason={self.reason}"


def assess_feedback(request_text: str, result_text: str, feedback_text: str) -> FeedbackAssessment:
    del request_text, result_text
    text = feedback_text.casefold().strip()
    if not text:
        return FeedbackAssessment(
            status="positive",
            reason="No objections or praise were detected.",
            has_objection=False,
            has_praise=False,
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

    if has_objection:
        return FeedbackAssessment(
            status="questionable",
            reason="An objection or correction was detected in the feedback.",
            has_objection=True,
            has_praise=has_praise,
        )
    if has_praise:
        return FeedbackAssessment(
            status="over_expectation",
            reason="A congratulatory or positive reinforcement signal was detected.",
            has_objection=False,
            has_praise=True,
        )
    return FeedbackAssessment(
        status="positive",
        reason="No objections were detected and the feedback is treated as positive.",
        has_objection=False,
        has_praise=False,
    )

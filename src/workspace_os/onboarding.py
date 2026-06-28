from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from workspace_os.memory import WorkspaceMemoryStore


ONBOARDING_PREF_KEY = "onboarding_completed"


@dataclass(frozen=True)
class OnboardingQuestion:
    prompt: str
    expected_terms: tuple[str, ...]
    success: str
    failure: str


@dataclass(frozen=True)
class OnboardingResult:
    completed: bool
    skipped: bool
    correct_answers: int
    total_questions: int
    already_completed: bool = False

    @property
    def passed(self) -> bool:
        return self.completed and not self.skipped


def build_onboarding_steps() -> list[str]:
    return [
        "Welcome to Workspace OS.",
        "Workspace OS keeps work local-first, searchable, and reusable across ADEV, OCE, and WOS.",
        "Before writing new durable content, search for existing context and classify where it belongs.",
        "Capture stores sanitized evidence. Promotion proposes doctrine. Final deliverables can later live in Google Workspace.",
        "Mutating work stays behind approval, and remote work stays declarative and allowlisted.",
    ]


def build_onboarding_questions() -> list[OnboardingQuestion]:
    return [
        OnboardingQuestion(
            prompt="1) Before adding new durable content, what should you do first?",
            expected_terms=("search", "before", "write"),
            success="Correct. Search before write keeps the librarian workflow intact.",
            failure="Not quite. The workflow starts by searching for related work before writing.",
        ),
        OnboardingQuestion(
            prompt="2) What does capture do before durable storage?",
            expected_terms=("sanitize",),
            success="Correct. Capture sanitizes evidence before writing it.",
            failure="Not quite. Capture sanitizes first so private details do not leak into durable storage.",
        ),
        OnboardingQuestion(
            prompt="3) What requires explicit approval before mutation?",
            expected_terms=("approval",),
            success="Correct. Mutation stays behind explicit approval.",
            failure="Not quite. Mutable or risky actions require explicit approval.",
        ),
    ]


def render_onboarding_intro() -> list[str]:
    return [
        "Onboarding tutorial:",
        "- WOS coordinates repositories, memory, context, and agent routing.",
        "- Search before write.",
        "- Capture sanitizes evidence; promotion proposes reusable doctrine.",
        "- Google Workspace is for final deliverables, not raw evidence.",
        "- Approval gates stay in place for mutation and remote actions.",
        "",
        "Type 'skip' to mark onboarding complete and continue to the shell.",
        "Press Enter to start the quick tutorial.",
    ]


def run_onboarding_tutorial(
    memory_store: WorkspaceMemoryStore,
    input_func: Callable[[str], str] = input,
    output_func: Callable[..., None] = print,
    mark_complete: bool = True,
) -> OnboardingResult:
    completed = _is_completed(memory_store)
    if completed:
        return OnboardingResult(completed=True, skipped=True, correct_answers=0, total_questions=0, already_completed=True)

    for line in render_onboarding_intro():
        output_func(line)

    start_choice = input_func("Onboarding choice [Enter=continue, skip=skip tutorial]: ").strip().casefold()
    if start_choice in {"skip", "s", "skip tutorial"}:
        if mark_complete:
            memory_store.record_preference(ONBOARDING_PREF_KEY, "true")
        output_func("Onboarding skipped. You can run `workspace onboarding` later to review the tutorial.")
        return OnboardingResult(completed=True, skipped=True, correct_answers=0, total_questions=0)

    correct_answers = 0
    questions = build_onboarding_questions()
    for question in questions:
        answer = input_func(f"{question.prompt}\n> ").strip().casefold()
        if _answer_matches(answer, question.expected_terms):
            correct_answers += 1
            output_func(question.success)
        else:
            output_func(question.failure)

    passed = correct_answers == len(questions)
    if passed and mark_complete:
        memory_store.record_preference(ONBOARDING_PREF_KEY, "true")
    output_func(
        f"Onboarding summary: {correct_answers}/{len(questions)} correct."
        + (" Tutorial complete." if passed else " Review it again with `workspace onboarding`.")
    )
    return OnboardingResult(
        completed=passed,
        skipped=False,
        correct_answers=correct_answers,
        total_questions=len(questions),
    )


def _answer_matches(answer: str, expected_terms: Sequence[str]) -> bool:
    if not answer:
        return False
    return all(term.casefold() in answer for term in expected_terms)


def _is_completed(memory_store: WorkspaceMemoryStore) -> bool:
    value = memory_store.get_preference(ONBOARDING_PREF_KEY)
    return value is not None and value.strip().casefold() in {"true", "1", "yes", "completed", "done"}

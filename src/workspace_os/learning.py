from __future__ import annotations

import re
from dataclasses import dataclass

from workspace_os.agent_policy import normalize_agent_name
from workspace_os.feedback import assess_feedback
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.profile import OperatorProfile


_ERROR_RECOMMENDATIONS = {
    "too_verbose": ("compact", "keep answers compact and actionable"),
    "wrong_agent": ("cross_check", "re-evaluate agent routing before responding"),
    "missing_repo_resolution": ("resolve_repo", "resolve the requested repo before delegating"),
    "missing_clarification": ("clarify", "ask for the missing context before delegating"),
    "ignored_preference": ("respect_profile", "follow the configured operator preference"),
    "generic_fallback": ("tighten_routing", "replace generic fallback with a concrete route"),
}


@dataclass(frozen=True)
class WorkspaceLearningModel:
    total_feedback: int
    dominant_error_type: str | None
    dominant_error_count: int
    confidence: float
    recommended_focus: str
    recommended_next_action: str
    detail_level_hint: str
    primary_agent_bias: str | None

    def render_summary(self) -> str:
        dominant = self.dominant_error_type or "none"
        primary = self.primary_agent_bias or "n/a"
        return (
            f"error={dominant} "
            f"confidence={self.confidence:.2f} "
            f"focus={self.recommended_focus} "
            f"next={self.recommended_next_action} "
            f"detail={self.detail_level_hint} "
            f"primary={primary}"
        )


def build_workspace_learning_model(memory_store: WorkspaceMemoryStore, profile: OperatorProfile) -> WorkspaceLearningModel:
    metrics = memory_store.feedback_metrics()
    error_counts = {
        "too_verbose": metrics.get("too_verbose_count", 0),
        "wrong_agent": metrics.get("wrong_agent_count", 0),
        "missing_repo_resolution": metrics.get("missing_repo_resolution_count", 0),
        "missing_clarification": metrics.get("missing_clarification_count", 0),
        "ignored_preference": metrics.get("ignored_preference_count", 0),
        "generic_fallback": metrics.get("generic_fallback_count", 0),
    }
    dominant_error_type, dominant_error_count = _top_error_type(error_counts)
    primary_agent = normalize_agent_name(profile.primary_agent)

    if dominant_error_type is None:
        return WorkspaceLearningModel(
            total_feedback=metrics.get("total", 0),
            dominant_error_type=None,
            dominant_error_count=0,
            confidence=0.0,
            recommended_focus="maintain current routing",
            recommended_next_action="keep current flow",
            detail_level_hint=profile.detail_level,
            primary_agent_bias=primary_agent,
        )

    detail_level_hint, recommended_focus = _ERROR_RECOMMENDATIONS[dominant_error_type]
    recommended_next_action = {
        "compact": "reduce answer verbosity by default",
        "cross_check": "route ambiguous work through a second pass",
        "resolve_repo": "resolve the target repo before delegating",
        "clarify": "ask for missing context before delegating",
        "respect_profile": "honor the configured operator preference",
        "tighten_routing": "replace generic fallback with an explicit route",
    }[detail_level_hint]

    total_feedback = metrics.get("total", 0)
    confidence = (dominant_error_count / total_feedback) if total_feedback else 0.0
    return WorkspaceLearningModel(
        total_feedback=total_feedback,
        dominant_error_type=dominant_error_type,
        dominant_error_count=dominant_error_count,
        confidence=confidence,
        recommended_focus=recommended_focus,
        recommended_next_action=recommended_next_action,
        detail_level_hint=detail_level_hint,
        primary_agent_bias=primary_agent,
    )


def _top_error_type(error_counts: dict[str, int]) -> tuple[str | None, int]:
    if not error_counts:
        return None, 0
    ordered = sorted(error_counts.items(), key=lambda item: (-item[1], item[0]))
    top_error, top_count = ordered[0]
    if top_count <= 0:
        return None, 0
    return top_error, top_count


@dataclass(frozen=True)
class AgentPerformanceMetrics:
    agent: str
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    avg_duration_seconds: float
    success_rate: float
    task_types: dict[str, int]  # task type -> count

    def render_summary(self) -> str:
        return (
            f"{self.agent}: tasks={self.total_tasks} success_rate={self.success_rate:.2f} "
            f"avg_duration={self.avg_duration_seconds:.1f}s"
        )


def compute_agent_performance(memory_store: WorkspaceMemoryStore) -> list[AgentPerformanceMetrics]:
    """
    Compute performance metrics for each agent based on historical task execution.

    Returns:
        List of AgentPerformanceMetrics ordered by success rate (descending)
    """
    # Group agent launches by agent name
    launches = memory_store.recent_launches(limit=1000)
    agent_stats: dict[str, dict] = {}

    for launch in launches:
        agent = launch.get("agent", "unknown")
        if agent not in agent_stats:
            agent_stats[agent] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "durations": [],
                "task_types": {},
            }

        stats = agent_stats[agent]
        stats["total"] += 1

        # Infer success from task name or other heuristics
        # This is a simplified heuristic; real tracking would need explicit success/failure markers
        task = launch.get("task", "")
        if "healing" in task or "correction" in task:
            stats["failed"] += 1
        else:
            stats["successful"] += 1

        # Track task types
        task_type = _extract_task_type(task)
        stats["task_types"][task_type] = stats["task_types"].get(task_type, 0) + 1

    metrics = []
    for agent, stats in agent_stats.items():
        total = stats["total"]
        successful = stats["successful"]
        success_rate = successful / total if total > 0 else 0.0
        avg_duration = sum(stats["durations"]) / len(stats["durations"]) if stats["durations"] else 0.0

        metrics.append(
            AgentPerformanceMetrics(
                agent=agent,
                total_tasks=total,
                successful_tasks=successful,
                failed_tasks=stats["failed"],
                avg_duration_seconds=avg_duration,
                success_rate=success_rate,
                task_types=dict(stats["task_types"]),
            )
        )

    return sorted(metrics, key=lambda m: (-m.success_rate, -m.total_tasks))


def _extract_task_type(task_name: str) -> str:
    """Extract task type from task name."""
    if "cycle-work" in task_name:
        return "cycle_work"
    if "healing" in task_name:
        return "healing"
    if "checkpoint" in task_name:
        return "checkpoint"
    if "validation" in task_name:
        return "validation"
    return "general"


def _is_agent_mismatch_error(error_msg: str) -> bool:
    """
    Determine if an error indicates agent capability mismatch.

    Returns True only when there's evidence the agent lacks required capabilities,
    not for generic failures (network, timeout, bugs, test failures, etc.).

    Args:
        error_msg: Error message from failed task

    Returns:
        True if error suggests wrong agent selection, False otherwise
    """
    if not error_msg:
        return False

    error_lower = error_msg.lower()

    # Capability mismatch indicators
    capability_issues = [
        "command not found",
        "executable not found",
        "not installed",
        "missing dependency",
        "unsupported operation",
        "agent does not support",
        "capability not available",
        "tool not found",
        "unknown command",
    ]

    # Generic failures that aren't routing issues - these take precedence
    generic_failures = [
        "network error",
        "timeout",
        "timed out",
        "connection refused",
        "out of memory",
        "killed by signal",
        "syntax error",
        "assertion failed",
        "test failed",
        "assertion error",
        "traceback",  # Python stack traces indicate code bugs, not agent issues
        "compilation failed",
        "build failed",
        "lint error",
    ]

    has_capability_issue = any(indicator in error_lower for indicator in capability_issues)
    has_generic_failure = any(failure in error_lower for failure in generic_failures)

    # Only classify as agent capability error if we have capability indicators
    # and no generic failure markers
    return has_capability_issue and not has_generic_failure


def recommend_agent_for_task(task_type: str, memory_store: WorkspaceMemoryStore) -> str | None:
    """
    Recommend the best agent for a given task type based on historical performance.

    Args:
        task_type: Type of task (cycle_work, healing, validation, etc.)
        memory_store: Memory store with historical data

    Returns:
        Recommended agent name or None if no clear recommendation
    """
    metrics = compute_agent_performance(memory_store)

    # Filter to agents that have handled this task type
    relevant_agents = [m for m in metrics if task_type in m.task_types]

    if not relevant_agents:
        # Fallback to agent with highest overall success rate
        return metrics[0].agent if metrics else None

    # Return agent with highest success rate for this task type
    return max(relevant_agents, key=lambda m: m.success_rate).agent


def update_agent_performance_from_queue(
    memory_store: WorkspaceMemoryStore,
    queue_tracker: object,  # AgentQueueTracker - avoid circular import
) -> None:
    """
    Update agent performance metrics from queue tracker.
    Called at checkpoints to learn from recent work.

    Args:
        memory_store: Memory store to record feedback
        queue_tracker: AgentQueueTracker with recent task history
    """
    from workspace_os.agent_queue import AgentTaskState

    recent = queue_tracker.recent_tasks(limit=50)

    for task in recent:
        if task.state in (AgentTaskState.COMPLETED, AgentTaskState.FAILED):
            # Record feedback based on task outcome
            success = (task.state == AgentTaskState.COMPLETED and task.returncode == 0)

            if not success:
                # Record negative feedback for failed tasks
                error_tags = set()

                # Classify the failure type to avoid polluting learning model
                if not task.error:
                    # Silent failure: agent executed but produced no error output
                    # This indicates agent config/execution issue, NOT routing issue
                    error_type = "silent_failure"
                    feedback_msg = f"Agent {task.agent} silent failure (no output, returncode {task.returncode})"
                elif _is_agent_mismatch_error(task.error):
                    # Capability mismatch: clear evidence of wrong agent selection
                    error_tags.add("wrong_agent")
                    error_type = "capability_mismatch"
                    feedback_msg = f"Agent {task.agent} capability mismatch: {task.error[:100]}"
                else:
                    # Generic failure: network, bugs, tests, etc.
                    error_type = "execution_failure"
                    feedback_msg = f"Agent {task.agent} execution failure: {task.error[:100]}"

                try:
                    memory_store.record_feedback_event(
                        request_text=f"cycle work item {task.task_id}",
                        result_text=f"{task.agent} failed with returncode {task.returncode} (type: {error_type})",
                        feedback_text=feedback_msg,
                        status="questionable",
                        error_type="wrong_agent" if "wrong_agent" in error_tags else "generic_fallback",
                        reason="Agent execution failure",
                        has_objection=True,
                        has_praise=False
                    )
                except Exception:
                    # Gracefully handle feedback recording errors
                    pass


@dataclass(frozen=True)
class ProactiveQuestionSuggestion:
    question: str
    context: str
    previous_answer: str
    frequency: int
    relevance_score: float

    def render_summary(self) -> str:
        return f"Q: {self.question} (asked {self.frequency}x, relevance={self.relevance_score:.2f})"


@dataclass(frozen=True)
class QuestioningPrompt:
    task_context: str
    questions: tuple[str, ...]
    answer_hints: tuple[str, ...]
    learned_count: int
    recorded_count: int
    question_categories: tuple[str, ...] = ()

    def render_summary(self) -> str:
        return f"questions={len(self.questions)} learned={self.learned_count} recorded={self.recorded_count}"

    def render(self) -> str:
        lines = [
            "Questioning phase:",
            "- Ask up to 3 clarifying questions before executing work.",
            "- Categories: clarification, scope, edge cases, dependencies, constraints.",
            "- Use Squad Lead context and learned answers when the prompt already resolves the ambiguity.",
            "",
            f"Task context: {self.task_context}",
            "",
            "Clarifying questions:",
        ]
        if not self.questions:
            lines.append("- No clarifying questions needed.")
        else:
            for index, question in enumerate(self.questions, 1):
                category = self.question_categories[index - 1] if index - 1 < len(self.question_categories) else "clarification"
                lines.append(f"{index}. {question}")
                lines.append(f"   Category: {category}")
                if index - 1 < len(self.answer_hints) and self.answer_hints[index - 1]:
                    lines.append(f"   Squad Lead hint: {self.answer_hints[index - 1]}")
        return "\n".join(lines)


@dataclass(frozen=True)
class QuestioningProtocol:
    """Formulate pre-execution questions and attach learned answers."""

    memory_store: WorkspaceMemoryStore
    answer_engine: SquadLeadAnswerEngine

    def formulate(
        self,
        task_context: str,
        limit: int = 3,
        role: str = "primary",
        work_item_id: str | None = None,
        agent_name: str | None = None,
        issue_data: dict[str, object] | None = None,
        code_context: str = "",
        related_issues: list[dict[str, object]] | tuple[dict[str, object], ...] = (),
    ) -> QuestioningPrompt:
        suggestions = suggest_questions_for_work(self.memory_store, task_context, limit=limit)
        questions: list[str] = []
        answer_hints: list[str] = []
        categories: list[str] = []
        recorded_count = 0

        def add_question(question: str, answer_hint: str, category: str, learned: bool) -> None:
            nonlocal recorded_count
            normalized = question.lower().strip()
            if normalized in {existing.lower().strip() for existing in questions}:
                return
            questions.append(question)
            answer_hints.append(answer_hint)
            categories.append(category)
            if not learned and answer_hint:
                try:
                    self.memory_store.record_qa(
                        question,
                        answer_hint,
                        task_context,
                        work_item_id=work_item_id,
                        agent_name=agent_name or role,
                    )
                    recorded_count += 1
                except Exception:
                    pass

        for suggestion in suggestions[:limit]:
            add_question(
                suggestion.question,
                suggestion.previous_answer or "Use the learned answer from similar work.",
                _classify_question_category(suggestion.question),
                learned=True,
            )

        heuristics = _questioning_heuristics(task_context, role)
        for question, answer_hint in heuristics:
            if len(questions) >= limit:
                break
            answer_draft = self.answer_engine.answer_question(
                task_context,
                question,
                issue_data=issue_data,
                code_context=code_context,
                related_issues=related_issues,
                work_item_id=work_item_id,
                agent_name=agent_name or role,
            )
            composed_answer = answer_draft.answer
            if answer_draft.should_escalate:
                composed_answer = f"Escalate to human: {composed_answer}"
            if not composed_answer:
                composed_answer = answer_hint
            add_question(
                question,
                composed_answer,
                _classify_question_category(question),
                learned=True,
            )
            if not answer_draft.cache_hit:
                recorded_count += 1

        return QuestioningPrompt(
            task_context=task_context,
            questions=tuple(questions[:limit]),
            answer_hints=tuple(answer_hints[:limit]),
            learned_count=len(suggestions[:limit]),
            recorded_count=recorded_count,
            question_categories=tuple(categories[:limit]),
        )


@dataclass(frozen=True)
class AnswerDraft:
    question: str
    answer: str
    confidence: float
    source_summary: str
    cache_hit: bool
    should_escalate: bool

    def render_summary(self) -> str:
        cache = "cache" if self.cache_hit else "fresh"
        return f"confidence={self.confidence:.2f} source={self.source_summary} mode={cache}"


class SquadLeadAnswerEngine:
    """Resolve agent questions using issue context, code context, and learned Q&A."""

    def __init__(self, memory_store: WorkspaceMemoryStore):
        self.memory_store = memory_store

    def answer_question(
        self,
        task_context: str,
        question: str,
        *,
        issue_data: dict[str, object] | None = None,
        code_context: str = "",
        related_issues: list[dict[str, object]] | tuple[dict[str, object], ...] = (),
        work_item_id: str | None = None,
        agent_name: str | None = None,
    ) -> AnswerDraft:
        """Answer a Squad Lead question using cached Q&A and local context."""
        normalized_question = _normalize_question(question)
        cache_hit = self._find_cached_answer(task_context, normalized_question, work_item_id)
        if cache_hit is not None:
            return cache_hit

        answer_parts: list[str] = []
        evidence: list[str] = []
        issue_number = int(issue_data.get("number", 0)) if issue_data else 0
        issue_title = str(issue_data.get("title", "")) if issue_data else ""
        acceptance_criteria = _extract_acceptance_criteria(issue_data)
        code_hint = _summarize_code_context(code_context)

        if _contains_any_text(normalized_question, ("source of truth", "issue", "scope")):
            if issue_number:
                answer_parts.append(
                    f"Use issue #{issue_number}: {issue_title or 'the referenced issue'} as the authoritative scope."
                )
                evidence.append("issue")
            if acceptance_criteria:
                answer_parts.append(f"Acceptance criteria: {acceptance_criteria[0]}")
                evidence.append("acceptance_criteria")

        if _contains_any_text(normalized_question, ("validation", "test", "prove", "verify")):
            validation_hint = _extract_validation_hint(code_context, issue_data)
            if validation_hint:
                answer_parts.append(validation_hint)
                evidence.append("validation")
            elif acceptance_criteria:
                answer_parts.append(f"Validate against the recorded acceptance criteria: {acceptance_criteria[0]}")
                evidence.append("acceptance_criteria")

        if _contains_any_text(normalized_question, ("dependency", "integration", "constraint", "edge case")):
            if code_hint:
                answer_parts.append(code_hint)
                evidence.append("code_context")
            related_hint = _summarize_related_issues(related_issues)
            if related_hint:
                answer_parts.append(related_hint)
                evidence.append("related_issues")

        if not answer_parts:
            answer_parts.append("Use the issue description, acceptance criteria, and nearby code context to answer before changing behavior.")

        source_summary = ",".join(evidence) if evidence else "fallback"
        confidence = _score_answer_confidence(evidence, cache_hit=False, question=normalized_question, task_context=task_context)
        answer = " ".join(answer_parts).strip()
        draft = AnswerDraft(
            question=question.strip(),
            answer=answer,
            confidence=confidence,
            source_summary=source_summary,
            cache_hit=False,
            should_escalate=confidence < 0.6,
        )
        self._record_answer(task_context, draft, work_item_id=work_item_id, agent_name=agent_name)
        return draft

    def _find_cached_answer(
        self,
        task_context: str,
        normalized_question: str,
        work_item_id: str | None,
    ) -> AnswerDraft | None:
        if work_item_id:
            for item in self.memory_store.get_qa_for_work_item(work_item_id):
                if _normalize_question(item["question"]) == normalized_question:
                    return AnswerDraft(
                        question=item["question"],
                        answer=item["answer"],
                        confidence=0.96,
                        source_summary="work_item_cache",
                        cache_hit=True,
                        should_escalate=False,
                    )

        for item in self.memory_store.get_similar_questions(task_context, limit=20):
            if _normalize_question(item["question"]) == normalized_question:
                return AnswerDraft(
                    question=item["question"],
                    answer=item["answer"],
                    confidence=0.9,
                    source_summary="task_context_cache",
                    cache_hit=True,
                    should_escalate=False,
                )
        return None

    def _record_answer(
        self,
        task_context: str,
        draft: AnswerDraft,
        *,
        work_item_id: str | None,
        agent_name: str | None,
    ) -> None:
        try:
            self.memory_store.record_qa(
                draft.question,
                draft.answer,
                task_context,
                work_item_id=work_item_id,
                agent_name=agent_name,
            )
        except Exception:
            pass


def build_squad_lead_answer_engine(memory_store: WorkspaceMemoryStore) -> SquadLeadAnswerEngine:
    """Create the Squad Lead answer engine for a given memory store."""
    return SquadLeadAnswerEngine(memory_store)


def suggest_questions_for_work(
    memory_store: WorkspaceMemoryStore,
    task_context: str,
    limit: int = 3,
) -> list[ProactiveQuestionSuggestion]:
    """
    Suggest proactive questions based on historical Q&A from similar work.

    Finds similar past work items, identifies commonly asked questions,
    and surfaces them to agents before they ask.

    Args:
        memory_store: Memory store with historical Q&A data
        task_context: Description of the current work
        limit: Maximum number of suggestions to return

    Returns:
        List of proactive question suggestions ordered by relevance
    """
    similar_qa = memory_store.get_similar_questions(task_context, limit=20)

    if not similar_qa:
        return []

    # Group by question and count frequency
    question_groups: dict[str, list[dict[str, str]]] = {}
    for qa in similar_qa:
        q_normalized = qa["question"].lower().strip()
        if q_normalized not in question_groups:
            question_groups[q_normalized] = []
        question_groups[q_normalized].append(qa)

    # Score and rank questions
    suggestions = []
    for question_norm, qa_list in question_groups.items():
        frequency = len(qa_list)
        original_question = qa_list[0]["question"]
        most_recent_answer = qa_list[0]["answer"]
        most_recent_context = qa_list[0]["context"]

        relevance_score = float(frequency)

        suggestions.append(
            ProactiveQuestionSuggestion(
                question=original_question,
                context=most_recent_context,
                previous_answer=most_recent_answer,
                frequency=frequency,
                relevance_score=relevance_score,
            )
        )

    # Sort by relevance score descending
    suggestions.sort(key=lambda s: (-s.relevance_score, -s.frequency))

    return suggestions[:limit]


def format_proactive_questions(suggestions: list[ProactiveQuestionSuggestion]) -> str:
    """
    Format proactive question suggestions for agent prompt.

    Args:
        suggestions: List of question suggestions

    Returns:
        Formatted string for inclusion in agent prompt
    """
    if not suggestions:
        return ""

    lines = ["Proactive Questions (from similar work):"]
    for i, suggestion in enumerate(suggestions, 1):
        lines.append(f"{i}. {suggestion.question}")
        if suggestion.frequency > 1:
            lines.append(f"   (Asked {suggestion.frequency}x in similar tasks)")

    return "\n".join(lines)


def build_questioning_prompt(
    memory_store: WorkspaceMemoryStore,
    task_context: str,
    limit: int = 3,
    role: str = "primary",
    work_item_id: str | None = None,
    agent_name: str | None = None,
    issue_data: dict[str, object] | None = None,
    code_context: str = "",
    related_issues: list[dict[str, object]] | tuple[dict[str, object], ...] = (),
) -> QuestioningPrompt:
    """Build the questioning phase prompt and seed it with learned answers."""
    protocol = QuestioningProtocol(
        memory_store=memory_store,
        answer_engine=build_squad_lead_answer_engine(memory_store),
    )
    return protocol.formulate(
        task_context,
        limit=limit,
        role=role,
        work_item_id=work_item_id,
        agent_name=agent_name,
        issue_data=issue_data,
        code_context=code_context,
        related_issues=related_issues,
    )


def _questioning_heuristics(task_context: str, role: str) -> list[tuple[str, str]]:
    context = task_context.lower()
    role_label = {
        "primary": "primary executor",
        "cross-check": "cross-check reviewer",
        "observer": "learning observer",
    }.get(role, "executor")

    heuristics = [
        (
            "What is the single source of truth for this task, and which repo or issue should I treat as authoritative?",
            "Use the assigned issue, objective, and current workspace context as the source of truth.",
        ),
        (
            "What acceptance criteria or validation must pass before this work is done?",
            "Use the narrowest meaningful validation surface and confirm the requested outcome before merging.",
        ),
        (
            "What dependencies, edge cases, or external constraints could block this implementation?",
            f"Check connected services, repo state, and {role_label} concerns before executing.",
        ),
    ]

    if "issue" in context or "#" in context:
        heuristics[0] = (
            "Which issue number and acceptance criteria should I optimize for first?",
            "Treat the referenced issue and its acceptance criteria as the authoritative scope.",
        )
    if "validation" in context or "test" in context:
        heuristics[1] = (
            "Which validation command or test module is required to prove this change?",
            "Run the narrowest meaningful test or validation command for the touched surface.",
        )
    if "dependency" in context or "connector" in context or "integration" in context:
        heuristics[2] = (
            "Which dependencies or integrations must be confirmed before implementation?",
            "Verify the current connectors, repo state, and integration prerequisites before changing behavior.",
        )

    return heuristics[:3]


def _classify_question_category(question: str) -> str:
    normalized = question.lower()
    if "validation" in normalized or "verify" in normalized or "test" in normalized:
        return "constraints"
    if "dependency" in normalized or "integration" in normalized:
        return "dependencies"
    if "edge" in normalized or "case" in normalized:
        return "edge_cases"
    if "source of truth" in normalized or "issue" in normalized or "scope" in normalized:
        return "scope"
    return "clarification"


def _normalize_question(question: str) -> str:
    return " ".join(question.lower().strip().split())


def _extract_acceptance_criteria(issue_data: dict[str, object] | None) -> list[str]:
    if not issue_data:
        return []
    body = str(issue_data.get("body", "") or "")
    lines = body.splitlines()
    criteria: list[str] = []
    capture = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if capture and criteria:
                break
            continue
        if stripped.casefold().startswith("## acceptance"):
            capture = True
            continue
        if capture and stripped.startswith("## "):
            break
        if capture and stripped[:2] in {"- ", "* "}:
            criteria.append(stripped[2:].strip())
    return criteria


def _extract_validation_hint(code_context: str, issue_data: dict[str, object] | None) -> str:
    snippets: list[str] = []
    if issue_data:
        criteria = _extract_acceptance_criteria(issue_data)
        if criteria:
            snippets.append(f"Validate the acceptance criteria: {criteria[0]}")
    if code_context:
        tests = re.findall(r"tests?/[A-Za-z0-9_./-]*test_[A-Za-z0-9_./-]*\\.py", code_context, flags=re.IGNORECASE)
        if tests:
            snippets.append(f"Start with the narrowest test surface: {tests[0]}")
    if not snippets and code_context:
        snippets.append(f"Use the code context to identify the narrowest meaningful validation path: {_summarize_code_context(code_context)}")
    return " ".join(snippets).strip()


def _summarize_code_context(code_context: str) -> str:
    text = " ".join(code_context.strip().split())
    if not text:
        return ""
    return text[:200]


def _summarize_related_issues(related_issues: list[dict[str, object]] | tuple[dict[str, object], ...]) -> str:
    if not related_issues:
        return ""
    fragments: list[str] = []
    for item in related_issues[:3]:
        number = item.get("number")
        title = str(item.get("title", "")).strip()
        if number and title:
            fragments.append(f"#{number} {title}")
        elif number:
            fragments.append(f"#{number}")
        elif title:
            fragments.append(title)
    if not fragments:
        return ""
    return f"Check related issues for precedent: {', '.join(fragments)}"


def _score_answer_confidence(
    evidence: list[str],
    *,
    cache_hit: bool,
    question: str,
    task_context: str,
) -> float:
    score = 0.25 + (0.2 * len(evidence))
    if cache_hit:
        score += 0.35
    if _contains_any_text(question, ("source of truth", "issue", "validation", "test", "dependency", "integration")):
        score += 0.1
    if task_context.strip():
        score += 0.05
    return max(0.0, min(score, 0.98))


def _contains_any_text(value: str, patterns: tuple[str, ...]) -> bool:
    normalized = value.lower()
    return any(pattern in normalized for pattern in patterns)

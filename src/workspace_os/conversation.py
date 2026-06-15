from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from workspace_os.conscience import ConscienceDecision, evaluate_request
from workspace_os.batch import current_batch_report, current_process_report
from workspace_os.config import Source
from workspace_os.git_status import inspect_source
from workspace_os.memory import MemoryHit, WorkspaceMemoryStore
from workspace_os.profile import load_profile
from workspace_os.sanitization import sanitize_text
from workspace_os.search import SearchMatch, search_sources


@dataclass(frozen=True)
class WorkspaceReply:
    reply: str
    conscience: ConscienceDecision
    learning: dict[str, object]
    source_matches: list[SearchMatch]
    memory_hits: list[MemoryHit]
    suggested_actions: list[dict[str, str]]


def build_workspace_reply(
    sources: list[Source],
    message: str,
    memory_store: WorkspaceMemoryStore | None = None,
    session_id: str = "default",
    tone: str = "neutral",
    detail_level: str = "standard",
) -> WorkspaceReply:
    clean_message = message.strip()
    conscience = evaluate_request(clean_message, destination="software")
    source_limit = _detail_limit(detail_level)
    memory_limit = _detail_limit(detail_level)
    source_matches = search_sources(sources, clean_message, max_results=source_limit)
    memory_hits = memory_store.search(clean_message, limit=memory_limit) if memory_store else []
    learning = _learning_signal(clean_message, memory_hits)

    if memory_store:
        request_hash = _hash_text(clean_message)
        memory_store.record_turn(session_id=session_id, role="user", message=clean_message)

    answer_lines = _answer_lines(clean_message, sources, memory_store)
    suggested_actions = _suggested_actions(clean_message, conscience, memory_store)
    if suggested_actions:
        answer_lines.extend(_redirect_guidance_lines(suggested_actions))
    trace_lines = [
        f"Style: {tone} / {detail_level}",
        f"Conscience: {conscience.decision} ({conscience.risk_level})",
        f"Strategy: {conscience.response_strategy}",
        f"Rationale: {conscience.rationale}",
        f"Policy refs: {', '.join(conscience.policy_refs) if conscience.policy_refs else 'n/a'}",
        f"Learning engine: {'activated' if learning['activated'] else 'standby'}",
        learning["summary"],
    ]

    if memory_store:
        process = current_process_report(memory_store)
        batch = current_batch_report(memory_store)
        context = memory_store.latest_context_snapshot()
        if context is not None:
            trace_lines.extend(
                [
                    "",
                    "Global context:",
                    f"- {context['reason']} @ {context['created_at']}",
                    f"- {context['summary']}",
                ]
            )
        if process is not None:
            trace_lines.extend(
                [
                    "",
                    "Active process:",
                    f"- {process.label}: objective={process.objective} checkpoints={process.checkpoint_count} delegations={process.delegations} defects={process.defect_iterations}",
                ]
            )
        if batch is not None:
            trace_lines.extend(
                [
                    "",
                    "Active batch:",
                    f"- {batch.label}: duration={batch.duration_seconds}s delegations={batch.delegations} defects={batch.defect_iterations}",
                ]
            )
        if conscience.context:
            trace_lines.extend(
                [
                    "",
                    "Moral context:",
                    f"- intent={conscience.context.get('user_intent', 'n/a')} domain={conscience.context.get('domain', 'n/a')} reversible={conscience.context.get('reversibility', 'n/a')}",
                    f"- salience={conscience.context.get('moral_salience', 'n/a')} confidence={conscience.context.get('confidence', 'n/a')}",
                ]
            )
        if suggested_actions and suggested_actions[0].get("reason"):
            trace_lines.extend(["", f"History bias: {suggested_actions[0]['reason']}"])

    if memory_hits:
        trace_lines.extend(["", "Memory signals:"])
        trace_lines.extend([hit.render() for hit in memory_hits[:3]])

    if source_matches:
        trace_lines.extend(["", "Related knowledge:"])
        trace_lines.extend(
            [
                f"- {match.source_name}:{match.path}:{match.line_number}: {sanitize_text(match.line)}"
                for match in source_matches[:3]
            ]
        )

    reply = sanitize_text("\n".join(["Answer:", *answer_lines, "", "Trace:", *trace_lines]))

    if memory_store:
        memory_store.record_decision(
            request_hash=request_hash,
            risk_level=conscience.risk_level,
            decision=conscience.decision,
            missing_context=conscience.missing_context,
            primary_agent=conscience.primary_agent,
            secondary_agent=conscience.secondary_agent,
            routing_reason=conscience.routing_reason,
        )
        memory_store.record_turn(session_id=session_id, role="assistant", message=reply)

    return WorkspaceReply(
        reply=reply,
        conscience=conscience,
        learning=learning,
        source_matches=source_matches,
        memory_hits=memory_hits,
        suggested_actions=suggested_actions,
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


def _detail_limit(detail_level: str) -> int:
    if detail_level == "minimal":
        return 2
    if detail_level == "comprehensive":
        return 8
    return 5


def _is_workspace_status_query(message: str) -> bool:
    text = message.casefold()
    keywords = (
        "que proyectos",
        "proyectos en curso",
        "proyectos",
        "projects in flight",
        "current projects",
        "working on",
        "work in progress",
        "wip",
        "en curso",
        "estado",
        "status",
        "qué proyectos",
    )
    return any(keyword in text for keyword in keywords)


def _is_greeting(message: str) -> bool:
    text = message.casefold().strip(" ?!.,")
    greetings = {"hola", "hello", "hi", "hey", "buenas", "buenos dias", "buenas tardes"}
    return text in greetings


def _is_app_overview_query(message: str) -> bool:
    text = message.casefold()
    keywords = (
        "que hace esta aplicacion",
        "qué hace esta aplicación",
        "what does this app do",
        "what does this application do",
        "que hace wos",
        "what is wos",
        "para que sirve",
        "what is this for",
    )
    return any(keyword in text for keyword in keywords)


def _is_repetition_query(message: str) -> bool:
    text = message.casefold()
    keywords = (
        "respondes siempre lo mismo",
        "always the same",
        "same thing",
        "no me ayudas",
        "not helpful",
        "sin ayuda",
        "repetitivo",
        "repetitive",
    )
    return any(keyword in text for keyword in keywords)


def _workspace_status_lines(memory_store: WorkspaceMemoryStore) -> list[str]:
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    launches = memory_store.recent_launches(limit=3)
    profile = load_profile(memory_store)
    workspace_name = profile.default_workspace or "all workspaces"
    codex_prompt = (
        f"Inspect the current workspace state for {workspace_name}, list the projects in flight, "
        "active branches, current process or batch windows, blockers, and the next best action."
    )

    lines = ["Projects in flight:"]
    lines.append(f"- workspace={workspace_name}")
    if process is None:
        lines.append("- process=none")
    else:
        lines.append(
            f"- process={process.label}: objective={process.objective} batches={process.batch_count} "
            f"checkpoints={process.checkpoint_count} delegations={process.delegations} defects={process.defect_iterations}"
        )
    if batch is None:
        lines.append("- batch=none")
    else:
        lines.append(
            f"- batch={batch.label}: objective={batch.objective} duration={batch.duration_seconds}s "
            f"delegations={batch.delegations} defects={batch.defect_iterations}"
        )
    if launches:
        lines.append("- recent launches:")
        for launch in launches:
            workspace = launch["workspace"] or "all"
            lines.append(f"  - {launch['agent']} {workspace}: {launch['task']}")
    else:
        lines.append("- recent launches=none")
    if process is None and batch is None:
        lines.extend(
            [
                "- primary route=/codex \"Inspect the current workspace state and summarize projects in flight, active branches, blockers, and the next best action.\"",
                "- fallback route=/claude \"Cross-check the same workspace inventory and add anything Codex missed; parallelize if faster.\"",
                f"- codex prompt={_agent_route_prompt('codex', profile.default_workspace or 'all workspaces')}",
            ]
        )
    else:
        lines.append(f"- next step={_next_step(process, batch)}")
    return lines


def _suggested_actions(message: str, conscience: ConscienceDecision, memory_store: WorkspaceMemoryStore | None) -> list[dict[str, str]]:
    if conscience.decision != "SAFE_REDIRECT" and not _is_workspace_status_query(message):
        return []
    profile = load_profile(memory_store) if memory_store else None
    workspace_name = "all workspaces"
    if profile and profile.default_workspace:
        workspace_name = profile.default_workspace
    primary_agent = conscience.primary_agent or "codex"
    secondary_agent = conscience.secondary_agent or ("claude" if primary_agent == "codex" else "codex")
    primary_agent, secondary_agent, route_reason = _refine_route_with_history(
        primary_agent,
        secondary_agent,
        conscience,
        memory_store,
    )
    primary_task = _agent_route_prompt(primary_agent, workspace_name)
    secondary_task = _agent_route_prompt(secondary_agent, workspace_name)
    return [
        {
            "agent": primary_agent,
            "task": primary_task,
            "brief": f"User request: {message}",
            "command": f'/{primary_agent} "{primary_task}"',
            "reason": route_reason,
        },
        {
            "agent": secondary_agent,
            "task": secondary_task,
            "brief": f"User request: {message}",
            "command": f'/{secondary_agent} "{secondary_task}"',
            "reason": route_reason,
        },
    ]


def _redirect_guidance_lines(actions: list[dict[str, str]]) -> list[str]:
    lines = [f"Suggested route: /{actions[0]['agent']}"]
    if actions:
        lines.append(f"Suggested command: {actions[0]['command']}")
    if len(actions) > 1:
        lines.extend([f"Fallback route: /{actions[1]['agent']}", f"Suggested command: {actions[1]['command']}"])
    return lines


def _answer_lines(message: str, sources: list[Source], memory_store: WorkspaceMemoryStore | None) -> list[str]:
    if _is_greeting(message):
        return [
            "Hola. Soy WOS: orquesto trabajo sobre tus repos, recuerdo contexto y delego a Codex o Claude cuando hace falta.",
            "Dame un repo, un objetivo o una pregunta y te devuelvo el siguiente paso concreto.",
        ]
    if _is_app_overview_query(message):
        return [
            "Workspace OS is your local workspace control plane.",
            "- tracks repos and git state",
            "- remembers context, decisions, handoffs, and preferences",
            "- routes ambiguous work to Codex first, Claude as backup",
            "- delegates execution and cross-checks to those agents when work needs throughput",
            "- compacts global context after each work window",
            "Try: /inspect, /context latest, /codex <task>, /claude <task>",
        ]
    if _is_repetition_query(message):
        return [
            "No. I now answer by intent instead of repeating the same fallback.",
            "If a question is ambiguous, I route it to Codex first and use Claude in parallel when a second pass is useful.",
            "Ask for repo state, an objective, or a task and I'll return the next action instead of a canned reply.",
        ]
    if memory_store and _is_workspace_status_query(message):
        return _workspace_status_answer_lines(sources, memory_store)
    return [
        "Give me a repo, goal, or question and I'll turn it into a task plan, route work to Codex, or cross-check with Claude.",
        "Try: 'what projects are in flight?', 'what does this app do?', '/inspect', '/codex <task>', or '/claude <task>'.",
    ]


def _workspace_status_answer_lines(sources: list[Source], memory_store: WorkspaceMemoryStore) -> list[str]:
    profile = load_profile(memory_store)
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    launches = memory_store.recent_launches(limit=3)
    route_hint = _history_route_hint(memory_store)
    lines: list[str] = []
    lines.append("Tracked projects:")
    for source in sources:
        status = inspect_source(source)
        branch = status.branch or "n/a"
        if status.state == "missing":
            detail = f"missing path={source.path}"
        elif status.state == "not-git":
            detail = f"not-git path={source.path}"
        elif status.state == "error":
            detail = f"error={status.error}"
        else:
            detail = f"branch={branch} changes={status.dirty_count} untracked={status.untracked_count}"
            if status.ahead or status.behind:
                detail += f" ahead={status.ahead} behind={status.behind}"
        lines.append(f"- {source.name}: {detail}")

    if process is None and batch is None:
        workspace_name = profile.default_workspace if profile and profile.default_workspace else "all workspaces"
        lines.extend(
            [
                "No active process or batch window is tracked.",
                "Primary route=/codex",
                "Use Codex to inventory the workspace and summarize active work.",
                f"Suggested command: /codex \"{_agent_route_prompt('codex', workspace_name)}\"",
                "Fallback route=/claude",
                "Use Claude in parallel to cross-check the inventory and fill gaps.",
                f"Suggested command: /claude \"{_agent_route_prompt('claude', workspace_name)}\"",
            ]
        )
        if route_hint:
            lines.append(f"History bias: {route_hint}")
    else:
        lines.append(f"Next step: {_next_step(process, batch)}")

    if launches:
        lines.append("Recent launches:")
        for launch in launches:
            workspace = launch["workspace"] or "all"
            lines.append(f"- {launch['agent']} {workspace}: {launch['task']}")
    return lines


def _agent_route_prompt(agent: str, workspace_name: str) -> str:
    if agent == "claude":
        return (
            f"Cross-check the workspace inventory for {workspace_name}; confirm any active work, "
            "identify gaps, and suggest the fastest next step."
        )
    return (
        f"Inspect the current workspace state for {workspace_name}, list the projects in flight, "
        "active branches, blockers, and the next best action."
    )


def _refine_route_with_history(
    primary_agent: str,
    secondary_agent: str,
    conscience: ConscienceDecision,
    memory_store: WorkspaceMemoryStore | None,
) -> tuple[str, str, str]:
    route_hint = _history_route_hint(memory_store)
    if route_hint == "route_to_claude_for_cross_check" and primary_agent != "claude":
        return "claude", "codex", "history_prefers_claude_cross_check"
    if route_hint == "route_to_codex_for_inventory" and primary_agent != "codex":
        return "codex", "claude", "history_prefers_codex_inventory"
    if route_hint == "keep_codex_as_primary_for_workspace_execution" and primary_agent != "codex":
        return "codex", "claude", "history_prefers_codex_execution"
    if route_hint == "keep_claude_as_primary_for_sensitive_reviews" and primary_agent != "claude":
        return "claude", "codex", "history_prefers_claude_review"
    if conscience.routing_reason == "authority_required":
        return primary_agent, secondary_agent, "authority_clarification"
    return primary_agent, secondary_agent, route_hint or conscience.routing_reason or "immediate_context"


def _history_route_hint(memory_store: WorkspaceMemoryStore | None) -> str | None:
    if memory_store is None:
        return None
    summary = memory_store.decision_metrics_summary(limit=20)
    if summary.get("total", 0) <= 0:
        return None
    return str(summary.get("recommended_next_action") or "") or None


def _next_step(process, batch) -> str:
    if process is not None:
        if process.checkpoint_count == 0:
            return "record the first process checkpoint"
        if batch is None:
            return "start a batch inside the active process"
        return "continue with the next batch checkpoint or close the process when complete"
    if batch is not None:
        return "start or close the process window around the active batch work"
    return "start a new process window before the next batch"

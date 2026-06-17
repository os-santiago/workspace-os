from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
import re

from workspace_os.agent_policy import normalize_agent_name
from workspace_os.conscience import ConscienceDecision, evaluate_request
from workspace_os.batch import current_batch_report, current_process_report
from workspace_os.config import Source
from workspace_os.delegation import build_agent_route_command, build_agent_route_prompt
from workspace_os.feedback import assess_feedback
from workspace_os.git_status import inspect_source
from workspace_os.memory import MemoryHit, WorkspaceMemoryStore
from workspace_os.overview import build_workspace_analysis
from workspace_os.profile import load_profile
from workspace_os.sanitization import sanitize_text
from workspace_os.search import SearchMatch, search_sources


@dataclass(frozen=True)
class WorkspaceReply:
    answer: str
    trace: str
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
    prior_turns = memory_store.recent_conversation_turns(limit=6, session_id=session_id) if memory_store else []

    if memory_store:
        request_hash = _hash_text(clean_message)
        memory_store.record_turn(session_id=session_id, role="user", message=clean_message)

    target_source = _resolve_target_source(clean_message, sources)
    answer_lines = _answer_lines(
        clean_message,
        sources,
        memory_store,
        target_source=target_source,
        profile=load_profile(memory_store) if memory_store else None,
    )
    suggested_actions = _suggested_actions(clean_message, conscience, memory_store, sources=sources, target_source=target_source)
    if suggested_actions:
        answer_lines.extend(_redirect_guidance_lines(suggested_actions))
    trace_lines = [
        f"Style: {tone} / {detail_level}",
        f"OCE: {conscience.decision} ({conscience.risk_level})",
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

    feedback_event = _record_feedback_event(memory_store, session_id, clean_message, prior_turns) if memory_store else None
    if feedback_event is not None:
        trace_lines.extend(
            [
                "",
                "Feedback layer:",
                f"- status={feedback_event['status']} objection={feedback_event['has_objection']} praise={feedback_event['has_praise']}",
                f"- error_type={feedback_event['error_type']}",
                f"- reason={feedback_event['reason']}",
            ]
        )

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

    answer = sanitize_text("\n".join(answer_lines))
    trace = sanitize_text("\n".join(trace_lines))
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
        answer=answer,
        trace=trace,
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


def _record_feedback_event(
    memory_store: WorkspaceMemoryStore,
    session_id: str,
    feedback_text: str,
    prior_turns: list[dict[str, str]],
) -> dict[str, object] | None:
    if not _is_feedback_message(feedback_text):
        return None
    request_turn = next((turn for turn in prior_turns if turn["role"] == "user"), None)
    result_turn = next((turn for turn in prior_turns if turn["role"] == "assistant"), None)
    if request_turn is None or result_turn is None:
        return None
    assessment = assess_feedback(request_turn["message"], result_turn["message"], feedback_text)
    memory_store.record_feedback_event(
        request_text=request_turn["message"],
        result_text=result_turn["message"],
        feedback_text=feedback_text,
        status=assessment.status,
        reason=assessment.reason,
        error_type=assessment.error_type,
        has_objection=assessment.has_objection,
        has_praise=assessment.has_praise,
    )
    return {
        "status": assessment.status,
        "reason": assessment.reason,
        "error_type": assessment.error_type,
        "has_objection": assessment.has_objection,
        "has_praise": assessment.has_praise,
        "session_id": session_id,
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


def _is_continuation_request(message: str) -> bool:
    text = message.casefold()
    keywords = (
        "quiero continuar",
        "continuar con la implementacion",
        "continuar con la implementación",
        "continue with the implementation",
        "continue implementation",
        "resume",
        "retomar",
        "siguiente lote",
        "next batch",
        "keep going",
    )
    return any(keyword in text for keyword in keywords)


def _is_feedback_message(message: str) -> bool:
    text = message.casefold()
    keywords = (
        "gracias",
        "thank you",
        "thanks",
        "good",
        "great",
        "excellent",
        "well done",
        "bien",
        "perfect",
        "excellent work",
        "no sirve",
        "not useful",
        "not helpful",
        "objection",
        "object",
        "problem",
        "issue",
        "wrong",
        "incorrect",
        "mejorar",
        "fix",
        "fail",
    )
    return any(keyword in text for keyword in keywords)


def _workspace_status_lines(memory_store: WorkspaceMemoryStore, target_source: Source | None = None) -> list[str]:
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    launches = memory_store.recent_launches(limit=3)
    profile = load_profile(memory_store)
    workspace_name = profile.default_workspace or "all workspaces"
    workspace_root = _workspace_root_from_sources([])

    lines = ["Projects in flight:"]
    if target_source is not None:
        status = inspect_source(target_source)
        branch = status.branch or "n/a"
        lines.extend(
            [
                f"- requested repo={target_source.name}",
                f"- target path={target_source.path}",
                f"- target state={status.state} branch={branch} changes={status.dirty_count} untracked={status.untracked_count}",
            ]
        )
    if workspace_root != "all workspaces":
        lines.append(f"- root={workspace_root}")
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
        primary_agent = normalize_agent_name(profile.primary_agent) or "opencode"
        lines.extend(
            [
                f"- primary route={build_agent_route_command(primary_agent, profile.default_workspace or 'all workspaces')}",
                f"- fallback route={build_agent_route_command('claude', profile.default_workspace or 'all workspaces')}",
                f"- {primary_agent} prompt={build_agent_route_prompt(primary_agent, profile.default_workspace or 'all workspaces')}",
            ]
        )
    else:
        lines.append(f"- next step={_next_step(process, batch)}")
    return lines


def _suggested_actions(
    message: str,
    conscience: ConscienceDecision,
    memory_store: WorkspaceMemoryStore | None,
    sources: list[Source] | None = None,
    target_source: Source | None = None,
) -> list[dict[str, str]]:
    if _is_greeting(message) or _is_app_overview_query(message) or _is_repetition_query(message):
        return []
    repo_request = target_source is not None and _is_repository_request(message)
    if conscience.decision != "SAFE_REDIRECT" and not (_is_workspace_status_query(message) or _is_continuation_request(message) or repo_request):
        return []
    profile = load_profile(memory_store) if memory_store else None
    workspace_name = "all workspaces"
    if profile and profile.default_workspace:
        workspace_name = profile.default_workspace
    if target_source is not None:
        workspace_name = target_source.name
    primary_agent = conscience.primary_agent or (profile.primary_agent if profile else None) or "opencode"
    secondary_agent = conscience.secondary_agent or ("claude" if primary_agent != "claude" else "opencode")
    if target_source is not None:
        primary_agent, secondary_agent, target_reason = _preferred_agents_for_source(target_source, primary_agent)
        primary_agent, secondary_agent, route_reason = _refine_route_with_history(
            primary_agent,
            secondary_agent,
            conscience,
            memory_store,
        )
        if route_reason == "immediate_context" and target_reason:
            route_reason = target_reason
    else:
        primary_agent, secondary_agent, route_reason = _refine_route_with_history(
            primary_agent,
            secondary_agent,
            conscience,
            memory_store,
        )
    primary_task = build_agent_route_prompt(primary_agent, workspace_name)
    secondary_task = build_agent_route_prompt(secondary_agent, workspace_name)
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
    lines = [f"Primary route: /{actions[0]['agent']}"]
    if actions:
        lines.append(f"Command: {actions[0]['command']}")
    if len(actions) > 1 and actions[1]["agent"] != actions[0]["agent"]:
        lines.extend([f"Optional cross-check: /{actions[1]['agent']}", f"Command: {actions[1]['command']}"])
    return lines


def _answer_lines(
    message: str,
    sources: list[Source],
    memory_store: WorkspaceMemoryStore | None,
    target_source: Source | None = None,
    profile=None,
) -> list[str]:
    if _is_greeting(message):
        return [
            "Hola. Soy WOS: orquesto trabajo sobre tus repos, recuerdo contexto y delego al agente primario configurado o a Claude cuando hace falta.",
            "Dame un repo, un objetivo o una pregunta y te devuelvo el siguiente paso concreto.",
        ]
    if target_source is not None and _is_repository_request(message):
        return _repository_request_lines(message, target_source, profile)
    if _is_app_overview_query(message):
        return [
            "Workspace OS is your local workspace control plane.",
            "- tracks repos and git state",
            "- remembers context, decisions, handoffs, and preferences",
            "- routes ambiguous work through OCE, then the configured primary agent and Claude as backup",
            "- delegates execution and cross-checks to those agents when work needs throughput",
            "- compacts global context after each work window",
            "Try: /inspect, /context latest, /oce, /opencode <task>, /codex <task>, /claude <task>",
        ]
    if _is_repetition_query(message):
        primary_agent = normalize_agent_name(profile.primary_agent) or "opencode"
        primary_agent_label = primary_agent.capitalize()
        return [
            "No. I now answer by intent instead of repeating the same fallback.",
            f"If a question is ambiguous, I route it to {primary_agent_label} first and use Claude in parallel when a second pass is useful.",
            "Ask for repo state, an objective, or a task and I'll return the next action instead of a canned reply.",
        ]
    if _is_continuation_request(message):
        workspace_name = _workspace_name_from_sources(sources)
        primary_agent = normalize_agent_name(profile.primary_agent) or "opencode"
        return [
            f"Ready. Continue with {workspace_name}.",
            "Fastest path: /inspect, then /next.",
            f"Primary route: /{primary_agent}",
            f"Command: {_route_command(primary_agent, workspace_name)}",
            "Optional cross-check: /claude",
            f"Command: {_route_command('claude', workspace_name)}",
        ]
    if _is_feedback_message(message):
        assessment = assess_feedback("", "", message)
        signal = assessment.status.replace("_", " ")
        return [
            "Feedback received.",
            f"Signal: {signal}",
            assessment.reason,
        ]
    if memory_store and _is_workspace_status_query(message):
        return _workspace_status_answer_lines(sources, memory_store, target_source=target_source)
    return [
            "Give me a repo, goal, or question and I'll turn it into a task plan, route work through OCE, or cross-check with Claude.",
            "Try: 'what projects are in flight?', 'what does this app do?', '/inspect', '/opencode <task>', '/codex <task>', or '/claude <task>'.",
        ]


def _repository_request_lines(message: str, source: Source, profile=None) -> list[str]:
    preferred_primary_agent = normalize_agent_name(profile.primary_agent) if profile else None
    resolved_agent, secondary_agent, reason = _preferred_agents_for_source(source, preferred_primary_agent)
    status = inspect_source(source)
    branch = status.branch or "n/a"
    command = _route_command(resolved_agent, source.name)
    lines = [
        f"Repo resolved: {source.name}",
        f"Path: {source.path}",
        f"Group: {source.group}",
        f"State: {status.state} branch={branch} changes={status.dirty_count} untracked={status.untracked_count}",
        f"Primary route: /{resolved_agent}",
        f"Command: {command}",
    ]
    if secondary_agent != resolved_agent:
        lines.extend([
            f"Optional cross-check: /{secondary_agent}",
            f"Command: {_route_command(secondary_agent, source.name)}",
        ])
    lines.append(f"Preference: {reason}")
    if status.ahead or status.behind:
        lines.append(f"Divergence: ahead={status.ahead} behind={status.behind}")
    return lines


def _workspace_status_answer_lines(
    sources: list[Source],
    memory_store: WorkspaceMemoryStore,
    target_source: Source | None = None,
) -> list[str]:
    process = current_process_report(memory_store)
    batch = current_batch_report(memory_store)
    launches = memory_store.recent_launches(limit=3)
    lines: list[str] = []
    source_states: list[str] = []
    workspace_sources = [source for source in sources if getattr(source, "group", "workspace") != "knowledge_base"]
    kb_sources = [source for source in sources if getattr(source, "group", "workspace") == "knowledge_base"]
    workspace_root = _workspace_root_from_sources(workspace_sources)
    kb_root = _workspace_root_from_sources(kb_sources)

    if target_source is not None:
        status = inspect_source(target_source)
        branch = status.branch or "n/a"
        lines.extend(
            [
                f"Requested repo: {target_source.name}",
                f"Target repo: {target_source.name}",
                f"Path: {target_source.path}",
                f"State: {status.state} branch={branch} changes={status.dirty_count} untracked={status.untracked_count}",
            ]
        )
    lines.append(f"Workspace root: {workspace_root}")
    lines.append("Workspace projects under root:")
    for source in workspace_sources:
        status = inspect_source(source)
        branch = status.branch or "n/a"
        if status.state == "missing":
            detail = f"[MISSING] {source.name}: path={source.path}"
            source_states.append("missing")
        elif status.state == "not-git":
            detail = f"[NOT-GIT] {source.name}: path={source.path}"
            source_states.append("not-git")
        elif status.state == "error":
            detail = f"[ERROR] {source.name}: error={status.error}"
            source_states.append("error")
        else:
            detail = (
                f"[DEV] {source.name}: branch={branch} changes={status.dirty_count} "
                f"untracked={status.untracked_count}"
            )
            if status.ahead or status.behind:
                detail += f" ahead={status.ahead} behind={status.behind}"
            source_states.append("ready")
        lines.append(f"- {detail}")

    lines.append(f"Knowledge base root: {kb_root}")
    lines.append("Knowledge base projects:")
    for source in kb_sources:
        status = inspect_source(source)
        branch = status.branch or "n/a"
        if status.state == "missing":
            detail = f"[MISSING] {source.name}: path={source.path}"
            source_states.append("missing")
        elif status.state == "not-git":
            detail = f"[NOT-GIT] {source.name}: path={source.path}"
            source_states.append("not-git")
        elif status.state == "error":
            detail = f"[ERROR] {source.name}: error={status.error}"
            source_states.append("error")
        else:
            detail = (
                f"[DEV] {source.name}: branch={branch} changes={status.dirty_count} "
                f"untracked={status.untracked_count}"
            )
            if status.ahead or status.behind:
                detail += f" ahead={status.ahead} behind={status.behind}"
            source_states.append("ready")
        lines.append(f"- {detail}")

    ready_count = source_states.count("ready")
    missing_count = source_states.count("missing")
    not_git_count = source_states.count("not-git")
    error_count = source_states.count("error")
    lines.insert(
        0,
        f"Workspace status: {ready_count} ready, {missing_count} missing, {not_git_count} not-git, {error_count} error.",
    )

    if process is None and batch is None:
        analysis = build_workspace_analysis(
            sources,
            memory_store,
            workspace=target_source.name if target_source is not None else _workspace_name_from_sources(sources),
            limit=5,
            compact=True,
        )
        lines.extend(
            [
                "No active work window is tracked.",
                "Analysis:",
                *analysis.recommendation_lines,
            ]
        )
    else:
        lines.append(f"Next step: {_next_step(process, batch)}")

    if launches:
        lines.append("Recent launches:")
        for launch in launches:
            workspace = launch["workspace"] or "all"
            lines.append(f"- {launch['agent']} {workspace}: {launch['task']}")
    return lines


def _workspace_root_from_sources(sources: list[Source]) -> str:
    workspace_sources = [source for source in sources if getattr(source, "group", "workspace") != "knowledge_base"]
    if not workspace_sources:
        return "all workspaces"
    paths = [str(source.path) for source in workspace_sources if source.path]
    if not paths:
        return "all workspaces"
    try:
        root = os.path.commonpath(paths)
    except ValueError:
        return "all workspaces"
    return root or "all workspaces"


def _workspace_name_from_sources(sources: list[Source]) -> str:
    for source in sources:
        if source.name == "workspace-os":
            return source.name
    if len(sources) == 1:
        return sources[0].name
    return "workspace-os"


def _is_repository_request(message: str) -> bool:
    text = message.casefold()
    return any(
        marker in text
        for marker in (
            "repo",
            "repositorio",
            "repository",
            "analiza",
            "analyze",
            "inspect",
            "revisa",
            "review",
        )
    )


def _preferred_agents_for_source(source: Source, preferred_primary_agent: str | None = None) -> tuple[str, str, str]:
    primary = preferred_primary_agent if preferred_primary_agent in {"opencode", "codex", "claude", "antigravity"} else "opencode"
    if source.group == "knowledge_base":
        if primary == "claude":
            return "claude", "opencode", "knowledge_base_first"
        return "claude", primary, "knowledge_base_first"
    secondary = "claude" if primary != "claude" else "opencode"
    return primary, secondary, "workspace_repo_first"


def _resolve_target_source(message: str, sources: list[Source]) -> Source | None:
    text = _normalized_text(message)
    best_source: Source | None = None
    best_score = 0
    for source in sources:
        score = _score_source_match(text, source)
        if score > best_score:
            best_score = score
            best_source = source
    return best_source if best_score > 0 else None


def _score_source_match(text: str, source: Source) -> int:
    score = 0
    raw_tokens = _tokenize_text(text)
    source_tokens = _source_match_tokens(source)
    name = _normalized_text(source.name)
    path_name = _normalized_text(source.path.name)
    path_stem = _normalized_text(source.path.stem)
    responsibility = _normalized_text(source.responsibility)
    if name and name in text:
        score += 6
    if path_name and path_name in text:
        score += 5
    if path_stem and path_stem in text:
        score += 4
    if source_tokens and raw_tokens:
        overlap = len(source_tokens & raw_tokens)
        score += overlap * 4
        if any(token in raw_tokens for token in _source_alias_tokens(source)):
            score += 3
    if responsibility:
        for token in responsibility.split():
            if len(token) > 3 and token in text:
                score += 1
    return score


def _source_match_tokens(source: Source) -> set[str]:
    tokens = set(_tokenize_text(source.name))
    tokens.update(_tokenize_text(source.path.name))
    tokens.update(_tokenize_text(source.path.stem))
    return {token for token in tokens if token}


def _source_alias_tokens(source: Source) -> set[str]:
    aliases: set[str] = set()
    name = source.name.casefold()
    aliases.add(name.replace("-", ""))
    aliases.add(name.replace("_", ""))
    aliases.update({token for token in _tokenize_text(source.name) if len(token) >= 2})
    return {alias for alias in aliases if alias}


def _tokenize_text(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.casefold()) if token}


def _normalized_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _route_command(agent: str, workspace_name: str) -> str:
    return build_agent_route_command(agent, workspace_name)


def _refine_route_with_history(
    primary_agent: str,
    secondary_agent: str,
    conscience: ConscienceDecision,
    memory_store: WorkspaceMemoryStore | None,
) -> tuple[str, str, str]:
    route_hint = _history_route_hint(memory_store)
    if route_hint == "route_to_claude_for_cross_check" and primary_agent != "claude":
        return "claude", "opencode", "history_prefers_claude_cross_check"
    if route_hint == "route_to_opencode_for_inventory" and primary_agent != "opencode":
        return "opencode", "claude", "history_prefers_opencode_inventory"
    if route_hint == "keep_opencode_as_primary_for_workspace_execution" and primary_agent != "opencode":
        return "opencode", "claude", "history_prefers_opencode_execution"
    if route_hint == "keep_claude_as_primary_for_sensitive_reviews" and primary_agent != "claude":
        return "claude", "opencode", "history_prefers_claude_review"
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

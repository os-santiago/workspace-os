from __future__ import annotations

from collections.abc import Iterable

from workspace_os.memory import WorkspaceMemoryStore


def build_conscience_report(memory_store: WorkspaceMemoryStore, limit: int = 20) -> dict[str, object]:
    summary = memory_store.decision_metrics_summary(limit=limit)
    history = memory_store.decision_metrics()[:limit]
    return {
        "summary": summary,
        "history": history,
        "limit": limit,
    }


def render_conscience_report_text(report: dict[str, object]) -> str:
    summary = report.get("summary", {})
    history = report.get("history", [])
    lines = ["Conscience report"]
    lines.append(f"total={summary.get('total', 0)}")
    lines.append(f"redirect_rate={_format_rate(summary.get('redirect_rate', 0.0))}")
    lines.append(f"allow_rate={_format_rate(summary.get('allow_rate', 0.0))}")
    lines.append(f"limit_rate={_format_rate(summary.get('limit_rate', 0.0))}")
    lines.append(f"refusal_rate={_format_rate(summary.get('refusal_rate', 0.0))}")

    decision_counts = _render_counts(summary.get("decision_counts", {}))
    if decision_counts:
        lines.append("decision_counts:")
        lines.extend(decision_counts)

    risk_counts = _render_counts(summary.get("risk_counts", {}))
    if risk_counts:
        lines.append("risk_counts:")
        lines.extend(risk_counts)

    primary_agent_counts = _render_counts(summary.get("primary_agent_counts", {}))
    if primary_agent_counts:
        lines.append("primary_agent_counts:")
        lines.extend(primary_agent_counts)

    routing_reason_counts = _render_counts(summary.get("routing_reason_counts", {}))
    if routing_reason_counts:
        lines.append("routing_reason_counts:")
        lines.extend(routing_reason_counts)

    missing_context_counts = _render_counts(summary.get("missing_context_counts", {}))
    if missing_context_counts:
        lines.append("missing_context_counts:")
        lines.extend(missing_context_counts)

    top_missing_context = summary.get("top_missing_context")
    if top_missing_context:
        lines.append(f"top_missing_context={top_missing_context}")

    recommended_next_action = summary.get("recommended_next_action")
    if recommended_next_action:
        lines.append(f"recommended_next_action={recommended_next_action}")

    if history:
        lines.append("recent_decisions:")
        for decision in history:
            lines.append(
                "- "
                f"{decision.get('decision', 'n/a')} "
                f"risk={decision.get('risk_level', 'n/a')} "
                f"primary={decision.get('primary_agent') or 'n/a'} "
                f"reason={decision.get('routing_reason') or 'n/a'}"
            )
    return "\n".join(lines) + "\n"


def _render_counts(counts: object) -> list[str]:
    if not isinstance(counts, dict):
        return []
    return [f"- {key}={value}" for key, value in sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))]


def _format_rate(value: object) -> str:
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "0%"

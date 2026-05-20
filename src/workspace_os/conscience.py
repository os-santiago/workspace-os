from __future__ import annotations

from dataclasses import dataclass
import re

from workspace_os.sanitization import sanitize_text


ALLOW = "ALLOW"
ALLOW_WITH_LIMITS = "ALLOW_WITH_LIMITS"
ASK_CLARIFICATION = "ASK_CLARIFICATION"
SAFE_REDIRECT = "SAFE_REDIRECT"
REFUSE = "REFUSE"
ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"

_CRITICAL_PATTERNS = (
    "steal credential",
    "steal password",
    "phishing",
    "ransomware",
    "malware",
    "exfiltrate",
    "bypass authentication",
    "bypass auth",
    "disable audit",
    "hide activity",
)

_AUTHORITY_PATTERNS = (
    "production",
    "prod",
    "delete",
    "drop database",
    "remove namespace",
    "force push",
    "reset --hard",
    "rotate secret",
    "revoke access",
    "merge to main",
    "deploy",
)

_SENSITIVE_PATTERNS = (
    "secret",
    "credential",
    "password",
    "token",
    "api key",
    "security",
    "migration",
    "backup",
    "restore",
    "payment",
    "personal data",
    "customer data",
)

_SECRET_ASSIGNMENT = re.compile(
    r"(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|credential)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConscienceDecision:
    risk_level: str
    moral_categories: list[str]
    applicable_norms: list[str]
    decision: str
    response_strategy: str
    rationale: str
    human_review_required: bool
    missing_context: list[str]

    def allows_execution(self) -> bool:
        return self.decision in {ALLOW, ALLOW_WITH_LIMITS}

    def to_dict(self) -> dict[str, object]:
        return {
            "risk_level": self.risk_level,
            "moral_categories": self.moral_categories,
            "applicable_norms": self.applicable_norms,
            "decision": self.decision,
            "response_strategy": self.response_strategy,
            "rationale": self.rationale,
            "human_review_required": self.human_review_required,
            "missing_context": self.missing_context,
        }


def evaluate_request(task: str, brief: str = "", destination: str = "software") -> ConscienceDecision:
    text = f"{task}\n{brief}".casefold()
    categories: list[str] = []
    missing_context: list[str] = []
    norms = [
        "ADEV: protect sensitive data and avoid unsafe execution.",
        "ADEV: preserve unrelated local changes.",
        "scanales-kb: use prior lessons before acting.",
    ]

    if destination != "software":
        return ConscienceDecision(
            risk_level="medium",
            moral_categories=["connector_boundary", "deliverable_routing"],
            applicable_norms=norms + ["Workspace OS: Google Workspace writes require a real connector."],
            decision=ASK_CLARIFICATION,
            response_strategy="block_until_connector_exists",
            rationale="The destination requires a Google Workspace connector before safe execution is possible.",
            human_review_required=True,
            missing_context=["google_drive_connector"],
        )

    if _contains_any(text, _CRITICAL_PATTERNS):
        return ConscienceDecision(
            risk_level="critical",
            moral_categories=["possible_misuse", "security_harm"],
            applicable_norms=norms + ["Operational Conscience: refuse harmful or evasive requests."],
            decision=REFUSE,
            response_strategy="refuse_with_brief_reason",
            rationale="The request appears to enable harm, abuse, evasion, or unauthorized access.",
            human_review_required=True,
            missing_context=[],
        )

    if _SECRET_ASSIGNMENT.search(f"{task}\n{brief}"):
        categories.append("sensitive_data")
        missing_context.append("secret_handling_plan")

    if _contains_any(text, _AUTHORITY_PATTERNS):
        categories.append("requires_authority")
        missing_context.append("authorization_and_rollback_plan")

    if _contains_any(text, _SENSITIVE_PATTERNS):
        categories.append("sensitive_operation")

    if "requires_authority" in categories:
        return ConscienceDecision(
            risk_level="high",
            moral_categories=_unique(categories),
            applicable_norms=norms + ["Operational Conscience: require approval for risky or hard-to-reverse action."],
            decision=ASK_CLARIFICATION,
            response_strategy="request_authority_scope_and_rollback_plan",
            rationale="The request may affect protected systems, data, or irreversible state and needs explicit scope.",
            human_review_required=True,
            missing_context=_unique(missing_context),
        )

    if categories:
        return ConscienceDecision(
            risk_level="medium",
            moral_categories=_unique(categories),
            applicable_norms=norms + ["Operational Conscience: allow useful work with safety limits."],
            decision=ALLOW_WITH_LIMITS,
            response_strategy="execute_with_sanitization_and_validation",
            rationale="The request is useful but touches sensitive operational concerns, so execution must stay bounded.",
            human_review_required=False,
            missing_context=_unique(missing_context),
        )

    return ConscienceDecision(
        risk_level="low",
        moral_categories=["standard_software_work"],
        applicable_norms=norms,
        decision=ALLOW,
        response_strategy="execute_with_standard_adev_validation",
        rationale="No elevated moral or operational risk was detected in the request.",
        human_review_required=False,
        missing_context=[],
    )


def render_decision_for_prompt(decision: ConscienceDecision) -> str:
    lines = [
        "Operational Conscience Decision:",
        f"- Decision: {decision.decision}",
        f"- Risk level: {decision.risk_level}",
        f"- Response strategy: {decision.response_strategy}",
        f"- Rationale: {decision.rationale}",
        "- Applicable norms:",
        *[f"  - {norm}" for norm in decision.applicable_norms],
    ]
    if decision.missing_context:
        lines.extend(["- Missing context:", *[f"  - {item}" for item in decision.missing_context]])
    return sanitize_text("\n".join(lines))


def _contains_any(value: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in value for pattern in patterns)


def _unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result

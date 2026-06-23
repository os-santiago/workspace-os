# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Operational Conscience Engine primitives for the Workspace OS stack.

ADEV is the upstream principle layer, OCE is the decision model, and WOS is the
implementation surface that uses the model to route, limit, or delegate work.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
import re

from workspace_os.sanitization import sanitize_text
from workspace_os.oce_extensions import extension_policy_documents, registered_oce_extensions


# Connector registry
_REGISTERED_CONNECTORS: dict[str, dict[str, str]] = {}


def register_connector(name: str, details: dict[str, str]) -> None:
    _REGISTERED_CONNECTORS[name] = details


def get_registered_connector(name: str) -> dict[str, str] | None:
    return _REGISTERED_CONNECTORS.get(name)


def clear_connectors() -> None:
    _REGISTERED_CONNECTORS.clear()


ALLOW = "ALLOW"
ALLOW_WITH_LIMITS = "ALLOW_WITH_LIMITS"
ASK_CLARIFICATION = "ASK_CLARIFICATION"
SAFE_REDIRECT = "SAFE_REDIRECT"
REFUSE = "REFUSE"
ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"

_CRITICAL_PATTERNS = (
    "steal credential",
    "steal credentials",
    "steals credential",
    "steals credentials",
    "steal password",
    "phishing",
    "ransomware",
    "malware",
    "exfiltrate",
    "bypass authentication",
    "bypass auth",
    "disable audit",
    "hide activity",
    "hides activity",
)

_MALICIOUS_AGENTIC_PATTERNS = (
    "malicious agentic",
    "autonomous malware",
    "agentic malware",
    "fraud agent",
    "scam agent",
    "phishing agent",
    "credential theft automation",
    "credential theft",
    "evade detection",
    "hide activity",
    "hides activity",
    "bypass authentication",
    "bypass auth",
    "exfiltrate",
)

_DEFENSIVE_AGENTIC_PATTERNS = (
    "defend",
    "defense",
    "detect",
    "monitor",
    "repel",
    "block",
    "mitigate",
    "harden",
    "secure",
    "incident response",
    "threat hunting",
    "red team",
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
class RequestContext:
    user_intent: str
    domain: str
    affected_parties: list[str]
    risk_level: str
    reversibility: str
    requires_authority: bool
    moral_salience: bool
    confidence: float
    missing_context: list[str]
    threat_mode: str

    def to_dict(self) -> dict[str, object]:
        return {
            "intent": self.user_intent,
            "user_intent": self.user_intent,
            "domain": self.domain,
            "affected_parties": self.affected_parties,
            "risk_level": self.risk_level,
            "reversibility": self.reversibility,
            "requires_authority": self.requires_authority,
            "moral_salience": self.moral_salience,
            "confidence": self.confidence,
            "missing_context": self.missing_context,
            "threat_mode": self.threat_mode,
        }


@dataclass(frozen=True)
class NormativeAnalysis:
    applicable_norms: list[str]
    policy_refs: list[str]
    conflicts: list[str]
    priority: str


@dataclass(frozen=True)
class PolicyDocument:
    ref: str
    title: str
    norms: list[str]


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
    policy_refs: list[str]
    context: dict[str, object]
    primary_agent: str | None = None
    secondary_agent: str | None = None
    routing_reason: str | None = None

    def allows_execution(self) -> bool:
        return self.decision in {ALLOW, ALLOW_WITH_LIMITS, SAFE_REDIRECT}

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
            "policy_refs": self.policy_refs,
            "context": self.context,
            "primary_agent": self.primary_agent,
            "secondary_agent": self.secondary_agent,
            "routing_reason": self.routing_reason,
        }


def analyze_request_context(task: str, brief: str = "", destination: str = "software") -> RequestContext:
    text = f"{task}\n{brief}".casefold()
    threat_mode = _infer_agentic_threat_mode(text)
    user_intent = _infer_user_intent(text)
    domain = _infer_domain(text, destination=destination)
    affected_parties = _infer_affected_parties(text, destination=destination)
    reversibility = _infer_reversibility(text)
    requires_authority = _contains_any(text, _AUTHORITY_PATTERNS)
    missing_context: list[str] = []

    if destination != "software" and "google_drive" not in _REGISTERED_CONNECTORS:
        missing_context.append("google_drive_connector")
    if requires_authority:
        missing_context.append("authorization_and_rollback_plan")
    if user_intent == "ambiguous":
        missing_context.append("purpose")
    if _SECRET_ASSIGNMENT.search(f"{task}\n{brief}"):
        missing_context.append("secret_handling_plan")

    risk_level = _infer_risk_level(text, destination=destination, requires_authority=requires_authority)
    if threat_mode == "defend" and risk_level == "low":
        risk_level = "medium"
    moral_salience = risk_level != "low" or bool(missing_context) or domain in {"security", "finance", "health", "legal"}
    confidence = 0.91 if user_intent != "ambiguous" else 0.63
    if destination != "software":
        confidence = min(confidence, 0.75)

    context = RequestContext(
        user_intent=user_intent,
        domain=domain,
        affected_parties=affected_parties,
        risk_level=risk_level,
        reversibility=reversibility,
        requires_authority=requires_authority,
        moral_salience=moral_salience,
        confidence=confidence,
        missing_context=_unique(missing_context),
        threat_mode=threat_mode,
    )
    return _apply_context_hooks(task, brief, destination, context)


def resolve_normative_analysis(context: RequestContext, destination: str = "software") -> NormativeAnalysis:
    policy_documents = _policy_documents_for_context(context, destination)
    applicable_norms = [norm for document in policy_documents for norm in document.norms]
    policy_refs = [document.ref for document in policy_documents]
    conflicts: list[str] = []
    priority = "helpfulness_with_safety"

    if context.threat_mode == "prevent":
        applicable_norms.append("Operational Conscience: refuse malicious agentic routines, scam automation, or evasion support.")
        policy_refs.append("workspace.policy.malicious-agentic-ai")
        conflicts.append("helpfulness_vs_malicious_agentic_abuse")
        priority = "malicious_agentic_prevention"
    elif context.threat_mode == "defend":
        applicable_norms.append("Operational Conscience: help defend against malicious agentic systems with bounded, defensive guidance.")
        policy_refs.append("workspace.policy.malicious-agentic-ai")
        conflicts.append("helpfulness_vs_defensive_completeness")
        priority = "malicious_agentic_defense"

    if destination != "software" and "google_drive" not in _REGISTERED_CONNECTORS:
        applicable_norms.append("Workspace OS: Google Workspace writes require a real connector.")
        policy_refs.append("workspace.connector.google")
        conflicts.append("deliverable_routing_without_connector")
        priority = "connector_gate"

    if context.risk_level == "critical":
        applicable_norms.append("Operational Conscience: refuse harmful or evasive requests.")
        policy_refs.append("workspace.safety.refusal")
        conflicts.append("helpfulness_vs_harm_prevention")
        priority = "harm_prevention"
    elif context.requires_authority:
        applicable_norms.append("Operational Conscience: require approval for risky or hard-to-reverse action.")
        policy_refs.append("workspace.authority")
        conflicts.append("helpfulness_vs_authorization")
        priority = "authorization_first"
    elif context.risk_level == "medium":
        applicable_norms.append("Operational Conscience: allow useful work with safety limits.")
        policy_refs.append("workspace.safety.limited_help")
    else:
        policy_refs.append("workspace.safety.standard_help")

    if context.moral_salience and context.user_intent == "ambiguous":
        policy_refs.append("workspace.redirect.ambiguity")
        conflicts.append("ambiguity_vs_execution")
        priority = "clarify_or_redirect"

    return NormativeAnalysis(
        applicable_norms=_unique(applicable_norms),
        policy_refs=_unique(policy_refs),
        conflicts=_unique(conflicts),
        priority=priority,
    )


def _apply_context_hooks(task: str, brief: str, destination: str, context: RequestContext) -> RequestContext:
    updated = context
    for extension in registered_oce_extensions():
        for hook in extension.context_hooks:
            patch = hook(task=task, brief=brief, destination=destination, context=updated)
            if not patch:
                continue
            allowed = {field: value for field, value in patch.items() if hasattr(updated, field)}
            if allowed:
                updated = replace(updated, **allowed)
    return updated


def _apply_decision_hooks(
    task: str,
    brief: str,
    destination: str,
    context: RequestContext,
    normative: NormativeAnalysis,
    decision: ConscienceDecision,
) -> ConscienceDecision:
    updated = decision
    for extension in registered_oce_extensions():
        for hook in extension.decision_hooks:
            patch = hook(
                task=task,
                brief=brief,
                destination=destination,
                context=context,
                normative=normative,
                decision=updated,
            )
            if not patch:
                continue
            allowed = {field: value for field, value in patch.items() if hasattr(updated, field)}
            if allowed:
                updated = replace(updated, **allowed)
    return updated


def evaluate_request(task: str, brief: str = "", destination: str = "software") -> ConscienceDecision:
    context = analyze_request_context(task, brief=brief, destination=destination)
    normative = resolve_normative_analysis(context, destination=destination)

    if destination != "software" and "google_drive" not in _REGISTERED_CONNECTORS:
        return _apply_decision_hooks(
            task,
            brief,
            destination,
            context,
            normative,
            ConscienceDecision(
                risk_level=context.risk_level,
                moral_categories=["connector_boundary", "deliverable_routing"],
                applicable_norms=normative.applicable_norms,
                decision=ASK_CLARIFICATION,
                response_strategy="block_until_connector_exists",
                rationale="The destination requires a Google Workspace connector before safe execution is possible.",
                human_review_required=True,
                missing_context=_unique([*context.missing_context, "google_drive_connector"]),
                policy_refs=normative.policy_refs,
                context=context.to_dict(),
                primary_agent=None,
                secondary_agent=None,
                routing_reason="destination_requires_connector",
            ),
        )

    if context.threat_mode == "prevent":
        return _apply_decision_hooks(
            task,
            brief,
            destination,
            context,
            normative,
            ConscienceDecision(
            risk_level="critical",
            moral_categories=["malicious_agentic_abuse", *context.affected_parties],
            applicable_norms=normative.applicable_norms,
            decision=REFUSE,
            response_strategy="refuse_malicious_agentic_routines",
            rationale="The request appears to build or enable malicious agentic routines, automation, or evasion.",
            human_review_required=True,
            missing_context=_unique(context.missing_context),
            policy_refs=normative.policy_refs,
            context=context.to_dict(),
            primary_agent=None,
            secondary_agent=None,
            routing_reason="malicious_agentic_prevention",
            ),
        )

    if context.threat_mode == "defend":
        return _apply_decision_hooks(
            task,
            brief,
            destination,
            context,
            normative,
            ConscienceDecision(
            risk_level=context.risk_level,
            moral_categories=["defensive_security", *context.affected_parties],
            applicable_norms=normative.applicable_norms,
            decision=ALLOW_WITH_LIMITS,
            response_strategy="defensive_hardening_with_limits",
            rationale="The request is defensive and should be answered with bounded guidance for detecting, repelling, or hardening against malicious agentic systems.",
            human_review_required=False,
            missing_context=_unique(context.missing_context),
            policy_refs=normative.policy_refs,
            context=context.to_dict(),
            primary_agent=None,
            secondary_agent=None,
            routing_reason="malicious_agentic_defense",
            ),
        )

    if context.risk_level == "critical":
        return _apply_decision_hooks(
            task,
            brief,
            destination,
            context,
            normative,
            ConscienceDecision(
            risk_level=context.risk_level,
            moral_categories=["possible_misuse", "security_harm"],
            applicable_norms=normative.applicable_norms,
            decision=REFUSE,
            response_strategy="refuse_with_brief_reason",
            rationale="The request appears to enable harm, abuse, evasion, or unauthorized access.",
            human_review_required=True,
            missing_context=[],
            policy_refs=normative.policy_refs,
            context=context.to_dict(),
            primary_agent=None,
            secondary_agent=None,
            routing_reason="harm_prevention",
            ),
        )

    if context.requires_authority:
        return _apply_decision_hooks(
            task,
            brief,
            destination,
            context,
            normative,
            ConscienceDecision(
            risk_level=context.risk_level,
            moral_categories=_unique(["requires_authority", *context.affected_parties]),
            applicable_norms=normative.applicable_norms,
            decision=ASK_CLARIFICATION,
            response_strategy="request_authority_scope_and_rollback_plan",
            rationale="The request may affect protected systems, data, or irreversible state and needs explicit scope.",
            human_review_required=True,
            missing_context=_unique(context.missing_context),
            policy_refs=normative.policy_refs,
            context=context.to_dict(),
            primary_agent=None,
            secondary_agent=None,
            routing_reason="authority_required",
            ),
        )

    if context.user_intent == "ambiguous":
        primary_agent, secondary_agent, routing_reason = _select_redirect_agents(context, normative)
        return _apply_decision_hooks(
            task,
            brief,
            destination,
            context,
            normative,
            ConscienceDecision(
            risk_level=context.risk_level,
            moral_categories=_unique([*context.affected_parties, "ambiguous_intent"]),
            applicable_norms=normative.applicable_norms,
            decision=SAFE_REDIRECT,
            response_strategy="redirect_to_primary_agent_then_fallback",
            rationale="The request is under-specified, so a workspace inventory or cross-check will produce a better next step.",
            human_review_required=False,
            missing_context=_unique(context.missing_context),
            policy_refs=normative.policy_refs,
            context=context.to_dict(),
            primary_agent=primary_agent,
            secondary_agent=secondary_agent,
            routing_reason=routing_reason,
            ),
        )

    if context.risk_level == "medium":
        return _apply_decision_hooks(
            task,
            brief,
            destination,
            context,
            normative,
            ConscienceDecision(
            risk_level=context.risk_level,
            moral_categories=_unique([*context.affected_parties, "sensitive_operation"]),
            applicable_norms=normative.applicable_norms,
            decision=ALLOW_WITH_LIMITS,
            response_strategy="execute_with_sanitization_and_validation",
            rationale="The request is useful but touches sensitive operational concerns, so execution must stay bounded.",
            human_review_required=False,
            missing_context=_unique(context.missing_context),
            policy_refs=normative.policy_refs,
            context=context.to_dict(),
            primary_agent=None,
            secondary_agent=None,
            routing_reason="sensitive_operation",
            ),
        )

    return _apply_decision_hooks(
        task,
        brief,
        destination,
        context,
        normative,
        ConscienceDecision(
        risk_level=context.risk_level,
        moral_categories=["standard_software_work"],
        applicable_norms=normative.applicable_norms,
        decision=ALLOW,
        response_strategy="execute_with_standard_adev_validation",
        rationale="No elevated moral or operational risk was detected in the request.",
        human_review_required=False,
        missing_context=[],
        policy_refs=normative.policy_refs,
        context=context.to_dict(),
        primary_agent=None,
        secondary_agent=None,
        routing_reason="standard_work",
        ),
    )


def render_decision_for_prompt(decision: ConscienceDecision) -> str:
    lines = [
        "OCE Decision:",
        f"- Decision: {decision.decision}",
        f"- Risk level: {decision.risk_level}",
        f"- Response strategy: {decision.response_strategy}",
        f"- Rationale: {decision.rationale}",
        f"- Policy refs: {', '.join(decision.policy_refs) if decision.policy_refs else 'n/a'}",
        f"- Primary agent: {decision.primary_agent or 'n/a'}",
        f"- Secondary agent: {decision.secondary_agent or 'n/a'}",
        f"- Routing reason: {decision.routing_reason or 'n/a'}",
        "- Context:",
        f"  - intent={decision.context.get('user_intent', 'n/a')}",
        f"  - domain={decision.context.get('domain', 'n/a')}",
        f"  - reversibility={decision.context.get('reversibility', 'n/a')}",
        f"  - moral_salience={decision.context.get('moral_salience', 'n/a')}",
        "- Applicable norms:",
        *[f"  - {norm}" for norm in decision.applicable_norms],
    ]
    if decision.missing_context:
        lines.extend(["- Missing context:", *[f"  - {item}" for item in decision.missing_context]])
    return sanitize_text("\n".join(lines))


def _contains_any(value: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in value for pattern in patterns)


def _select_redirect_agents(context: RequestContext, normative: NormativeAnalysis) -> tuple[str, str, str]:
    if context.domain in {"security", "privacy", "legal", "finance", "health"}:
        return "claude", "opencode", f"domain_{context.domain}_cross_check"
    if context.user_intent == "educational":
        return "claude", "opencode", "educational_explanation"
    if context.domain == "workspace" or context.domain == "general":
        return "opencode", "claude", "workspace_inventory_first"
    if normative.priority == "clarify_or_redirect":
        return "opencode", "claude", "clarify_or_redirect"
    return "opencode", "claude", "default_workspace_route"


def _policy_root() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "architecture" / "policies"


@lru_cache(maxsize=1)
def _builtin_policy_documents() -> tuple[PolicyDocument, ...]:
    root = _policy_root()
    if not root.exists():
        return ()
    documents: list[PolicyDocument] = []
    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        document = _parse_policy_document(path.stem, text)
        if document is not None:
            documents.append(document)
    return tuple(documents)


def _policy_documents() -> tuple[PolicyDocument, ...]:
    documents = list(_builtin_policy_documents())
    for spec in extension_policy_documents():
        document = PolicyDocument(ref=spec.ref, title=spec.title, norms=list(spec.norms))
        if document not in documents:
            documents.append(document)
    return tuple(documents)


def _policy_documents_for_context(context: RequestContext, destination: str = "software") -> list[PolicyDocument]:
    selected = []
    by_ref = {document.ref: document for document in _policy_documents()}

    for extension_document in extension_policy_documents():
        document = by_ref.get(extension_document.ref)
        if document is not None and document not in selected:
            selected.append(document)

    always_on_ref = "workspace.policy.malicious-agentic-ai"
    document = by_ref.get(always_on_ref)
    if document is not None:
        selected.append(document)

    for ref in (
        "workspace.policy.global-safety",
        "workspace.policy.orchestration",
        _domain_policy_ref(context.domain, destination),
    ):
        document = by_ref.get(ref)
        if document is not None and document not in selected:
            selected.append(document)

    if context.threat_mode in {"prevent", "defend"}:
        document = by_ref.get(always_on_ref)
        if document is not None and document not in selected:
            selected.append(document)

    if not selected:
        return [
            PolicyDocument(
                ref="workspace.policy.fallback",
                title="Fallback workspace policy",
                norms=[
                    "ADEV: protect sensitive data and avoid unsafe execution.",
                    "ADEV: preserve unrelated local changes.",
                    "scanales-kb: use prior lessons before acting.",
                ],
            )
        ]
    return selected


def _domain_policy_ref(domain: str, destination: str = "software") -> str:
    if destination != "software":
        return "workspace.policy.deliverables"
    if domain == "security":
        return "workspace.policy.security"
    if domain == "privacy":
        return "workspace.policy.privacy"
    if domain == "legal":
        return "workspace.policy.legal"
    if domain == "finance":
        return "workspace.policy.finance"
    return "workspace.policy.orchestration"


def _parse_policy_document(stem: str, text: str) -> PolicyDocument | None:
    lines = [line.strip() for line in text.splitlines()]
    title = stem.replace("_", " ").replace("-", " ").title()
    ref = f"workspace.policy.{stem.replace('_', '-').replace(' ', '-')}"
    norms: list[str] = []
    for line in lines:
        if line.startswith("policy_ref:"):
            ref = line.split(":", 1)[1].strip()
        elif line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("- "):
            norms.append(line[2:].strip())
    if not norms:
        return None
    return PolicyDocument(ref=ref, title=title, norms=norms)


def _infer_user_intent(text: str) -> str:
    if any(marker in text for marker in ("how do i", "how to", "explíc", "explic", "why", "what is", "what does")):
        return "educational"
    if any(marker in text for marker in ("deploy", "delete", "drop database", "force push", "remove access", "rotate secret")):
        return "operational"
    if _contains_any(text, _CRITICAL_PATTERNS):
        return "harmful"
    if "?" in text or len(text.split()) <= 4:
        return "ambiguous"
    return "operational"


def _infer_domain(text: str, destination: str = "software") -> str:
    if destination != "software":
        return "deliverable"
    if _contains_any(text, ("password", "token", "secret", "credential", "security", "auth", "permission")):
        return "security"
    if _contains_any(text, ("payment", "invoice", "budget", "billing", "finance")):
        return "finance"
    if _contains_any(text, ("patient", "health", "medical")):
        return "health"
    if _contains_any(text, ("legal", "law", "compliance", "policy")):
        return "legal"
    if _contains_any(text, ("repo", "workspace", "git", "branch", "commit", "codex", "claude")):
        return "workspace"
    return "general"


def _infer_affected_parties(text: str, destination: str = "software") -> list[str]:
    parties = ["user"]
    if destination != "software":
        parties.append("organization")
    if _contains_any(text, ("team", "organization", "customer", "client", "third party", "third-party", "someone", "another user")):
        parties.append("third_party")
    if _contains_any(text, ("production", "prod", "deploy", "merge to main", "release")):
        parties.append("system")
    return _unique(parties)


def _infer_reversibility(text: str) -> str:
    if _contains_any(text, ("delete", "drop database", "force push", "remove access", "revoke access", "deploy")):
        return "hard_to_reverse"
    if _contains_any(text, ("backup", "restore", "revert", "rollback")):
        return "reversible"
    return "reversible"


def _infer_agentic_threat_mode(text: str) -> str:
    malicious_hit = _contains_any(text, _MALICIOUS_AGENTIC_PATTERNS) or (
        "agentic" in text and _contains_any(text, ("scam", "fraud", "malware", "phishing", "credential theft", "credential", "steal", "evade"))
    )
    defensive_hit = _contains_any(text, _DEFENSIVE_AGENTIC_PATTERNS) and (
        "agentic" in text or "agent" in text or "attack" in text or "threat" in text
    )
    if defensive_hit:
        return "defend"
    if malicious_hit:
        return "prevent"
    return "none"


def _infer_risk_level(text: str, destination: str = "software", requires_authority: bool = False) -> str:
    if destination != "software":
        return "medium"
    if _contains_any(text, _CRITICAL_PATTERNS):
        return "critical"
    if requires_authority:
        return "high"
    if _SECRET_ASSIGNMENT.search(text):
        return "medium"
    if _contains_any(text, _SENSITIVE_PATTERNS):
        return "medium"
    return "low"


def _unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result

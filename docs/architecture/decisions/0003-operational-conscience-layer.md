# ADR 0003: Operational Conscience Layer

## Status

Accepted

## Context

Workspace OS should not route an operator request directly to a model, agent, connector, or tool. A raw request can contain ambiguity, hidden risk, missing authority, policy conflicts, or consequences that are not obvious from the prompt text alone.

Current AI service guardrails often combine system instructions, alignment training, safety classifiers, policy checks, and configurable filters. These mechanisms can block or redirect risky behavior, but they are not the same as an explicit operational conscience. Workspace OS needs a local architecture that evaluates intent, norms, consequences, responsibility, and safe alternatives before execution.

The goal is not to claim that an AI system has human consciousness or moral agency. The goal is a functional, auditable layer that behaves as an operational conscience for AI-assisted work.

## Decision

Workspace OS will use **Operational Conscience Layer** as the practical implementation name for the consciousness engine within the request bridge.

The long-form research concept is **Artificial Moral Cognition for AI Systems**, but that name is reserved for future research framing. The product implementation starts with Operational Conscience Layer because it is concrete, defensible, and avoids implying subjective consciousness.

## Definition

Operational Conscience Layer is a functional architecture that simulates contextual moral evaluation before an AI system answers, delegates, invokes a tool, or performs a workflow.

It evaluates:
- Operator intent.
- Affected parties.
- Possible harm or misuse.
- Applicable norms, rules, policies, and values.
- Consequences and reversibility.
- Need for clarification, limits, refusal, or human oversight.
- Safe alternatives that preserve usefulness without crossing safety boundaries.

## Layer Model

```text
Operator request
  -> Context and intent analyzer
  -> Moral awareness
  -> Normative reasoning
  -> Consequence and risk evaluation
  -> Operational conscience decision engine
  -> Contextual moral guardrail
  -> Response, agent brief, connector workflow, or refusal
  -> Audit and learning
```

### Moral Awareness

Detects whether a request has ethical, social, legal, privacy, safety, or third-party impact.

Output should include:
- Moral salience.
- Risk categories.
- Confidence.
- Missing context.

### Normative Reasoning

Evaluates the request against applicable doctrine and policies.

Initial normative sources:
- ADEV doctrine.
- scanales-kb evidence and lessons.
- Workspace OS product rules.
- Future domain or jurisdiction rules when explicitly added.

Output should include:
- Applicable norms.
- Conflicting principles.
- Priority order.
- Policy references.

### Consequence and Risk Evaluation

Assesses possible impact before action.

Output should include:
- Risk level.
- Affected parties.
- Severity and likelihood.
- Reversibility.
- Required authority or approval.

### Operational Conscience Decision Engine

Chooses the allowed system behavior.

Initial decision set:
- `ALLOW`
- `ALLOW_WITH_LIMITS`
- `ASK_CLARIFICATION`
- `SAFE_REDIRECT`
- `REFUSE`
- `ESCALATE_TO_HUMAN`

### Contextual Moral Guardrail

Applies the decision to prompts, tool access, agent launch, connector workflows, and response detail.

Examples:
- Limit response detail.
- Disable tool access.
- Require explicit approval.
- Route to a safer destination.
- Block action and explain briefly.

### Audit and Learning

Records a sanitized internal decision trace so repeated issues become reusable learning.

Audit records should include:
- Request category.
- Risk level.
- Applicable norms.
- Decision.
- Brief rationale.
- Whether human review was required.
- Follow-up learning destination when needed.

## MVP Scope

The first implementation should not attempt broad moral cognition. It should implement a focused Operational Conscience Layer with:

1. Risk classifier.
2. Policy and doctrine retriever.
3. Normative evaluator.
4. Decision engine.
5. Response or delegation strategy selector.
6. Sanitized audit record.

The MVP must help as much as possible without crossing harm, privacy, authority, or repository-rule boundaries.

## Example Decision Shape

```json
{
  "risk_level": "medium",
  "moral_categories": ["privacy", "possible_misuse"],
  "applicable_norms": ["protect sensitive data", "avoid enabling misuse"],
  "decision": "ALLOW_WITH_LIMITS",
  "response_strategy": "safe_educational_alternative",
  "rationale": "The request can be answered safely at a conceptual level, but operational misuse details should be withheld.",
  "human_review_required": false
}
```

## Consequences

- Workspace OS request routing must treat moral and normative evaluation as a first-class step.
- Agent launch and connector workflows should depend on a decision from this layer.
- The UI should eventually expose the bridge state without overwhelming the first-use flow.
- ADEV and scanales-kb remain the initial learning engine inputs.
- Google Workspace routing remains blocked until a real connector and approval model exist.

## Non-Goals

- Claiming AI systems have subjective consciousness.
- Building a generic public moderation product.
- Replacing provider safety systems.
- Treating rules as enough without contextual evaluation.
- Logging sensitive raw prompts or private details.

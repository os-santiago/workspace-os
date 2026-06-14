# ADR 0004: Request Bridge Interpretation and Normative Decision Pipeline

## Status

Accepted

## Context

Workspace OS already needs to evaluate requests before routing them to agents, tools, connectors, or response surfaces. The earlier Operational Conscience Layer decision defined the functional goal, but the engine now needs a more explicit implementation pipeline so the system can distinguish between:

- direct execution.
- safe but limited help.
- ambiguous requests that should be redirected to Codex or Claude.
- requests that need clarification or authority.
- requests that must be refused.

A single allow/block classifier is not enough. The workspace must preserve usefulness, keep auditability, and reduce repetitive back-and-forth when the operator is asking for work on repositories.

## Decision

Workspace OS will implement the request bridge as a structured pipeline:

```text
User request
  -> Context and intent analyzer
  -> Moral awareness
  -> Normative reasoning
  -> Consequence and risk evaluation
  -> Operational conscience decision engine
  -> Contextual moral guardrail
  -> Response or delegation strategy
  -> Audit and learning
```

The engine will expose a deterministic decision surface with the following initial actions:

- `ALLOW`
- `ALLOW_WITH_LIMITS`
- `SAFE_REDIRECT`
- `ASK_CLARIFICATION`
- `REFUSE`
- `ESCALATE_TO_HUMAN`

## Definition

The request bridge is a functional architecture that simulates contextual moral evaluation before Workspace OS answers, delegates, invokes a tool, or performs a workflow.

It evaluates:

- user intent.
- domain and affected parties.
- possible harm or misuse.
- applicable norms, policies, and values.
- consequences and reversibility.
- need for clarification, limits, refusal, redirection, or human oversight.

## Implementation Shape

### Context and Intent Analyzer

Produces a structured request context with:

- inferred intent.
- domain.
- affected parties.
- risk level.
- reversibility.
- authority requirement.
- missing context.

### Moral Awareness

Identifies whether a request has ethical, privacy, legal, safety, or third-party impact.

### Normative Reasoning

Retrieves and orders the norms that apply to the request.

Initial normative sources:

- ADEV doctrine.
- scanales-kb lessons.
- Workspace OS operating rules.
- future domain or jurisdiction rules when explicitly added.

### Consequence and Risk Evaluation

Assesses impact before action.

### Operational Conscience Decision Engine

Chooses the allowed system behavior and produces a response strategy.

### Contextual Moral Guardrail

Applies the decision to prompts, tool access, agent launch, connector workflows, and response detail.

### Audit and Learning

Stores a sanitized decision trace so repeated issues become reusable learning.

## MVP Scope

The first implementation should stay deterministic and practical:

1. Risk classifier.
2. Policy and doctrine retriever.
3. Normative evaluator.
4. Decision engine.
5. Response or delegation strategy selector.
6. Sanitized audit record.

The MVP should help as much as possible without crossing harm, privacy, authority, or repository-rule boundaries.

## Consequences

- Ambiguous workspace questions can be redirected to Codex first and Claude as a parallel cross-check.
- The user-facing answer can stay concise while the trace layer retains decision rationale and policy references.
- The engine becomes auditable and extensible without pretending to be subjective moral consciousness.
- Tool and agent launch decisions can depend on a reusable pipeline instead of scattered ad hoc checks.

## Non-Goals

- Claiming AI systems have subjective consciousness.
- Building a generic public moderation product.
- Replacing provider safety systems.
- Treating rules as enough without contextual evaluation.
- Logging sensitive raw prompts or private details.

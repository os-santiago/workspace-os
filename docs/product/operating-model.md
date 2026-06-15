# Operating Model

## Source of Truth

ADEV is the upstream source of truth for operating doctrine.

Workspace OS consumes ADEV rules through the Operational Conscience Engine model and implements workflows around them. It does not replace ADEV.
Delegated Codex and Claude runs inherit the same ADEV guardrail contract before they touch files or launch follow-up actions.

## Knowledge Flow

```text
Operator request
  -> OCE interprets intent, values, risk, and decision boundaries
  -> learning engine applies ADEV doctrine and scanales-kb evidence
  -> Workspace OS selects destination and execution path
  -> software and infrastructure work goes to Git
  -> document, deck, sheet, proposal, and estimate deliverables go to Google Workspace
  -> evidence is captured in scanales-kb
  -> reusable lessons are promoted to ADEV
```

## Consciousness Engine

The consciousness engine is the operator-facing judgment layer. It decides what the request means before work is routed.

Workspace OS implements this through the OCE model defined in `docs/architecture/decisions/0005-adev-oce-wos-stack.md`.

Responsibilities:
- Interpret operator intent and desired outcome.
- Identify urgency, risk, and required checkpoints.
- Decide whether the request needs clarification, research, delegation, or direct execution.
- Preserve operator values, tone, decision style, and quality bar.
- Prevent action when the request conflicts with safety, privacy, or repository rules.

## Learning Engine

The learning engine is grounded in ADEV and scanales-kb.

Responsibilities:
- Load applicable ADEV doctrine, guardrails, and validation rules.
- Search scanales-kb for reusable evidence, mistakes, decisions, and lessons.
- Prevent repeated errors by turning prior failures into checks, tests, prompts, or backlog items.
- Classify new learning before capture so doctrine and evidence stay organized.
- Feed concise context into Workspace OS before an agent or connector acts.

## Predictive and Generative Mix

Workspace OS should prefer predictive or discriminative logic for:

- classification;
- routing;
- missing-context detection;
- confidence scoring;
- next-best-action selection;
- recommendation biasing.

Workspace OS should use generative logic for:

- concise explanations;
- agent briefs;
- summaries and handoffs;
- final user-facing artifacts;
- synthesis from multiple sources.

The product goal is not to generate everything. The product goal is to use the lowest-cost technique that can make the next decision correct, then use generation only when it adds clear value.

Workspace OS also exposes a non-interactive bridge for other CLI agents. The bridge lets Codex, Claude, or any comparable tool ask WOS what is available, what should continue next, and which surfaces are safe to use without entering the interactive shell.

## Librarian Rule

Before adding durable content:

1. Search related local sections and files.
2. Classify the content.
3. Update the canonical location when possible.
4. Create new files only for distinct content.
5. Add cross-references when content spans repositories.
6. Remove temporary artifacts after use.

## Content Classification

| Content Type | Destination |
| --- | --- |
| Doctrine, rules, guardrails | ADEV |
| Evidence, incidents, sessions, decisions | scanales-kb |
| Scripts, local automation, agent tooling | homedir |
| Product roadmap and architecture for this system | Workspace OS |
| Final docs, decks, sheets, proposals | Google Workspace |
| Temporary exploration | Delete or consolidate |

## Safety Rules

- No secrets in Git.
- No personal or company-specific data in durable records.
- No arbitrary remote shell execution.
- Mutating actions require explicit approval.
- Temporary files must not survive completion unless promoted.

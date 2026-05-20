# Operating Model

## Source of Truth

ADEV is the upstream source of truth for operating doctrine.

Workspace OS consumes ADEV rules and implements workflows around them. It does not replace ADEV.

## Knowledge Flow

```text
Operator request
  -> consciousness engine interprets intent, values, risk, and decision boundaries
  -> learning engine applies ADEV doctrine and scanales-kb evidence
  -> Workspace OS selects destination and execution path
  -> software and infrastructure work goes to Git
  -> document, deck, sheet, proposal, and estimate deliverables go to Google Workspace
  -> evidence is captured in scanales-kb
  -> reusable lessons are promoted to ADEV
```

## Consciousness Engine

The consciousness engine is the operator-facing judgment layer. It decides what the request means before work is routed.

Workspace OS implements this as the Operational Conscience Layer defined in `docs/architecture/decisions/0003-operational-conscience-layer.md`.

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

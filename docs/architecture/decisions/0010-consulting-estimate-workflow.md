# ADR 0010: Consulting Estimate Workflow

## Status

Accepted

## Context

Workspace OS needs a repeatable way to help produce consulting estimates for platform, modernization, automation, and SDLC acceleration work.

Estimation is valuable only when it stays explicit about:

- scope;
- assumptions;
- exclusions;
- risks;
- dependencies;
- confidence.

The product also needs to keep the estimate flow aligned with the repository responsibilities model:

- estimation logic and evidence live in Git and workspace docs;
- final office deliverables can be produced in Google Workspace;
- the system should not invent an estimate without surfacing the assumptions behind it.

## Decision

Workspace OS will implement consulting estimation as a structured, reviewable workflow.

The workflow should:

1. capture the delivery request and classify the work domain;
2. extract scope, constraints, assumptions, exclusions, risks, dependencies, and confidence;
3. flag unrealistic or underspecified assumptions;
4. search related prior work or evidence before drafting;
5. produce a sanitized estimate brief or outline as the default artifact;
6. route the result to Google Workspace when a final deliverable is desired, without mixing raw evidence into the final output.

## Estimate Contract

The estimate workflow must include at least:

- problem statement;
- desired outcome;
- in-scope items;
- out-of-scope items;
- assumptions;
- exclusions;
- risks;
- dependencies;
- confidence level or confidence note;
- delivery format or destination.

The workflow should make unsupported assumptions visible instead of hiding them in prose.

## Validation Model

The estimate workflow passes validation when:

- the estimate brief is sanitized;
- unrealistic assumptions are explicitly marked;
- the output includes the required estimate fields;
- the draft can be reviewed before any external deliverable is produced;
- the destination aligns with the product boundary for Google Workspace deliverables.

A good estimate is not just a number. It is a reviewable set of assumptions that can survive scrutiny.

## Consequences

- Workspace OS can help create credible consulting estimates instead of vague summary text.
- Operators can review and adjust assumptions before producing a deliverable.
- The workflow becomes reusable across platform, modernization, automation, and SDLC work.
- The output can evolve into Google Workspace deliverables without changing the estimation logic.

## Non-Goals

- Producing a final customer quote with no assumptions.
- Hiding risks or exclusions.
- Bypassing review in order to generate a polished artifact faster.
- Treating Google Workspace as the source of truth for estimation logic.

## Notes

- This decision formalizes WSOS-011.
- The implementation should stay deterministic and reviewable first; generative polish is secondary to clarity and accuracy.

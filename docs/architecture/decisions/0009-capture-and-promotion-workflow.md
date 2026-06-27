# ADR 0009: Capture and Promotion Workflow

## Status

Accepted

## Context

Workspace OS needs a safe workflow for turning raw operating observations into durable knowledge without mixing source responsibilities.

The product already distinguishes between:

- execution content in Git and workspace repos;
- evidence and lessons in scanales-kb or similar knowledge stores;
- doctrine in ADEV;
- final deliverables in Google Workspace when appropriate.

The capture/promotion flow must preserve that separation while still making it easy to convert useful observations into reusable doctrine.

## Decision

Workspace OS will treat capture and promotion as two distinct, reviewable steps:

1. **Capture** converts a sanitized observation into an evidence record.
2. **Promotion** converts reusable evidence into a doctrine proposal.

The workflow rules are:

- capture is evidence-first and sanitizes before write;
- capture must map the input to the right source responsibility;
- promotion must search for related existing doctrine before proposing new content;
- promotion should create a proposed diff or brief, not silently rewrite doctrine;
- both steps must preserve source references and avoid copying private raw content into the wrong repository.

## Capture Contract

Capture is responsible for:

- accepting a typed input such as daily, incident, session, or decision;
- sanitizing personal, customer, or secret-like data before durable storage;
- storing the result in the evidence-oriented destination only;
- retaining enough metadata to recover provenance without exposing raw content;
- refusing writes when the source or target is not appropriate.

Capture should answer the question:

> What did we learn or observe, and where should that evidence live?

## Promotion Contract

Promotion is responsible for:

- identifying reusable lessons inside evidence;
- searching for similar doctrine before proposing changes;
- drafting a proposed doctrine update or brief;
- linking the proposal back to evidence references;
- avoiding direct mutation of doctrine unless a separate approval path exists.

Promotion should answer the question:

> What reusable rule or practice should we suggest for doctrine?

## Validation Model

The workflow passes validation when:

- the capture path produces sanitized evidence;
- the promotion path produces a clear proposal or diff;
- neither step stores raw sensitive output by default;
- the workflow keeps source boundaries intact;
- a manual review of a sanitized sample incident shows the data lands in the expected destination.

## Consequences

- WOS can capture learning without polluting doctrine.
- The system can promote reusable rules without losing provenance.
- Operators have a predictable, reviewable path from observation to doctrine.
- The workflow stays aligned with the librarian model and the privacy policy.

## Non-Goals

- Auto-promoting every capture into doctrine.
- Writing raw incident data into doctrine or deliverables.
- Skipping sanitization for the sake of convenience.
- Treating capture and promotion as the same operation.

## Notes

- This decision formalizes the workflow referenced by WSOS-005.
- The existing CLI capture and promotion commands remain the implementation surface, but the workflow boundary is now explicit.

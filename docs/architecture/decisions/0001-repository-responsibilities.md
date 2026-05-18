# ADR 0001: Repository Responsibilities

## Status

Accepted

## Context

The workspace depends on multiple repositories and cloud tools. Without explicit boundaries, knowledge becomes duplicated, mixed, or hard to reuse.

## Decision

Use dedicated responsibilities:

- ADEV governs doctrine.
- scanales-kb stores sanitized evidence and learning.
- homedir executes local automation and workstation behavior.
- Workspace OS defines and implements the workspace product.
- Google Workspace stores final office deliverables when appropriate.

## Consequences

- New reusable operating rules are promoted to ADEV.
- New evidence is captured in scanales-kb.
- New automation is implemented in homedir unless it belongs directly to Workspace OS.
- Workspace OS focuses on orchestration, classification, indexing, and product management.


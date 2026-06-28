# Agent Performance Analytics Dashboard

Workspace OS exposes a lightweight performance dashboard for local squad analysis.

## What It Shows

- Per-agent success rates
- Average task duration
- Role performance for `primary`, `cross-check`, and `observer`
- Recent learning velocity
- Specialization patterns based on observed task types

## Where It Appears

- Web UI panel
- JSON endpoint at `/api/agent-performance`
- Markdown export at `/api/agent-performance.md`

## Why It Stays Lightweight

The dashboard is built from the existing WOS queue state and does not require an external telemetry stack.

It is meant to improve routing and team selection inside the workspace, not to introduce a heavy observability dependency.

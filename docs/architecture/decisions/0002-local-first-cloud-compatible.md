# ADR 0002: Local First, Cloud Compatible

## Status

Accepted

## Context

The workspace must work locally first while remaining deployable to cloud or private infrastructure later.

## Decision

Build local-first components with cloud-compatible boundaries:

- Use plain files and Git for durable source-controlled assets.
- Keep runtime indexes rebuildable.
- Avoid machine-specific committed configuration.
- Define connectors through configuration.
- Treat cloud services as integrations, not as the core source of truth.

## Consequences

- The MVP can run without cloud infrastructure.
- Deployment can later move to containers, a private server, Kubernetes, or OpenShift.
- Secrets and local paths must remain outside committed files.


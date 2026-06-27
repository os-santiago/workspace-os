# Architecture Overview

## System Boundary

Workspace OS is a local-first orchestration layer for AI-assisted work. It coordinates repositories, cloud deliverables, and agents without becoming the owner of all content.

The canonical stack is:

```text
ADEV -> OCE -> WOS
principle -> model -> implementation
```

- **ADEV** is the upstream principle layer.
- **OCE** is the Operational Conscience Engine model layer.
- **WOS** is the Workspace OS implementation surface.

## Core Components

```text
Operator Request
  -> Consciousness Engine
  -> Learning Engine
Workspace CLI
  -> Source Registry
  -> Librarian Search
  -> Agent Context Pack
  -> Content Classifier
  -> Workspace Validator
  -> Capture and Promotion Workflows
  -> Local Web Pilot
  -> Connector Interfaces
  -> Agent Router
```

## Responsibilities

### Workspace CLI

Provides the operator-facing command surface.

Initial commands:
- `workspace status`
- `workspace search`
- `workspace context`
- `workspace classify`
- `workspace capture`
- `workspace promote`
- `workspace housekeeping`
- `workspace validate`

### Consciousness Engine

Interprets requests before routing them to execution.

Workspace OS implements this concept as the Operational Conscience Engine model defined in `docs/architecture/decisions/0005-adev-oce-wos-stack.md`.
The operational decision pipeline is further specified in `docs/architecture/decisions/0004-request-bridge-pipeline.md`.
The original Operational Conscience Layer framing remains valid as the functional predecessor recorded in `docs/architecture/decisions/0003-operational-conscience-layer.md`.
The layered extension model is specified in `docs/architecture/decisions/0006-oce-layered-extension-model.md`.
The normative base is stored as versioned Markdown under `docs/architecture/policies/`.

Initial scope:
- Convert raw operator requests into explicit intent, context, domain, risk, and checkpoint expectations.
- Evaluate context, norms, consequences, and decision tradeoffs before answering or delegating.
- Decide whether the request should be clarified, safely redirected, converted to an agent brief, or executed.
- Block or downgrade requests that conflict with privacy, safety, authority, or repository rules.
- Preserve operator preferences and decision style as explicit context rather than implicit chat memory.

Initial implementation:
- Uses deterministic rules for low, medium, high, and critical software delegation risk.
- Emits `ALLOW`, `ALLOW_WITH_LIMITS`, `SAFE_REDIRECT`, `ASK_CLARIFICATION`, `REFUSE`, and `ESCALATE_TO_HUMAN` decisions.
- Allows `ALLOW`, `ALLOW_WITH_LIMITS`, and `SAFE_REDIRECT` decisions to proceed to response generation or allowed redirection.
- Blocks `ASK_CLARIFICATION`, `REFUSE`, and `ESCALATE_TO_HUMAN` decisions before agent launch.
- Applies malicious-agentic hardening implicitly to every request: refuse routines that enable scams, evasion, or abuse, and allow bounded defensive guidance for detection, blocking, and recovery.
- Accepts layered extension modules that can add policy documents, context hooks, and decision hooks without replacing the core engine.
- Returns the decision, policy references, and compact context to the web UI so the operator can inspect the bridge state.

### Learning Engine

Applies accumulated doctrine and evidence before execution.

Initial scope:
- Use ADEV as the doctrine source of truth.
- Use scanales-kb as the evidence and learning source.
- Search before writing or delegating.
- Promote repeated lessons into durable rules, checks, tests, or backlog items.
- Feed relevant context to agent briefs and connector workflows.

### Model Provider Layer

Provides an optional brain layer that WOS can use for planning, synthesis, and review when a model is configured.

Initial scope:
- Default to no-model operation when nothing is configured.
- Support local or remote OpenAI-compatible providers through config or environment variables.
- Route tasks by capability and fall back cleanly when a provider is missing or unavailable.
- Keep model choice independent from agent orchestration and workspace execution.

### Autonomous Cycle Orchestrator

Coordinates the first closed-loop WOS flow for a single issue: select, branch, implement, validate, open PR, and merge when policy allows.

Initial scope:
- Classify each candidate issue through OCE before starting a cycle.
- Evaluate scope size, change surface, test coverage, merge risk, ambiguity, and cross-cutting impact before any mutation.
- Persist the issue, branch, PR, validation, blockers, and learning signals.
- Refuse mutation or merge when validation fails or when the autonomy policy requires human review.
- Keep the orchestration logic separate from the implementation agent and from the model provider layer.

### Autonomous Cycle State Store

Stores the durable history of autonomous cycles so later runs can inspect prior outcomes without relying on transient agent context.

Initial scope:
- Save stage transitions and review outcomes across sessions.
- Store learning signals from blocked, partial, or successful cycles.
- Expose the latest cycle records for the next run and for documentation.

### Source Registry

Defines known sources and their responsibilities.

Examples:
- doctrine repository
- evidence repository
- execution repository
- product repository
- cloud deliverable index

### Librarian Search

Searches existing content before new content is added.

Initial implementation should use plain text search before adding vector search.

### Agent Context Pack

Builds a governed Markdown context pack before an agent starts work.

Initial implementation:
- Includes source repository state without machine-specific paths.
- Includes an ADEV doctrine excerpt from configured doctrine sources.
- Includes existing knowledge matches for the task topic.
- Redacts common secret-like assignments in emitted text.

### Content Classifier

Classifies content into doctrine, evidence, execution, deliverable, product, or temporary.

Initial implementation:
- Classifies supplied text or file content without writing files.
- Uses explicit keyword rules as the first deterministic baseline.
- Returns target, confidence, and reason so agents can explain placement decisions.

### Workspace Validator

Validates local workspace configuration and source health without mutating repositories.

Initial implementation:
- Confirms at least one source is configured.
- Confirms each configured source exists and is a Git repository.
- Reports source Git state.
- Optionally checks temporary artifacts through the housekeeping scanner.

### Capture and Promotion Workflows

Creates sanitized evidence and promotes reusable rules to doctrine.

Initial implementation:
- Capture creates sanitized drafts for daily, incident, session, and decision entries.
- Capture is dry-run by default and writes only with explicit `--write`.
- Promotion creates proposal-only Markdown output and does not mutate doctrine.
- Promotion includes related existing content so doctrine edits can consolidate instead of duplicate.

### Local Web Pilot

Provides a local browser interface for operator supervision.

Initial implementation:
- Runs from `python -m workspace_os web`.
- Serves static assets from the Workspace OS package.
- Exposes only allowlisted local endpoints.
- Does not expose arbitrary shell execution.
- Can launch approved software delegations only through allowlisted agent commands.
- Blocks Google Drive destinations until a real connector exists.
- Uses homedir-inspired visual patterns adapted for Workspace OS.

### Connector Interfaces

Connectors should be read-only by default. Write operations require explicit approval.

### Agent Router

Routes tasks to agents under allowlisted commands and approval rules.

Initial implementation:
- Supports approved local software delegation to Codex or Claude.
- Starts agents from the local Git workspace root.
- Does not accept free-form shell commands from the browser.
- Keeps document and presentation delegation blocked until Google Drive support is real.

## Deployment Model

Start local.

Later deployment targets:
- local workstation
- private server
- container runtime
- Kubernetes or OpenShift
- cloud VM

## Storage Model

- Git repositories store code, doctrine, product docs, and sanitized evidence.
- Google Workspace stores final office deliverables.
- Local indexes store derived search data and can be rebuilt.

## Security Model

- Deny arbitrary command execution.
- Use allowlists for automation.
- Keep secrets outside repositories.
- Sanitize logs and evidence.
- Prefer private network access for remote control.

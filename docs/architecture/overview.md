# Architecture Overview

## System Boundary

Workspace OS is a local-first orchestration layer for AI-assisted work. It coordinates repositories, cloud deliverables, and agents without becoming the owner of all content.

## Core Components

```text
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
- Uses homedir-inspired visual patterns adapted for Workspace OS.

### Connector Interfaces

Connectors should be read-only by default. Write operations require explicit approval.

### Agent Router

Routes tasks to agents under allowlisted commands and approval rules.

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

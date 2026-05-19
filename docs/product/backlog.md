# Product Backlog

## Now

### WSOS-001: Define Repository Responsibilities

As the operator, the system needs clear repository responsibilities so knowledge and execution do not drift.

Acceptance criteria:
- ADEV, scanales-kb, homedir, Google Workspace, and Workspace OS responsibilities are documented.
- Boundaries are described in the architecture overview.

### WSOS-002: Define MVP CLI Commands

As the operator, the system needs a small CLI command set before implementation starts.

Acceptance criteria:
- Initial commands are listed.
- Each command has a clear purpose.
- Commands avoid arbitrary shell execution.

### WSOS-003: Define Librarian Workflow

As an agent, the system needs a repeatable workflow to search and classify before adding content.

Acceptance criteria:
- Search-before-write behavior is documented.
- Content classification rules are documented.
- Duplicate avoidance is documented.

### WSOS-010: Define Agent Alignment Context Pack

As the operator, the system needs agents to start work with the right doctrine, evidence, tone, constraints, and known mistakes.

Acceptance criteria:
- Context pack structure is documented.
- ADEV rules are included by reference.
- Relevant scanales-kb evidence can be attached by topic.
- The pack lists assumptions, constraints, and forbidden behaviors.

Initial implementation:
- `python -m workspace_os context <topic>` emits a governed Markdown context pack.
- The pack includes source state, ADEV excerpt, task-relevant existing knowledge, and required agent behavior.
- Output avoids local machine paths and redacts common secret-like assignments.

### WSOS-011: Define Consulting Estimate Workflow

As the operator, the system needs repeatable estimation support for platform and modernization work.

Acceptance criteria:
- Estimate workflow captures scope, assumptions, exclusions, risks, and confidence.
- The workflow flags unrealistic assumptions.
- Output destination is Google Workspace, with source logic in Git.

### WSOS-012: Define Integrated Tool Environment MVP

As the operator, the system needs one local entrypoint for repositories, agents, and workspace state.

Acceptance criteria:
- MVP entrypoint is documented.
- It connects ADEV, scanales-kb, homedir, and workspace-os.
- It supports status, search, and agent context preparation before implementation expands.

## In Progress

### WSOS-004: Implement Workspace Source Registry

As the workspace controller, the system needs to know which repositories and folders are part of the workspace.

Acceptance criteria:
- Source registry format is defined.
- Local paths can be configured without committing sensitive machine-specific details.
- Registry supports repository type, responsibility, and search scope.

Initial implementation:
- Example JSON registry exists at `config/workspace.sources.example.json`.
- Relative paths are resolved from the registry file location.
- Source records include name, type, responsibility, path, and search scope.

### WSOS-005: Implement `workspace status`

As the operator, the system needs a quick status across core repositories.

Acceptance criteria:
- Reports branch, dirty state, untracked files, and upstream divergence.
- Does not mutate repositories.
- Output is concise and suitable for chat summaries.

Initial implementation:
- `python -m workspace_os status` reports repository branch, clean or dirty state, untracked count, and upstream divergence.
- Missing paths and non-Git paths are reported without mutation.

### WSOS-006: Implement `workspace search`

As an agent, the system needs localized search across doctrine and evidence.

Acceptance criteria:
- Searches configured repositories.
- Supports scoped search by source type.
- Returns file paths and line numbers.

Initial implementation:
- `python -m workspace_os search <query>` searches configured text files.
- `--source-type` limits search to one source type.
- Results include source, relative path, line number, and matching text.

### WSOS-013: Implement `workspace housekeeping`

As an operator, the system needs a non-destructive way to find temporary artifacts before handoff.

Acceptance criteria:
- Reports likely temporary files across configured sources.
- Does not delete files.
- Excludes VCS and common generated directories.

Initial implementation:
- `python -m workspace_os housekeeping` reports likely scratch, backup, log, and temporary files.

## Next

## Later

### WSOS-007: Add Google Workspace Metadata Connector

Acceptance criteria:
- Read-only by default.
- Captures metadata and links, not document contents unless explicitly allowed.
- Does not store sensitive content in Git.

### WSOS-008: Add Agent Command Router

Acceptance criteria:
- Uses allowlisted commands.
- Requires approval for mutations.
- Logs sanitized action summaries.

### WSOS-009: Add Secure Remote Interface

Acceptance criteria:
- Works through private network access.
- Does not expose arbitrary command execution.
- Provides audit logs and a kill switch.

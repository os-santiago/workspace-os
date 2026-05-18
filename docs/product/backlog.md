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

## Next

### WSOS-004: Implement Workspace Source Registry

As the workspace controller, the system needs to know which repositories and folders are part of the workspace.

Acceptance criteria:
- Source registry format is defined.
- Local paths can be configured without committing sensitive machine-specific details.
- Registry supports repository type, responsibility, and search scope.

### WSOS-005: Implement `workspace status`

As the operator, the system needs a quick status across core repositories.

Acceptance criteria:
- Reports branch, dirty state, untracked files, and upstream divergence.
- Does not mutate repositories.
- Output is concise and suitable for chat summaries.

### WSOS-006: Implement `workspace search`

As an agent, the system needs localized search across doctrine and evidence.

Acceptance criteria:
- Searches configured repositories.
- Supports scoped search by source type.
- Returns file paths and line numbers.

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


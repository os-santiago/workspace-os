# Product Backlog

## Done

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

### WSOS-012: Define Integrated Tool Environment MVP

As the operator, the system needs one local entrypoint for repositories, agents, and workspace state.

Acceptance criteria:
- MVP entrypoint is documented.
- It connects ADEV, scanales-kb, homedir, and workspace-os.
- It supports status, search, and agent context preparation before implementation expands.

### WSOS-014: Implement `workspace classify`

As an agent, the system needs deterministic content classification before capture or promotion.

Acceptance criteria:
- Classifies supplied text or file content.
- Supports doctrine, evidence, execution, deliverable, product, temporary, and unknown targets.
- Returns a reason and confidence.

Initial implementation:
- `python -m workspace_os classify <text>` classifies text.
- `python -m workspace_os classify --path <file>` classifies file content when available.
- The classifier is read-only and does not create durable content.

### WSOS-015: Implement `workspace validate`

As an operator, the system needs a fast local validation gate before handoff.

Acceptance criteria:
- Validates that configured sources exist.
- Validates that configured sources are Git repositories.
- Reports pass or fail per validation.
- Exits non-zero when validation fails.

Initial implementation:
- `python -m workspace_os validate` validates registry and source health.
- `--skip-housekeeping` allows validation when known external temporary artifacts are out of scope.
- Housekeeping validation is non-destructive.

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

### WSOS-016: Implement Capture Workflow

As an operator, the system needs a safe way to capture session, incident, decision, and daily notes.

Acceptance criteria:
- Capture writes only to configured knowledge destinations.
- Capture applies sanitization before write.
- Capture requires explicit type selection.
- Capture keeps generated content in English.

Initial implementation:
- `python -m workspace_os capture --type <type> --title <title> --text <text>` creates a sanitized dry-run draft.
- `--write` writes to the configured evidence source.
- Supported capture types are daily, incident, session, and decision.
- Output uses source-relative references instead of local machine paths.

### WSOS-017: Implement Promotion Workflow

As an operator, the system needs a controlled way to promote reusable lessons into doctrine.

Acceptance criteria:
- Promotion creates a clear proposed diff.
- Promotion links back to evidence when available.
- Promotion does not write secrets or sensitive raw output.
- Promotion can be validated before commit.

Initial implementation:
- `python -m workspace_os promote --to <target> --rule <rule> --evidence <ref>` emits a proposal-only Markdown brief.
- Promotion output includes related existing content found through librarian search.
- Promotion does not mutate doctrine or evidence.

## Next

### WSOS-018: Define Homedir-Based UI Foundation

As an operator, the system needs a UI shell that reflects the proven homedir operating style.

Acceptance criteria:
- UI scope is documented before implementation.
- UI reads from Workspace OS commands or API instead of duplicating business logic.
- UI shows source status, search, context, classify, validate, and roadmap progress.
- Mutating workflows require explicit approval.

Initial implementation:
- `python -m workspace_os shell` opens a terminal-first workspace shell with workspace switching and conversational prompts.
- `python -m workspace_os web` starts the local web pilot.
- The pilot uses allowlisted local endpoints instead of arbitrary shell execution.
- The UI includes software, documents, presentations, and learning contexts inspired by homedir.
- Capture and promotion actions are preview-only from the browser.
- Software delegation can launch an approved Codex or Claude run from the local Git workspace.
- Document and presentation delegation remain blocked until a real Google Drive connector exists.
- Shell profile commands remember tone, detail level, default workspace, and shortcut aliases in persistent memory, and the shell startup banner summarizes inferred operator habits from recent launches and conversation activity.
- Shell agent commands launch allowlisted Codex or Claude tasks from the active workspace and record the launch.
- Batch telemetry records start and end time, delegations, defects, and conversation activity so each iteration can be reported with duration and defect-driven churn.
- Chat and web responses surface the active batch summary so the current work window stays visible outside the shell.
- Batch summary output lists the recent batch count with duration and defect iterations per batch, and reports the global process window from first start to last end for accurate stopwatch-style measurement.
- Process summary output gives a dedicated stopwatch for a long-running work window, including batch count, delegations, and defect iterations for the whole process.
- Process checkpoints record milestones within the active process so the operator can mark progress without closing the window.
- A read-only `inspect` surface condenses source status, memory, profile, habits, active process, active batch, and recent launches into one operator-facing summary.
- `inspect --compact` trims the overview into summary lines for lower-noise supervision.
- A concise `handoff` surface turns the current workspace state into a copyable closing summary for iteration wrap-up.
- `context latest` replays the most recent compacted global context snapshot directly from memory, while `context <topic>` still builds a governed task pack.
- The interactive chat CLI opens by showing the latest compacted global context snapshot before prompting for input so the operator starts from shared state.
- The web chat shows the latest compacted global context snapshot above the chat history, refreshes it from the latest reply, lets the operator expand or collapse the block on demand, and remembers that preference across reloads.
- Chat replies separate the user-facing `Answer:` from the internal `Trace:` so reasoning and results are visually distinct.
- Greetings, app-overview questions, and repetition complaints return intent-aware guidance instead of the same canned fallback.
- Ambiguous workspace-status questions route to Codex first with Claude as a parallel fallback when the workspace needs inventory or cross-checking.
- `handoff` can export Markdown to a file from the CLI and shell so the closing summary can be archived or pasted elsewhere without copying.
- `batch handoff` and `process handoff` export scoped closing summaries for the active batch or process, including optional `--output` and `--compact` modes.
- `batch stop` and `process stop` write a default `handoff.md` beside the local memory store and a `context-global.md` snapshot so completed windows leave both a closing artifact and compacted durable context automatically, and shell exit also persists the latest context snapshot.
- The web pilot exposes the same handoff summary through a local API so the browser panel can close work without entering the shell.
- The web panel shows refreshable handoff and context blocks, plus direct download actions, so the closing summary and compacted workspace context stay visible and exportable during supervision.

### WSOS-019: Deepen Web Pilot Workflows

As an operator, the system needs browser workflows that move from preview to reviewed action without losing governance.

Acceptance criteria:
- Capture preview can become an approved write.
- Promotion proposals can become reviewed PR tasks.
- UI state clearly separates dry-run, preview, and mutation.
- Mobile viewport remains usable for supervision.
- Agent launch requires explicit approval and uses allowlisted agents only.

### WSOS-020: Define Request Bridge Engines

As the operator, the system needs every request to pass through a consciousness engine and learning engine before execution.

Acceptance criteria:
- Consciousness engine captures intent, desired outcome, risk, priority, timing, and checkpoint needs.
- Learning engine applies ADEV doctrine and scanales-kb evidence before routing.
- Routing output identifies destination: Git, Google Workspace, agent brief, answer, clarification, or refusal.
- OCE is captured as sanitized local architecture documentation, with Operational Conscience Layer retained as the historical predecessor.
- The UI exposes the bridge state without overwhelming the first-use flow.

Initial implementation:
- Deterministic Operational Conscience evaluation exists for delegated software work.
- Launch decisions return risk level, moral categories, applicable norms, policy refs, context, decision, strategy, rationale, review requirement, and missing context.
- Ambiguous requests can return `SAFE_REDIRECT` so the system can route them to Codex first and Claude as a parallel cross-check.
- The chat surfaces keep the user-facing answer terse by default and expose the full answer-plus-trace payload only through `verbose` mode in the shell or web UI.
- Continuation requests such as "keep going" or "continue the implementation" answer with a direct resume path instead of the generic fallback, usually pointing at `/inspect`, `/next`, and the active Codex/Claude route.
- `analysis` surfaces the workspace root, the projects under that root, and a recommendation for which repo to continue first, so the initial workspace scan can start from the highest-leverage repo.
- `feedback` should record the request, result, and follow-up reaction, then classify the signal as positive, questionable, or over expectation so WOS can reinforce what worked and discourage what did not. The feedback layer also tags common agent errors such as too-verbose answers, wrong-agent routing, missing repo resolution, missing clarification, ignored preference, and generic fallback so the lightweight learning model can bias future routing and answer style.
- The web chat exposes redirect routes as launchable actions for ambiguous requests.
- `conscience status` and `conscience history` expose decision metrics, routing reasons, and recent conscience decisions in CLI, shell, and web.
- `conscience recommend` exposes a compact next action derived from the decision log so repeated work can move faster with less trace noise.
- `conscience extensions` exposes registered OCE extension layers, policy docs, and hook counts so collaborators can review what is pluggable without reading source code first, and the workspace config can list extension modules to load at startup.
- `next` exposes the immediate operational step from the current workspace state so the operator can move without opening the full overview.
- `bridge next` exposes the shortest decision surface, `bridge status` defaults to a short decision-oriented summary, `bridge status --detail` expands the full bridge inventory, and `bridge capabilities` exposes the command surface so Codex, Claude, or any other CLI agent can query WOS without opening the shell.
- `cycle` orchestrates long-running implementation plans with explicit health, stability, security, and quality checkpoints between iterations so WOS can supervise long cycles of delegated work, and `cycle run` can execute multiple checkpoints in one pass when the active cycle is already open or when a new cycle is started with a label and objective.
- `tests/test_smoke_queries.py` provides a regression battery of representative user queries and command surfaces, and each batch should run it alongside the normal validation suite.
- `workspace validate` includes the smoke regression battery by default, with `--skip-smoke-queries` available for narrower gates, and optional sources do not fail the gate when they are marked `required: false`.
- The web UI exposes a collapsible Conscience panel with decision, policy refs, and moral context.
- The canonical architecture stack is documented as ADEV -> OCE -> WOS, where ADEV is the principle layer, OCE is the Operational Conscience Engine model layer, and WOS is the implementation layer.
- The OCE layer is layered and pluggable: it can accept bounded context hooks, decision hooks, and policy documents through registered extension modules and a workspace config list.
- The operating model distinguishes predictive routing from generative synthesis so the product can use low-cost interpretation before high-value generation.
- The normative base is stored as versioned Markdown under `docs/architecture/policies/`.
- Delegate launch is blocked when the decision is `ASK_CLARIFICATION`, `REFUSE`, or `ESCALATE_TO_HUMAN`.
- Google Workspace destinations remain blocked until a real connector exists.
- The web UI exposes a chat-first workspace with engine activation indicators and recent local software and document activity.

### WSOS-021: Persist Operator Memory

As the operator, the system needs a persistent memory layer that captures preferences, lessons, outcomes, and conversation traces so repeated instructions do not have to be re-entered.

Acceptance criteria:
- Workspace memory is stored locally in SQLite.
- Preferences, reusable lessons, outcomes, and decision traces can be recorded and retrieved.
- Context packs and chat responses can consult prior memory entries.
- The memory store remains local-first and portable across workspace roots.

Initial implementation:
- `python -m workspace_os chat` can record conversation turns in the memory store.
- `python -m workspace_os memory status` reports memory store location and counts.
- `python -m workspace_os memory preference set|get` can seed and retrieve operator preferences.

### WSOS-011: Define Consulting Estimate Workflow

As the operator, the system needs repeatable estimation support for platform and modernization work.

Acceptance criteria:
- Estimate workflow captures scope, assumptions, exclusions, risks, and confidence.
- The workflow flags unrealistic assumptions.
- Output destination is Google Workspace, with source logic in Git.

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

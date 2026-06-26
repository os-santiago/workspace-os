# Workspace OS

Workspace OS is a local-first, cloud-compatible operating system for AI-assisted work.

It coordinates doctrine, evidence, execution, deliverables, and AI agents through a single governed workspace model.

## Quick Start

**New to Workspace OS?** See the [Getting Started Guide](docs/GETTING_STARTED.md) for a 5-minute quickstart.

```bash
# Install
pip install -e .

# Try the demo
./examples/quickstart_demo.sh
# or on Windows:
# .\examples\quickstart_demo.ps1

# Get started
workspace --help
```

## Purpose

The system exists to reduce scattered knowledge and make work reusable as context, guardrails, product assets, software, proposals, estimates, delivery artifacts, and non-interactive agent handshakes.

## Responsibility Model

- ADEV governs doctrine, rules, guardrails, and validation standards.
- scanales-kb learns from sanitized evidence, incidents, sessions, and decisions under the knowledge base root.
- homedir executes local automation, workstation setup, scripts, and agent tooling.
- Google Workspace produces final deliverables such as documents, slides, sheets, and external-facing assets.
- Codex, Claude, Antigravity, Gemini, and other agents receive hardened ADEV delegation prompts and operate under ADEV rules.
- The librarian layer prevents duplication, fragmentation, and knowledge loss.

The intended layout is `D:\git` for workspaces and `D:\kb` for knowledge bases. `adev` and `scanales-kb` live under `D:\kb`; `homedir` remains a workspace under `D:\git`.

## Design Principles

- Local first, cloud compatible.
- Everything suitable as code lives in Git.
- Final office deliverables live in Google Workspace when appropriate.
- Durable knowledge is generic, impersonal, sanitized, and searchable.
- Temporary artifacts are removed or consolidated before handoff.
- Agents must search and classify before adding content.
- Build incrementally; do not create a platform before the workflow proves it is needed.

## Initial Product Shape

The first product is a command-line workspace controller:

```text
workspace status
workspace search <query>
workspace context <topic>
workspace classify <path-or-text>
workspace capture --type <daily|incident|session|decision>
workspace promote --to <adev|scanales-kb|homedir|google>
workspace housekeeping
workspace validate
workspace bridge status --format json
```

## Repository Map

```text
docs/
|-- architecture/       # System boundaries and decisions
|-- product/            # Vision, product plan, roadmap, backlog, operating model
`-- runbooks/           # Operational procedures
```

## Current Status

Stage: terminal-first workspace shell foundation.

Runtime implementation exists for source registry loading, repository status, librarian search, non-destructive housekeeping reports, terminal conversation, a persistent workspace memory store for preferences, lessons, outcomes, decision traces, and batch telemetry, and an interactive shell for switching workspaces and running routine actions.

## First MVP Direction

The first MVP is an integrated local tool environment, not a broad knowledge base.

It should connect the core repositories, expose workspace status, support librarian search, and prepare governed context for agents before delegated work starts.

Progress toward the UI is tracked in `docs/product/roadmap.md`.
The canonical product plan lives in `docs/product/product-plan.md`.

## Key Features

### Agent Routing Validation

Workspace OS includes intelligent agent routing validation to ensure work is delegated to the most appropriate agent:

- **Pre-assignment validation** - Validates agent capabilities before task delegation
- **Task-aware routing** - Keyword matching to agent specializations (opencode, claude, antigravity)
- **Learning model integration** - Adapts routing based on historical feedback
- **Structured logging** - Audit trail for routing decisions

See [Agent Routing Validation](docs/features/agent-routing-validation.md) for details.

## Documentation

- [Getting Started Guide](docs/GETTING_STARTED.md) - 5-minute quickstart for new users
- [Product Vision](docs/product/vision.md) - Goals, outcomes, and success criteria
- [Roadmap](docs/product/roadmap.md) - Implementation stages and current progress
- [Architecture Overview](docs/architecture/overview.md) - System design and boundaries
- [Agent Routing Validation](docs/features/agent-routing-validation.md) - Intelligent agent routing
- [Examples](examples/README.md) - Usage patterns and demo scripts

## Local Usage

After installation, use the `workspace` command:

```bash
# Check repository status
workspace --config config/workspace.sources.local.json status

# Search across sources
workspace --config config/workspace.sources.local.json search "query"

# Build context for agent work
workspace --config config/workspace.sources.local.json context "topic"

# Classify content
workspace --config config/workspace.sources.local.json classify "text"

# Capture session notes
workspace --config config/workspace.sources.local.json capture --type session --title "Title" --text "Content" --write

# Validate workspace
workspace --config config/workspace.sources.local.json validate

# Launch web interface
workspace --config config/workspace.sources.local.json web
```

The example source registry uses relative paths and should be copied to `config/workspace.sources.local.json` before machine-specific customization. See the [Getting Started Guide](docs/GETTING_STARTED.md) for detailed setup instructions.

### Advanced Usage

For advanced usage and all available commands:

```bash
python -m pip install -e .
python -m workspace_os --config config/workspace.sources.example.json status
python -m workspace_os --config config/workspace.sources.example.json search ADEV --source-type doctrine
python -m workspace_os --config config/workspace.sources.example.json context "agent alignment"
python -m workspace_os --config config/workspace.sources.example.json chat "Remember to keep batches large but coherent."
python -m workspace_os --config config/workspace.sources.example.json inspect
python -m workspace_os --config config/workspace.sources.example.json handoff
python -m workspace_os --config config/workspace.sources.example.json memory status
python -m workspace_os --config config/workspace.sources.example.json shell
python -m workspace_os --config config/workspace.sources.example.json batch start --label sprint-1 --objective "keep batches large"
python -m workspace_os --config config/workspace.sources.example.json batch report
python -m workspace_os --config config/workspace.sources.example.json batch summary
python -m workspace_os --config config/workspace.sources.example.json process start --label iteration-1 --objective "10 batch window"
python -m workspace_os --config config/workspace.sources.example.json process summary
python -m workspace_os --config config/workspace.sources.example.json classify "Agents must validate scripts before release."
python -m workspace_os --config config/workspace.sources.example.json capture --type session --title "Agent checkpoint" --text "Sanitized session note."
python -m workspace_os --config config/workspace.sources.example.json promote --to adev --rule "Agents must validate scripts before release." --evidence "scanales-kb:captures/session/example.md"
python -m workspace_os --config config/workspace.sources.example.json web
python -m workspace_os --config config/workspace.sources.example.json validate
python -m workspace_os --config config/workspace.sources.example.json housekeeping
python -m workspace_os --config config/workspace.sources.example.json validate --skip-housekeeping
```

## Quality Assurance

### Mutation Testing

Mutation testing is used to verify test quality by introducing code mutations and ensuring tests detect them. The minimum mutation score threshold is 70%.

Run mutation tests:

```bash
# Linux/Mac
./scripts/run-mutation-tests.sh

# Windows
.\scripts\run-mutation-tests.ps1
```

See [docs/testing/mutation-testing.md](docs/testing/mutation-testing.md) for detailed information.

## Agent Routing

### Task-Aware Routing

Task-aware routing matches agents to work based on task characteristics, reducing wrong-agent errors. The system analyzes task descriptions for keywords and routes accordingly:

- **opencode**: refactoring, cleanup, mechanical changes (keywords: refactor, cleanup, rename, delete, format, lint, remove, move, mechanical)
- **claude**: analysis, planning, reasoning (keywords: analyze, review, plan, design, explain, cross-check, verify, evaluate, investigate)
- **antigravity**: architectural work, gap discovery (keywords: gap, architectural, leverage, discover, audit, assess, strategic, opportunity)

Routing priority: `learning_bias` (65% weight) > `task_hint` > `preferred_primary` > random fallback.

**Environment Variables:**
- `WOS_TASK_AWARE_ROUTING`: Enable/disable task-aware routing (default: `true`)
- `WOS_ROUTING_DEBUG`: Enable routing debug logging (default: `false`)

Example:
```bash
# Disable task-aware routing
export WOS_TASK_AWARE_ROUTING=false

# Enable routing debug logs
export WOS_ROUTING_DEBUG=true
```

## PowerShell Integration

To install a reusable PowerShell `wos` command for the current user, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-wos-command.ps1
```

That installer writes the `wos` function into the current user's all-hosts PowerShell profile and adds `scripts/` to the user PATH, so `wos` is available in future PowerShell and `cmd.exe` sessions on that machine.

After that, `wos` defaults to the shell and forwards any additional arguments to Workspace OS:

```powershell
wos
wos validate
wos web
```

The example source registry uses relative paths and should be copied to a local, ignored configuration file before machine-specific customization. Sources can also be marked `required: false` when they are useful references but not mandatory for a healthy local workspace.
In the default workspace setup, `D:\git` is the canonical workspace root and each configured project under that root is treated as a workspace-in-development candidate. The terminal surfaces use colored, prefixed sections so `Answer`, `Next`, `Workspace root`, `Projects under root`, and `Trace` are easy to scan at a glance.

Inside the shell, common commands include `/ws`, `/status`, `/search`, `/context`, `/analysis`, `/bridge`, `/profile`, `/habits`, `/batch`, `/cycle`, `/alias`, `/codex`, `/claude`, `/antigravity`, `/memory`, `/feedback`, and `/launches`.
/context latest renders the most recent compacted global context snapshot directly from memory, while `/context <topic>` still builds a governed context pack for a task. The chat CLI opens by showing that latest compacted context before prompting for input. The web chat now also shows the latest compacted context above the chat history, keeps it refreshed from the most recent reply, lets you expand or collapse that block when you need more detail, and remembers that preference across reloads. Chat replies default to the user-facing `Answer:` only; `/verbose` in the shell and `/verbose` or the verbose toggle in the web chat reveal the full `Answer:` plus `Trace:` detail layer for debugging. Continuation requests now answer with the fastest path to resume work, usually `/inspect` and `/next`, plus Codex and Claude routes when a fresh implementation increment is needed. Ambiguous status questions surface Codex as the primary route and Claude as a parallel fallback.
`/analysis` renders the workspace root, the projects under that root, and a recommendation for which repo to continue first. `/analysis --compact` trims the output down to the ranked repo list and recommendation. `/inspect` renders a condensed workspace overview with sources, memory, profile, habits, active process, active batch, and recent launches. `/inspect --compact` trims the overview down to summary lines. `/bridge next` is the shortest decision surface and returns only the next action plus the command to run; `/bridge next --detail` adds supporting context. `/bridge status` defaults to a short decision-oriented summary and `/bridge status --detail` expands to the full bridge inventory. `/bridge capabilities` lists the surfaces available to Codex, Claude, or any other CLI that needs to query WOS without opening the interactive shell. `/conscience extensions` exposes the registered OCE extension layers, their policy docs, and hook counts. All bridge modes support `--format json` for machine use. `/handoff` renders a concise copyable closing summary for the active workspace. Delegated Codex and Claude tasks always inherit an ADEV guardrail prompt before execution.
`/feedback add --request <text> --result <text> --feedback <text>` records a request/result feedback cycle and classifies it as positive, questionable, or over expectation. The feedback layer also tags common agent errors such as too-verbose answers, wrong-agent routing, missing repo resolution, missing clarification, ignored preference, and generic fallback. `/feedback history` lists recent signals and `/feedback status` shows summary counts plus the lightweight learning model summary.
The same feedback workflow is also available from CLI as `workspace feedback add|history|status`.
`/handoff --output <file>` writes the same closing summary to a Markdown file. `/batch handoff` and `/process handoff` export a scoped closing summary for the active batch or process, and both accept `--output <file>` plus `--compact` for a shorter report. `batch stop` and `process stop` also write a default `handoff.md` beside the local memory store and a `context-global.md` snapshot so each completed window leaves both a closing artifact and a compacted durable context. Exiting the shell also persists the latest `context-global.md` snapshot. The web pilot exposes the same closing summary through its API, plus the durable context snapshot, so the local panel can fetch both without entering the shell. The right rail now includes refresh and download actions for the context, handoff, questioning, agent utilization, and security panels.
The web right rail also includes a Questioning panel that surfaces Q&A volume, recent entries, and question-pattern hints from the memory store so learning signals stay visible while work continues.
When a batch is active, `chat` and the web reply include a compact batch summary alongside the normal response. `batch summary` reports the recent batch window, and `process summary` reports the stopwatch-style global process window from first start to last end. `process checkpoint` records milestones inside the active process window. Chat replies now keep the visible output terse by default and expose the reasoning/log layer only through verbose mode, so the user-facing result stays actionable while the trace remains available for supervision. The conscience engine now operates as OCE, the Operational Conscience Engine model, which applies versioned Markdown policies under `docs/architecture/policies/`, records an auditable moral trace, supports layered extension modules loaded from the workspace config, and can `SAFE_REDIRECT` ambiguous workspace requests to Codex first with Claude as the parallel cross-check. The web chat surfaces those redirect routes as launchable actions, and the right rail exposes a collapsible OCE panel with decision, policy refs, moral context, and a compact recommendation view. `conscience status`, `conscience history`, `conscience recommend`, and `conscience extensions` expose the decision log and extension registry so the engine can be reviewed from CLI, shell, and web. `next` exposes the immediate operational step from the current workspace state in CLI, shell, and web. Greetings, app-overview questions, and repetition complaints now return intent-aware guidance instead of a generic fallback, and ambiguous workspace-status questions route to Codex first with Claude as the parallel fallback when the workspace needs inventory or cross-checking.

The repository includes a smoke/regression query battery in `tests/test_smoke_queries.py`. It exercises representative user queries and command surfaces so each batch can compare visible output against expected operator behavior.
`workspace validate` runs that battery by default alongside source and housekeeping checks, and `--skip-smoke-queries` is available when a narrower gate is needed.
`/cycle` or `workspace cycle` orchestrates longer implementation runs with explicit health, stability, security, and quality checkpoints between iterations. `cycle run` executes a multi-iteration cycle against the active cycle or creates one when given `--label` and `--objective`, `cycle watch` keeps checkpointing until a target duration elapses, `cycle work` actively delegates implementation tasks to agents in parallel. Use `--continuous` mode for long-run productivity: it minimizes agent idle time by queueing new work as soon as any agent finishes instead of waiting for both to complete before starting the next iteration, keeping the agent pool busy throughout the window and reducing idle ratio. Continuous mode is recommended for extended work sessions (≥10 minutes) where maximizing throughput matters. `cycle next` recommends the next cycle action, `cycle checkpoint` captures the current gate state, `cycle report` summarizes the active or selected cycle, and `cycle status` shows the latest checkpoint summary. Each long run also writes a narrative execution journal under the workspace memory root so code metrics, functional metrics, checkpoint stories, wall-clock time, logical time, and idle ratio can be reviewed over time with `journal status|history|report`.

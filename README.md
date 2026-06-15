# Workspace OS

Workspace OS is a local-first, cloud-compatible operating system for AI-assisted work.

It coordinates doctrine, evidence, execution, deliverables, and AI agents through a single governed workspace model.

## Purpose

The system exists to reduce scattered knowledge and make work reusable as context, guardrails, product assets, software, proposals, estimates, and delivery artifacts.

## Responsibility Model

- ADEV governs doctrine, rules, guardrails, and validation standards.
- scanales-kb learns from sanitized evidence, incidents, sessions, and decisions.
- homedir executes local automation, workstation setup, scripts, and agent tooling.
- Google Workspace produces final deliverables such as documents, slides, sheets, and external-facing assets.
- Codex, Claude, Gemini, and other agents operate under ADEV rules.
- The librarian layer prevents duplication, fragmentation, and knowledge loss.

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
```

## Repository Map

```text
docs/
|-- architecture/       # System boundaries and decisions
|-- product/            # Vision, roadmap, backlog, operating model
`-- runbooks/           # Operational procedures
```

## Current Status

Stage: terminal-first workspace shell foundation.

Runtime implementation exists for source registry loading, repository status, librarian search, non-destructive housekeeping reports, terminal conversation, a persistent workspace memory store for preferences, lessons, outcomes, decision traces, and batch telemetry, and an interactive shell for switching workspaces and running routine actions.

## First MVP Direction

The first MVP is an integrated local tool environment, not a broad knowledge base.

It should connect the core repositories, expose workspace status, support librarian search, and prepare governed context for agents before delegated work starts.

Progress toward the UI is tracked in `docs/product/roadmap.md`.

## Local Usage

Run from the repository root:

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

The example source registry uses relative paths and should be copied to a local, ignored configuration file before machine-specific customization.
In the default workspace setup, `D:\git` is the canonical workspace root and each configured project under that root is treated as a workspace-in-development candidate. The terminal surfaces use colored, prefixed sections so `Answer`, `Next`, `Workspace root`, `Projects under root`, and `Trace` are easy to scan at a glance.

Inside the shell, common commands include `/ws`, `/status`, `/search`, `/context`, `/analysis`, `/profile`, `/habits`, `/batch`, `/alias`, `/codex`, `/claude`, `/memory`, and `/launches`.
/context latest renders the most recent compacted global context snapshot directly from memory, while `/context <topic>` still builds a governed context pack for a task. The chat CLI opens by showing that latest compacted context before prompting for input. The web chat now also shows the latest compacted context above the chat history, keeps it refreshed from the most recent reply, lets you expand or collapse that block when you need more detail, and remembers that preference across reloads. Chat replies default to the user-facing `Answer:` only; `/verbose` in the shell and `/verbose` or the verbose toggle in the web chat reveal the full `Answer:` plus `Trace:` detail layer for debugging. Continuation requests now answer with the fastest path to resume work, usually `/inspect` and `/next`, plus Codex and Claude routes when a fresh implementation increment is needed. Ambiguous status questions surface Codex as the primary route and Claude as a parallel fallback.
`/analysis` renders the workspace root, the projects under that root, and a recommendation for which repo to continue first. `/analysis --compact` trims the output down to the ranked repo list and recommendation. `/inspect` renders a condensed workspace overview with sources, memory, profile, habits, active process, active batch, and recent launches. `/inspect --compact` trims the overview down to summary lines. `/handoff` renders a concise copyable closing summary for the active workspace.
`/handoff --output <file>` writes the same closing summary to a Markdown file. `/batch handoff` and `/process handoff` export a scoped closing summary for the active batch or process, and both accept `--output <file>` plus `--compact` for a shorter report. `batch stop` and `process stop` also write a default `handoff.md` beside the local memory store and a `context-global.md` snapshot so each completed window leaves both a closing artifact and a compacted durable context. Exiting the shell also persists the latest `context-global.md` snapshot. The web pilot exposes the same closing summary through its API, plus the durable context snapshot, so the local panel can fetch both without entering the shell. The right rail now includes refresh and download actions for the context and handoff panels.
When a batch is active, `chat` and the web reply include a compact batch summary alongside the normal response. `batch summary` reports the recent batch window, and `process summary` reports the stopwatch-style global process window from first start to last end. `process checkpoint` records milestones inside the active process window. Chat replies now keep the visible output terse by default and expose the reasoning/log layer only through verbose mode, so the user-facing result stays actionable while the trace remains available for supervision. The conscience engine now operates as OCE, the Operational Conscience Engine model, which applies versioned Markdown policies under `docs/architecture/policies/`, records an auditable moral trace, and can `SAFE_REDIRECT` ambiguous workspace requests to Codex first with Claude as the parallel cross-check. The web chat surfaces those redirect routes as launchable actions, and the right rail exposes a collapsible OCE panel with decision, policy refs, moral context, and a compact recommendation view. `conscience status`, `conscience history`, and `conscience recommend` expose the decision log as metrics and a single next action so the engine can be reviewed from CLI, shell, and web. `next` exposes the immediate operational step from the current workspace state in CLI, shell, and web. Greetings, app-overview questions, and repetition complaints now return intent-aware guidance instead of a generic fallback, and ambiguous workspace-status questions route to Codex first with Claude as the parallel fallback when the workspace needs inventory or cross-checking.

The repository includes a smoke/regression query battery in `tests/test_smoke_queries.py`. It exercises representative user queries and command surfaces so each batch can compare visible output against expected operator behavior.
`workspace validate` runs that battery by default alongside source and housekeeping checks, and `--skip-smoke-queries` is available when a narrower gate is needed.

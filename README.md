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
python -m workspace_os --config config/workspace.sources.example.json housekeeping
python -m workspace_os --config config/workspace.sources.example.json validate --skip-housekeeping
```

The example source registry uses relative paths and should be copied to a local, ignored configuration file before machine-specific customization.

Inside the shell, common commands include `/ws`, `/status`, `/search`, `/context`, `/profile`, `/habits`, `/batch`, `/alias`, `/codex`, `/claude`, `/memory`, and `/launches`.
`/inspect` renders a condensed workspace overview with sources, memory, profile, habits, active process, active batch, and recent launches. `/handoff` renders a concise copyable closing summary for the active workspace.
The web pilot exposes the same closing summary through its API so the local panel can fetch a handoff without entering the shell, and the right rail shows a refreshable handoff panel.
When a batch is active, `chat` and the web reply include a compact batch summary alongside the normal response. `batch summary` reports the recent batch window, and `process summary` reports the stopwatch-style global process window from first start to last end. `process checkpoint` records milestones inside the active process window.

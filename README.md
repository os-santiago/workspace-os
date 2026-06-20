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

Stage: first local CLI foundation.

Runtime implementation exists for source registry loading, repository status, librarian search, and non-destructive housekeeping reports.

## First MVP Direction

The first MVP is an integrated local tool environment, not a broad knowledge base.

It should connect the core repositories, expose workspace status, support librarian search, and prepare governed context for agents before delegated work starts.

Progress toward the UI is tracked in `docs/product/roadmap.md`.

## Documentation

- [Getting Started Guide](docs/GETTING_STARTED.md) - 5-minute quickstart for new users
- [Product Vision](docs/product/vision.md) - Goals, outcomes, and success criteria
- [Roadmap](docs/product/roadmap.md) - Implementation stages and current progress
- [Architecture Overview](docs/architecture/overview.md) - System design and boundaries
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

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
workspace capture --type <daily|incident|session|decision>
workspace classify <path-or-text>
workspace promote --to <adev|scanales-kb|homedir|google>
workspace housekeeping
workspace validate
```

## Repository Map

```text
docs/
├── architecture/       # System boundaries and decisions
├── product/            # Vision, roadmap, backlog, operating model
└── runbooks/           # Operational procedures
```

## Current Status

Stage: product discovery and MVP planning.

No runtime implementation exists yet.

## First MVP Direction

The first MVP is an integrated local tool environment, not a broad knowledge base.

It should connect the core repositories, expose workspace status, support librarian search, and prepare governed context for agents before delegated work starts.

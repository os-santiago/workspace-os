# Product Vision

## Problem

Work is distributed across repositories, local folders, Google Workspace, and multiple AI tools. Knowledge becomes difficult to find, reuse, validate, or convert into durable capability.

## Vision

Workspace OS provides one governed workspace model for AI-assisted work. It connects local repositories under `D:\git`, knowledge bases under `D:\kb`, cloud deliverables, and agent tools while preserving clear ownership and rules.

The product follows the canonical stack:

```text
ADEV -> OCE -> WOS
principle -> model -> implementation
```

Workspace OS should act as the bridge between operator requests and execution. Requests pass first through OCE, the Operational Conscience Engine model, which interprets intent, priorities, risk, timing, decision boundaries, and extension layers. They then pass through a learning engine grounded in ADEV and scanales-kb before Workspace OS routes work to repositories, Google Workspace, or agents. In practice, ADEV and scanales-kb live under `D:\kb`, while workspace repos such as `homedir` and `workspace-os` stay under `D:\git`.

Workspace OS also needs a non-interactive bridge so Codex, Claude, and other CLI-based agents can query the current workspace state, available surfaces, and recommended continuation path without entering the interactive shell.

The intended AI mix is predictive-first and generative-last:

- predictive and discriminative logic should handle intent detection, routing, confidence, ranking, and repeated decisions cheaply;
- generative logic should handle synthesis, explanation, prompt drafting, and high-value final output.

This lets Workspace OS optimize the request path before generation and reserve generative cost for the moments where it creates the most value.

The collaboration model should stay pluggable: collaborators can contribute bounded OCE extension layers for policy, context, and decision refinement without forking the engine.

The long-term ambition is to let one operator execute work at organizational scale by delegating toil, preserving experience, and leading multiple product or delivery streams through checkpoints instead of constant manual execution.

## Outcomes

- Find relevant prior work before starting new work.
- Capture evidence without exposing sensitive details.
- Promote reusable lessons into doctrine.
- Convert work into reusable assets, proposals, estimates, software, and operational playbooks.
- Let AI agents operate consistently across local and cloud environments.
- Reduce repeated work, duplicated notes, and forgotten decisions.
- Produce consulting estimates, proposals, presentations, and software with higher speed and quality.
- Let agents apply accumulated doctrine and daily learning by default.
- Convert raw requests into conscious, learned, governed actions before execution.
- Optimize the request path with predictive routing before invoking generative work.

## Primary Work Domains

- Platform engineering.
- Cloud-native modernization.
- Container platform adoption.
- Application migration.
- SDLC acceleration.
- Software supply chain security.
- Process automation at scale.

## Non-Goals

- Replace ADEV as the doctrine source of truth.
- Replace Google Workspace for final office deliverables.
- Store secrets or sensitive raw outputs.
- Train a model directly from private work in the MVP.
- Execute arbitrary commands from chat.
- Treat unverified external chat links as durable product definitions without capturing the sanitized definition in Git.
- Treat generation as the final value layer, not the default control plane.

## Users

- Primary operator managing personal and professional work.
- AI agents operating under repository rules.
- Future collaborators who need structured handoff and traceability.

## MVP Success Criteria

- Agents use ADEV and accumulated learning before delegated work starts.
- Similar knowledge is found before new content is created.
- Daily learning is captured and made reusable.
- Known mistakes are not repeated.
- Generated software avoids obvious security and quality regressions.
- Estimates are grounded in explicit assumptions and do not invent unrealistic effort.

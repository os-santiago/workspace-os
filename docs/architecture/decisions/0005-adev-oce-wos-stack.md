# ADR 0005: ADEV -> OCE -> WOS Stack

## Status

Accepted

## Context

Workspace OS needs a product architecture that separates principle, model, and implementation.

The system should not blur:

- the governing doctrine that defines how work should be done;
- the decision engine that interprets requests and decides what should happen next;
- the implementation surface that exposes CLI, shell, web, memory, routing, and agent execution.

The product also needs a practical way to combine predictive and generative AI:

- predictive / discriminative logic for low-cost interpretation, routing, ranking, and control;
- generative logic for synthesis, explanation, prompt expansion, and final output.

## Decision

Workspace OS will use the following stack:

```text
ADEV  ->  OCE  ->  WOS
principle   model    implementation
```

- **ADEV** is the principle layer.
- **OCE** is the Operational Conscience Engine model layer.
- **WOS** is the Workspace OS implementation layer.

This structure is canonical for the product and should be used in docs, code comments, roadmaps, and launch decisions.

## Layer Definitions

### 1. ADEV: Principle Layer

ADEV is the upstream operating doctrine.

It defines:

- how work should be planned and delivered;
- what counts as good judgment;
- what must be protected;
- how to validate quality;
- how to capture and reuse learning;
- how to avoid institutionalizing guesswork.

In the product stack, ADEV is the rule source, not the execution engine.

### 2. OCE: Operational Conscience Engine Model Layer

OCE is the decision model that evaluates an incoming request before WOS answers, delegates, or launches work.

OCE combines:

- context and intent analysis;
- risk and reversibility evaluation;
- policy retrieval;
- routing and approval logic;
- decision trace generation;
- recommendation of the next best action.

OCE should be biased toward:

- predictive / discriminative logic for classification, confidence scoring, routing, ranking, anomaly detection, and next-best-action selection;
- generative logic only when the response needs synthesis, explanation, prompt drafting, or a final user-facing artifact.

In practice, OCE decides:

- whether the request is allowed;
- whether it needs clarification;
- whether it should redirect to Codex or Claude;
- whether it should stay limited or be escalated;
- what the compact recommendation should be.

### 3. WOS: Workspace OS Implementation Layer

WOS is the implementation that makes OCE useful in the operator's daily workflow.

It provides:

- CLI commands;
- terminal shell;
- local web UI;
- persistent memory;
- context compaction;
- handoff generation;
- agent launch and delegation;
- repository-aware workspace inventory;
- recommendation surfaces for quick action.

WOS must stay local-first and workspace-centric.

## Flow

```text
Operator request
  -> WOS captures the request
  -> OCE interprets context, risk, and intent
  -> OCE consults ADEV and versioned policy documents
  -> OCE chooses a decision and a route
  -> WOS either answers directly, asks for clarification, or prepares Codex / Claude execution
  -> WOS records the trace, recommendation, and outcome
  -> WOS compacts the context for later reuse
```

## Internal OCE Flow

```text
Request
  -> Context & intent analysis
  -> Predictive classification and ranking
  -> Normative reasoning
  -> Risk and reversibility evaluation
  -> Decision engine
  -> Response strategy selection
  -> Generative synthesis only when needed
  -> Audit and learning
```

## Layers and Techniques

### Predictive / Discriminative Layer

Use for:

- request intent classification;
- workspace vs. general domain detection;
- risk scoring;
- missing-context detection;
- routing choice between Codex and Claude;
- next-action recommendation;
- confidence and anomaly scoring;
- repeated-pattern detection.

Preferred techniques:

- deterministic rules;
- lightweight classifiers;
- ranking heuristics;
- schema-based scoring;
- cached memory lookups;
- frequency analysis over past decisions.

### Generative Layer

Use for:

- concise explanations;
- agent briefs;
- summaries and handoffs;
- context compaction;
- user-facing response drafting;
- synthesis from multiple sources;
- high-value final output where format matters more than raw classification.

Preferred techniques:

- large language models;
- prompt templates;
- constrained synthesis;
- output shaping with traces and policies.

### Memory and Evaluation Layer

Use for:

- profile storage;
- decision logs;
- batch and process telemetry;
- context snapshots;
- learning from outcomes;
- recommendation biasing.

Preferred techniques:

- SQLite;
- markdown snapshots;
- rule-based aggregation;
- append-only traces for auditability.

## Technology Choices

The current implementation direction is:

- **Language:** Python
- **Runtime:** local CLI + local web server
- **Persistence:** SQLite
- **Context format:** Markdown snapshots
- **UI surfaces:** terminal shell and browser UI
- **Agent execution:** allowlisted subprocess launches for Codex and Claude
- **Policy storage:** versioned Markdown under `docs/architecture/policies/`
- **Search / retrieval:** repository and text search over local sources

These choices are practical because they:

- keep the system portable;
- keep the memory layer inspectable;
- reduce deployment friction;
- support deterministic control flow;
- allow local-first development before any larger platform work.

## Feasibility

This design is technically feasible with the current codebase because:

- the request bridge already exists;
- the conscience engine already produces structured decisions;
- the memory store already persists profile, decisions, batches, process windows, and context snapshots;
- the CLI and shell already expose operational commands;
- the web UI already exposes the same workflow surfaces;
- Codex and Claude are already treated as allowlisted execution targets.

The main engineering challenge is not raw capability. It is keeping the routing deterministic enough to be trustworthy while still allowing generative assistance when it adds value.

## Requirements

### Functional

- Distinguish principle, model, and implementation layers.
- Prefer predictive routing before generative synthesis.
- Use generative output only when the task needs it.
- Keep decision traces auditable.
- Record compact recommendations and context history.
- Support workspace-aware routing to Codex and Claude.
- Keep context compaction and handoff generation automatic.

### Non-Functional

- Low latency for routine routing.
- Low token cost for repetitive work.
- Local-first operation.
- Deterministic behavior for core decisions.
- Reproducible traces.
- Sanitized durable memory.
- Vendor-neutral implementation language in canonical docs.

## Customer Fit

The target customer fit is strongest for operators who:

- work across multiple Git repositories;
- need to delegate repetitively to AI tools;
- want consistent judgment and routing;
- need memory and traceability across sessions;
- want less toil and fewer repeated instructions;
- need fast inventory, summarization, and handoff generation.

The strongest fit is not a generic chatbot market. The strongest fit is:

- AI-assisted engineering operations;
- solo operators managing multiple workstreams;
- small teams that need a governed local control plane;
- delivery environments that value repeatability, auditability, and context preservation.

## Projection

The product can evolve in three practical phases:

### Phase 1: Operational Control Plane

- Local workspace inventory.
- Memory persistence.
- Conscience routing.
- Codex / Claude delegation.
- Handoffs and context snapshots.

### Phase 2: Predictive Optimization Layer

- Better routing prediction.
- Better missing-context detection.
- Better recommendation quality.
- Better reuse of operator preferences and outcomes.
- Lower toil through stronger automation.

### Phase 3: Generative Value Layer

- Higher-quality synthesis.
- Better multi-agent coordination.
- Stronger cross-checking.
- More useful final outputs with less operator intervention.

The projection is that the product becomes more valuable as the predictive layer gets better, because the generative layer is only invoked when it can increase impact instead of repeating work.

## Consequences

- Architecture discussions now have a canonical hierarchy.
- Product language becomes clearer and more marketable.
- Predictive and generative components can be assigned deliberately instead of blended loosely.
- OCE becomes the model name for the conscience engine.
- WOS becomes the implementation that exposes that model to operators.

## Non-Goals

- Claiming predictive models alone are enough.
- Replacing generative models everywhere.
- Treating WOS as a general-purpose public AI platform.
- Duplicating ADEV doctrine inside implementation code.
- Promising product scope beyond what the current stack can deliver.

# Product Plan

## Purpose

Workspace OS (WOS) is a local-first workspace operating system for AI-assisted work. Its job is to reduce orchestration overhead, align multiple agents, preserve context, and turn repeated work into durable capability.

The product succeeds when the operator can move from intent to action with fewer instructions, fewer retries, lower defect rates, and a consistent experience regardless of which agent executes the work.

## Product Thesis

WOS should combine three layers:

1. Predictive and discriminative logic for routing, ranking, confidence scoring, and next-best-action selection.
2. Operational conscience for governance, hardening, and safe redirection.
3. Generative synthesis only when it creates clear value in summaries, handoffs, prompts, or final artifacts.

The design goal is not to generate everything. The design goal is to choose the cheapest correct action first, then reserve generation for the moments where it multiplies value.

## Core Competencies

WOS must be strong in the following product competencies:

- workspace discovery and repo resolution;
- agent orchestration and preference-aware routing;
- consistent user experience across shell, CLI, web, and bridge surfaces;
- context compaction and durable memory;
- parallel execution and cross-checking;
- guarded delegation under ADEV and OCE;
- feedback-driven learning and mastery;
- long-running cycle orchestration;
- traceability, handoff, and recovery;
- extension-friendly architecture for collaborators.

## Product Gaps To Close

### 1. Multiple Context Overhead

WOS should reduce the cost of switching between repositories, tasks, and agents by:

- resolving the requested repo automatically when the user names it;
- ranking the active workspaces by freshness and relevance;
- compacting the current state into a single recommendation;
- exposing detail only when requested.

### 2. Agent Fragmentation

WOS should hide agent differences behind one consistent contract:

- one workspace state model;
- one governed context format;
- one bridge surface for external agents;
- one visible answer format by default;
- one trace format available on demand.

The operator should not need to relearn the interface every time the agent changes.

### 3. Parallelization and Cross-Checks

WOS should use one agent for execution and another for cross-check when the task benefits from speed and validation.

The default pattern should be:

- primary execution agent for the first pass;
- cross-check agent for divergence detection, quality review, or sensitive work;
- explicit alternation during long runs so the system learns from different execution paths.

### 4. Operational Conscience and Hardening

OCE must remain always on and always active.

Its responsibilities are:

- prevent malicious agentic behavior;
- block unsafe delegation patterns;
- allow defensive work with limits;
- attach policy references to decisions;
- keep the reasoning auditable;
- support layered extensions without weakening the core guardrails.

### 5. Learning From Outcomes

WOS should learn from outcomes, not only from prompts.

It should reward:

- lower defect counts;
- correct repo resolution;
- correct agent choice;
- fewer clarifications over time;
- positive feedback and over-expectation feedback;
- repeated patterns of high-impact behavior.

It should suppress:

- generic fallbacks;
- repeated negative outcomes;
- verbose but low-value answers;
- wrong-agent routing;
- missing repo resolution;
- ignored preferences;
- repeated clarification loops.

### 6. Long-Run Delivery

WOS should support work that lasts from minutes to hours and requires repeated checkpoints.

The cycle model should enforce:

- health checks;
- stability checks;
- security checks;
- quality checks;
- checkpoint history;
- early stop on failure when appropriate;
- alternating execution/cross-check roles where useful.

## Architecture Layers

```text
User intent
  -> OCE interpretation and hardening
  -> workspace and repo resolution
  -> learning and context compaction
  -> agent selection and routing
  -> cycle orchestration for long runs
  -> execution / cross-check
  -> feedback capture and mastery update
  -> durable handoff and context snapshot
```

### Layer 1: Request Intake

The first layer accepts the raw request and identifies:

- the requested repo or workspace;
- the task type;
- the minimum useful answer;
- missing context;
- the required safety level.

### Layer 2: OCE

OCE is the operational conscience model.

It must:

- classify intent and risk;
- apply always-on hardening;
- decide whether to allow, limit, clarify, refuse, or redirect;
- choose whether the request should run sequentially or in parallel;
- surface the decision with traceability.

### Layer 3: Workspace Memory

The memory layer stores:

- outcomes;
- preferences;
- decision traces;
- feedback signals;
- cycle checkpoints;
- context snapshots;
- learning summaries.

This layer exists to reduce repetition and preserve behavior across sessions.

### Layer 4: Agent Router

The router selects the right tool for the job.

It should support:

- configurable primary agent preference;
- cross-check agent preference;
- role switching during long runs;
- one shared command contract;
- non-interactive bridge access for external agents.

### Layer 5: Cycle Orchestrator

The cycle engine manages long-running work.

It should:

- run multiple iterations;
- enforce health, stability, security, and quality checkpoints;
- alternate execution and review roles when useful;
- stop early when a gate fails;
- produce a compact report suitable for handoff.

### Layer 6: User Surfaces

The user experience should remain stable across:

- shell;
- CLI;
- web;
- bridge;
- handoff artifacts.

The same question should lead to the same decision regardless of surface.

## UX Contract

WOS should behave as follows:

- show the answer first;
- hide trace/debug details unless verbose mode is enabled;
- recommend one next action by default;
- name the repo explicitly when it has been resolved;
- expose parallel execution only when it improves speed or quality;
- keep the visible style compact and decisive;
- preserve a richer trace for supervision, testing, and debugging.

## Learning Model

WOS should use a lightweight learning loop before any heavier model work.

Signals to learn from:

- request/result/feedback cycles;
- task outcomes;
- defect iterations;
- launch success or failure;
- user overrides;
- repeated clarification patterns;
- positive versus negative feedback;
- cross-check disagreements.

Desired learning outputs:

- routing bias;
- detail bias;
- preferred agent;
- preferred execution mode;
- context gap detection;
- next-action recommendation;
- stop/continue criteria for long runs.

The system should bias toward patterns that produce fewer defects and more durable results.

## Safety And Security

WOS should treat hardening as a default product capability, not an optional mode.

Requirements:

- malicious agentic behavior is always checked;
- defensive use is allowed with limits;
- secret handling remains out of durable knowledge;
- agent prompts inherit the ADEV contract;
- mutation paths remain explicit and governed;
- context snapshots stay sanitized.

## Customer Fit

Primary users:

- a single operator managing multiple repositories and streams of work;
- collaborators who need consistent governed handoffs;
- future teams that want one local orchestration layer across agents.

What the product should do for them:

- save time on orchestration;
- reduce rework;
- reduce the number of times the same context must be repeated;
- improve quality through cross-checks;
- keep work moving during long runs;
- make the next step obvious.

## Market Projection

WOS is most credible as a product when it is positioned as a workspace orchestration layer, not as a generic chatbot.

Likely expansion path:

1. single operator, local-first workspace control;
2. multi-agent orchestration with stable preferences and cross-checks;
3. extension ecosystem for bounded contribution;
4. collaborative adoption across adjacent workspaces and teams;
5. reusable operational standard for agent-assisted delivery.

The product value grows when it becomes the lowest-friction way to keep work moving with less context loss and better decision quality.

## Success Metrics

The product is healthy when it improves:

- time to next action;
- number of instructions per task;
- wrong-agent rate;
- reroute frequency;
- defect iterations per cycle;
- context reuse rate;
- handoff quality;
- positive feedback rate;
- long-run completion rate;
- operator confidence in the next action.

## Delivery Phases

### Phase 1: Stable Workspace Orchestration

- shared workspace state;
- repo resolution;
- answer-first UX;
- bridge surfaces;
- hardened delegation;
- durable memory.

### Phase 2: Learning and Mastery

- feedback-driven adaptation;
- error pattern suppression;
- positive pattern reinforcement;
- preference-aware routing;
- better context selection.

### Phase 3: Long-Run Execution

- cycle orchestration;
- repeated health and quality checks;
- execution/cross-check alternation;
- stop criteria and recovery.

### Phase 4: Extension Ecosystem

- bounded OCE extensions;
- collaborative improvements;
- policy and context hooks;
- plug-in oriented adoption.

### Phase 5: Durable Operating Standard

- consistent UX across agents;
- repeatable handoffs;
- reusable workspace intelligence;
- adoption beyond the first operator.


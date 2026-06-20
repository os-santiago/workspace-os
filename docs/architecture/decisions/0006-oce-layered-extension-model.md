# 0006: OCE Layered Extension Model

## Status
Accepted

## Context

Workspace OS now uses the Operational Conscience Engine (OCE) as the model layer between ADEV and the Workspace OS implementation surface.
The model must stay adaptable without turning the core into a monolith:

- new policy layers should be addable without rewriting the engine;
- collaborators should be able to contribute bounded policy documents and hooks;
- the engine must stay auditable and deterministic by default;
- hardening must remain always on;
- extension points must not create arbitrary execution surfaces.

The product also needs a clear maintenance story:

- OCE policy and behavior should be understandable from the repository alone;
- the engine should support incremental growth in context, decision, and reporting layers;
- the runtime should expose a stable inventory of extension layers to humans and external CLI agents.

## Decision

OCE is implemented as a layered engine with a constrained extension registry.

The engine is divided into the following conceptual layers:

1. **Context layer** - derives intent, domain, reversibility, missing context, and threat mode.
2. **Normative layer** - resolves versioned policy documents and computes applicable norms.
3. **Decision layer** - selects the operational outcome and routing strategy.
4. **Reporting layer** - renders compact or detailed views for CLI, shell, and bridge surfaces.
5. **Extension layer** - contributes bounded policy documents, context hooks, and decision hooks.

Extensions are expected to register themselves through explicit code, not through implicit free-form execution.
Supported extension capabilities are intentionally narrow:

- add policy documents;
- patch context fields with validated keys;
- patch decision fields with validated keys;
- report the extension inventory.

The runtime loads configured extension modules from the workspace configuration or from local Python modules, then registers them into the OCE registry.
The registry is read-only from the point of view of the request flow: extensions can influence evaluation, but they do not bypass the hardening model.

## Consequences

- OCE remains pluggable without losing traceability.
- Collaborators can add a new layer without editing the whole engine.
- Policy and behavior changes stay visible through `conscience extensions` and bridge surfaces.
- The design supports future additions such as scoring layers, domain-specific policy packs, or reporting adapters.
- The system still requires tests for every new extension behavior to avoid silent drift.

## Notes

- ADEV remains the principle layer.
- WOS remains the implementation surface.
- OCE remains the decision model and extension host.
- Malicious agentic hardening stays implicit and always on.

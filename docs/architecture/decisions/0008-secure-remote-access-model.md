# ADR 0008: Secure Remote Access Model

## Status

Accepted

## Context

Workspace OS may eventually be supervised or triggered from remote devices, but remote convenience must not become arbitrary command execution.

The remote-access design must protect:

- credentials and secrets;
- private repositories and workspace state;
- approval boundaries;
- auditability of every action;
- the ability to stop remote control quickly if behavior becomes unsafe.

The system already prefers local-first operation and allowlisted execution. Remote access must extend those principles rather than weaken them.

## Decision

Workspace OS will treat remote access as a controlled supervision channel, not a general shell endpoint.

The secure remote access model is:

1. **Private network first** - remote control should prefer VPN or equivalent private access before any broader exposure.
2. **Declarative commands only** - remote requests must map to allowlisted intents and workflows, not free-form shell commands.
3. **Explicit approval for mutation** - actions that change repositories, run elevated operations, or touch secrets require a human approval step.
4. **Kill switch required** - remote access must have an immediate shutdown path that disables launch and mutation surfaces.
5. **Audit trail required** - every remote request, decision, approval, execution, and failure must be recorded in sanitized form.
6. **No arbitrary execution surface** - the remote interface may launch only curated operations already known to WOS.

## Remote Interaction Contract

The remote channel may support:

- requesting status;
- asking for workspace summaries;
- launching allowlisted workflows;
- reviewing decision traces;
- approving or rejecting a proposed action;
- viewing sanitized audit records.

The remote channel must not support:

- arbitrary command execution;
- direct secret access;
- unaudited repository mutation;
- bypassing policy decisions;
- hidden background operations.

## Safety Model

Remote control is allowed only if the following remain true:

- requests are classifiable into known intents;
- the command map is allowlisted and reviewable;
- approvals are visible and durable;
- logs are sanitized before storage;
- the operator can disable remote actions without deleting history.

If any of those conditions fail, the remote feature remains blocked.

## Consequences

- Workspace OS can grow into remote supervision without becoming an uncontrolled remote shell.
- The product can expose a mobile-friendly or networked control surface later with clear governance.
- Audit and kill-switch behavior become first-class requirements instead of afterthoughts.
- The remote story remains compatible with the local-first architecture and the OCE request bridge.

## Non-Goals

- Free-form SSH-like command execution from chat.
- Public internet exposure without a private access boundary.
- Unbounded automation that bypasses approval.
- Storing raw secrets in audit logs.

## Notes

- This decision defines the design boundary requested by WSOS-008.
- Implementation should remain blocked until an allowlisted remote command surface and audit pipeline exist.

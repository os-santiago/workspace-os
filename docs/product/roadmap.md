# Roadmap

## Progress Map

Status legend:

```text
[DONE]  implemented or documented enough to use
[NEXT]  next implementation batch
[TODO]  planned but not started
[LATER] later stage after the MVP proves value
```

Current path to the first UI:

```text
GOAL
  Workspace OS UI based on the homedir experience
  |
  +-- [DONE] Stage 0 - Product definition
  |      +-- Repository responsibilities
  |      +-- Vision, roadmap, backlog, operating model
  |      +-- Local-first architecture boundaries
  |      +-- Request bridge concept: consciousness engine plus learning engine
  |
  +-- [DONE] Stage 1 - Local CLI foundation
  |      +-- workspace status
  |      +-- workspace search
  |      +-- workspace context
  |      +-- workspace classify
  |      +-- workspace housekeeping
  |      +-- workspace validate
  |
  +-- [DONE] Stage 2 - Learning loop
  |      +-- capture session, incident, decision, and daily notes
  |      +-- sanitize before write
  |      +-- promote reusable rules to ADEV
  |      +-- link evidence back to scanales-kb
  |
  +-- [DONE] Stage 3 - Direct web pilot
  |      +-- expose read-only workspace state
  |      +-- expose context and search endpoints
  |      +-- expose governed capture and promote workflows
  |      +-- keep shell execution out of the API
  |
  +-- [NEXT] Stage 4 - Homedir-based UI workflow depth
  |      +-- reuse homedir visual and navigation patterns
  |      +-- show status, search, context, classify, validate
  |      +-- show batch progress and active roadmap
  |      +-- keep mutation flows behind explicit approval
  |      +-- shell-first conversation and workspace switching
  |
  +-- [LATER] Stage 5 - Delivery workflows
  |      +-- consulting estimates
  |      +-- proposals
  |      +-- presentations
  |      +-- software delivery plans
  |
  +-- [LATER] Stage 6 - Secure remote operation
         +-- phone supervision
         +-- allowlisted task launch
         +-- approval workflow
         +-- sanitized audit trail
```

Current batch sequence:

```text
Batch 01 [DONE] Local CLI foundation
  status | search | housekeeping

Batch 02 [DONE] Agent context pack
  context | sanitized search output

Batch 03 [DONE] Classify and validate
  classify | validate

Batch 04 [DONE] Capture and promotion loop
  capture | sanitize | promote | evidence links

Batch 05 [DONE] Direct web pilot
  local web app | allowlisted endpoints | homedir-inspired shell

Batch 06 [NEXT] UI workflow depth
  capture flow | promotion flow | roadmap progress | agent context flow | terminal shell

Batch 07 [TODO] Pilot hardening
  approvals | write workflows | local auth boundary | mobile access design

Batch 08 [TODO] Request bridge
  operational conscience | ADEV and scanales-kb learning engine | governed routing
```

## Stage 0: Product Definition

Goal: define the operating model, roadmap, repository responsibilities, and first backlog.

Exit criteria:
- Repository created.
- Product vision documented.
- Roadmap documented.
- Initial backlog documented.
- Architecture boundaries documented.

## Stage 1: Integrated Local Workspace Foundation

Goal: create an integrated local environment that connects the core repositories and gives agents governed access to status, search, and librarian context.

Capabilities:
- Show status across ADEV, scanales-kb, homedir, and this repository.
- Search local doctrine and evidence.
- Classify whether new content belongs in doctrine, evidence, execution, or deliverables.
- Run housekeeping checks for temporary artifacts.
- Prepare minimal context packs for agents before delegated work begins.

Exit criteria:
- `workspace status` works locally.
- `workspace search` can search configured repositories.
- `workspace housekeeping` reports temporary or untracked artifacts.
- Agent context includes relevant ADEV rules and scanales-kb evidence.
- Validation is documented and repeatable.

## Stage 1A: Request Bridge

Goal: make Workspace OS the bridge between raw operator requests and governed execution.

Capabilities:
- Receive a request as input.
- Run the request through OCE, the Operational Conscience Engine model, which extracts intent, outcome, priority, risk, and checkpoint needs.
- Run the interpreted request through a learning engine that applies ADEV and searches scanales-kb.
- Route the result to software work in Git, deliverables in Google Workspace, or an agent brief.
- Refuse or pause requests that conflict with privacy, safety, or repository rules.

Exit criteria:
- The ADEV -> OCE -> WOS stack is captured in sanitized local documentation.
- Learning-engine inputs are explicitly ADEV and scanales-kb.
- Every delegated task includes intent, risk, relevant learning, destination, and approval requirements.
- Google Workspace routing is blocked until a real connector exists.

## Stage 2: Agent Alignment and Learning Loop

Goal: make assistants behave consistently with accumulated doctrine, decisions, style, and lessons.

Capabilities:
- Capture daily notes, incidents, sessions, and decisions into scanales-kb.
- Promote reusable rules into ADEV.
- Link evidence to doctrine.
- Enforce sanitization before write.
- Create task-specific agent briefs from doctrine and evidence.
- Capture mistakes and corrections after each delegated task.

Exit criteria:
- New entries use templates.
- Content is sanitized by default.
- Similar content is searched before creating new files.
- Promotion creates clear diffs.
- Delegated tasks include a traceable context source list.
- Repeated mistakes become rules, tests, checklists, or evidence.

## Stage 3: Consulting Delivery Workflows

Goal: support high-value outputs: estimates, proposals, presentations, and software delivery plans.

Capabilities:
- Generate estimate drafts from reusable assumptions and delivery patterns.
- Produce proposal outlines and presentation structures.
- Link deliverables to source evidence without copying sensitive content into Git.
- Flag unrealistic assumptions or missing inputs.

Exit criteria:
- Estimate drafts list assumptions, exclusions, risks, and confidence.
- Proposal drafts map to known capabilities and evidence.
- Presentation outlines can be exported to Google Workspace.

## Stage 4: Connectors

Goal: connect external sources without losing ownership boundaries.

Capabilities:
- Read Google Workspace metadata and links.
- Register deliverables without copying sensitive content into Git.
- Index selected local folders and repositories.
- Keep connector configuration as code where appropriate.

Exit criteria:
- Google Workspace connector is read-only by default.
- Local source registry exists.
- Indexed content has source, owner, type, and freshness metadata.

## Stage 5: Agent Router

Goal: let Codex, Claude, Gemini, and future agents operate through the same governed workspace.

Capabilities:
- Route tasks to the right agent or CLI.
- Inject minimal relevant context.
- Require approvals for risky actions.
- Log agent activity as sanitized evidence.

Exit criteria:
- Agent runs are traceable.
- Command allowlist exists.
- Approvals are required for mutation, deployment, and elevated execution.

## Stage 6: Secure Remote Access

Goal: interact with the workspace from a phone or remote device safely.

Capabilities:
- Secure channel through VPN or equivalent private access.
- Chat interface to request allowed actions.
- Explicit approval workflow.
- Audit trail for all remote commands.

Exit criteria:
- No arbitrary shell execution from chat.
- All remote actions use allowlisted commands.
- Logs are sanitized and searchable.

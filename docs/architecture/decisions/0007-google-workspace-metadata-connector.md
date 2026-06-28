# ADR 0007: Google Workspace Metadata Connector

## Status

Accepted

## Context

Workspace OS needs a way to reference Google Workspace deliverables without turning Git into a mirror of private office content.

The product boundary is clear:

- Git stores code, doctrine, product docs, and sanitized evidence.
- Google Workspace stores final office deliverables when appropriate.
- Workspace OS should be able to register and reason about deliverables without copying sensitive document contents into the repository.

The connector also needs to respect the privacy model:

- minimize exposure of personal, customer, or company-specific data;
- redact private identifiers before durable storage or export;
- prefer generic, role-based language over identifying details;
- require escalation when third-party data handling or authorization is needed.

## Decision

Workspace OS will treat Google Workspace as a metadata-first connector surface.

The connector design is:

1. **Read-only by default** - the connector may inspect metadata and links, but it must not write to Google Workspace unless an explicit approval flow exists.
2. **Metadata over content** - the connector records document identity, title, owner, timestamps, sharing state, and links. It does not persist full document contents in Git.
3. **Approval for writes** - any future write action, such as creating or updating a document, requires explicit human approval and a dedicated mutation path.
4. **Privacy-preserving references** - durable records should store stable references and sanitized summaries rather than raw private content.
5. **Separation of responsibilities** - Workspace OS can register deliverables and surface links, while Google Workspace remains the system of record for final office artifacts.

## Connector Contract

The initial connector contract should support:

- listing deliverables by metadata;
- resolving a document link to a stable external reference;
- storing source, owner, type, freshness, and link metadata;
- attaching sanitized notes or classifications to the deliverable record;
- refusing any operation that would copy sensitive content into Git by default.

The connector should not assume that every deliverable is safe to index in full text.

## Validation Model

The connector passes the privacy model if it can answer these questions positively:

- Does it avoid storing raw document contents by default?
- Does it preserve source boundaries between Git and Google Workspace?
- Does it require explicit approval for write actions?
- Does it keep personally identifying or customer-specific data minimized?
- Does it support generic references that are still useful for workspace coordination?

If any answer is no, the connector is too permissive for the current architecture.

## Consequences

- Workspace OS can reference external deliverables without losing provenance.
- The product can support consulting, proposal, and presentation workflows without copying private content into Git.
- The privacy boundary stays simple enough to audit.
- Future write support can be added later without changing the read-only default.
- Documentation and implementation can evolve independently while keeping the connector contract stable.

## Non-Goals

- Mirroring Google Drive content into Git.
- Automatic write access to Google Workspace.
- Indexing full private document contents by default.
- Building a generic third-party document platform.

## Notes

- This design supports the roadmap stage for connectors and the backlog item for the Google Workspace metadata connector.
- The implementation should stay narrow until an approval-safe mutation path exists.

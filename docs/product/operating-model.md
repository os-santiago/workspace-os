# Operating Model

## Source of Truth

ADEV is the upstream source of truth for operating doctrine.

Workspace OS consumes ADEV rules and implements workflows around them. It does not replace ADEV.

## Knowledge Flow

```text
Work happens
  -> evidence is captured in scanales-kb
  -> reusable lessons are promoted to ADEV
  -> execution improvements are implemented in homedir
  -> final deliverables are produced in Google Workspace
  -> Workspace OS indexes and orchestrates the flow
```

## Librarian Rule

Before adding durable content:

1. Search related local sections and files.
2. Classify the content.
3. Update the canonical location when possible.
4. Create new files only for distinct content.
5. Add cross-references when content spans repositories.
6. Remove temporary artifacts after use.

## Content Classification

| Content Type | Destination |
| --- | --- |
| Doctrine, rules, guardrails | ADEV |
| Evidence, incidents, sessions, decisions | scanales-kb |
| Scripts, local automation, agent tooling | homedir |
| Product roadmap and architecture for this system | Workspace OS |
| Final docs, decks, sheets, proposals | Google Workspace |
| Temporary exploration | Delete or consolidate |

## Safety Rules

- No secrets in Git.
- No personal or company-specific data in durable records.
- No arbitrary remote shell execution.
- Mutating actions require explicit approval.
- Temporary files must not survive completion unless promoted.


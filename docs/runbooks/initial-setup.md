# Initial Setup Runbook

## Goal

Prepare the repository for product discovery and later implementation.

## Steps

1. Clone the repository.
2. Read `README.md`.
3. Read `docs/product/vision.md`.
4. Read `docs/product/roadmap.md`.
5. Read `docs/product/backlog.md`.
6. Read `docs/product/operating-model.md`.
7. Review architecture decisions.
8. Copy `config/workspace.sources.example.json` to a local ignored config if your workspace root or memory path differs from the default and set `workspace_root`, `memory_db`, `WORKSPACE_OS_GIT_ROOT`, or `WORKSPACE_OS_MEMORY_DB`.

## Validation

```bash
git status --short
```

Expected result:

```text

```

No uncommitted changes should be present after setup.


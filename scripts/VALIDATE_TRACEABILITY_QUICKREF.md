# Validate Traceability - Quick Reference

## Commands

```bash
# TRACE COMMANDS
# --------------
# Trace issue → PRs
python scripts/validate_traceability.py trace issue --issue-number <NUM> [--output json|markdown|text]

# Trace PR → issues
python scripts/validate_traceability.py trace pr --pr-number <NUM> [--output json|markdown|text]

# Trace work item → issue → PR
python scripts/validate_traceability.py trace work-item --cycle-id <ID> --work-item <NUM> [--output json|text]


# VALIDATE COMMANDS
# -----------------
# Validate cycle traceability
python scripts/validate_traceability.py validate cycle --cycle-id <ID> [--mode soft|hard|batch] [--output json|csv|markdown|text]


# FIX COMMANDS
# ------------
# Auto-fix PR closing keywords
python scripts/validate_traceability.py fix pr --pr-number <NUM> --issue-number <NUM>
```

## Common Options

```bash
--workspace-root PATH   # Workspace root (default: current directory)
--timeout SECONDS       # API timeout (default: 10.0)
--verbose, -v           # Enable debug logging
--help, -h              # Show help
```

## Output Formats

| Format   | Use Case                          | File Extension |
|----------|-----------------------------------|----------------|
| json     | Machine parsing, API integration  | .json          |
| csv      | Spreadsheet import, analysis      | .csv           |
| markdown | Documentation, reports            | .md            |
| text     | Terminal output, logs             | .txt           |

## Validation Modes

| Mode  | Behavior                              | Exit Code            |
|-------|---------------------------------------|----------------------|
| soft  | Log warnings, don't block             | Always 0             |
| hard  | Block on failures                     | 1 if < 100% compliant|
| batch | Defer validation to checkpoint        | Always 0             |

## Quick Examples

```bash
# Check if issue #123 has proper PR links
python scripts/validate_traceability.py trace issue --issue-number 123

# Generate cycle 2 compliance report
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output markdown > report.md

# Fix missing closing keyword
python scripts/validate_traceability.py fix pr --pr-number 456 --issue-number 123

# CI/CD gate (exits 1 if not 100% compliant)
python scripts/validate_traceability.py validate cycle --cycle-id 2 --mode hard

# Export to CSV for spreadsheet analysis
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output csv > cycle-2.csv
```

## Report Metrics

**TraceabilityReport includes:**
- `compliance_rate`: % of work items with valid PR links
- `total_work_items`: Total work items in cycle
- `prs_created`: Number of PRs created
- `prs_with_valid_links`: PRs with proper closing keywords
- `prs_missing_keywords`: PRs without closing keywords
- `prs_not_created`: Work items without PRs
- `quality_gates_passed`: Number of gates passed
- `quality_gates_failed`: Number of gates failed
- `avg_work_to_pr_seconds`: Average time from work start to PR creation
- `validation_failures`: Detailed list of failures

## Closing Keywords

Recognized keywords (case-insensitive):
- close, closes, closed
- fix, fixes, fixed
- resolve, resolves, resolved

Format: `Closes #123` or `Fixes: #456` or `Resolves #789.`

## Exit Codes

- `0`: Success (or SOFT/BATCH mode)
- `1`: Failure (validation error, API error, or HARD mode < 100% compliance)

## Prerequisites

- Python 3.11+
- GitHub CLI (`gh`) authenticated
- Git repository with remote
- SQLite database at `.claude/memory.db` (for cycle/work-item commands)

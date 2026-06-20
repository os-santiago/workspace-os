# Traceability Validation Script

Production-ready CLI tool for validating PR-to-issue traceability, quality gates, and cycle compliance in Workspace OS.

## Features

- **Trace Issues to PRs**: Find all PRs linked to a specific issue
- **Trace PRs to Issues**: Find all issues referenced in a PR
- **Trace Work Items**: Follow work items through the complete cycle
- **Validate Cycles**: Generate comprehensive compliance reports for entire cycles
- **Auto-fix PRs**: Automatically add missing closing keywords to PRs
- **Multiple Output Formats**: JSON, CSV, Markdown, and plain text
- **Validation Modes**: SOFT (warnings only), HARD (blocking), and BATCH (deferred)
- **Production-ready**: Full error handling, type hints, logging, and docstrings

## Installation

The script is located in `scripts/validate_traceability.py` and requires:

- Python 3.11+
- GitHub CLI (`gh`) installed and authenticated
- Git repository with remote configured
- SQLite database at `.claude/memory.db` (for work item and cycle validation)

## Usage

### Basic Commands

```bash
# Show help
python scripts/validate_traceability.py --help

# Enable verbose logging
python scripts/validate_traceability.py --verbose <command>

# Specify workspace root
python scripts/validate_traceability.py --workspace-root /path/to/repo <command>
```

### Trace Commands

#### Trace Issue to PRs

Find all PRs that reference a specific issue:

```bash
# Text output (default)
python scripts/validate_traceability.py trace issue --issue-number 123

# JSON output
python scripts/validate_traceability.py trace issue --issue-number 123 --output json

# Markdown output
python scripts/validate_traceability.py trace issue --issue-number 123 --output markdown
```

**Output includes:**
- Issue title, state, and closed status
- All linked PRs with closing keyword verification
- Summary of PRs with/without proper keywords

#### Trace PR to Issues

Find all issues referenced in a specific PR:

```bash
# Text output (default)
python scripts/validate_traceability.py trace pr --pr-number 456

# JSON output
python scripts/validate_traceability.py trace pr --pr-number 456 --output json

# Markdown output
python scripts/validate_traceability.py trace pr --pr-number 456 --output markdown
```

**Output includes:**
- PR title, state, URL, and merge status
- All linked issues with closing keywords
- Summary of issues with proper linking

#### Trace Work Item

Follow a work item through issue → PR → merge:

```bash
# Text output (default)
python scripts/validate_traceability.py trace work-item \
  --cycle-id 2 \
  --work-item 5

# JSON output with custom database path
python scripts/validate_traceability.py trace work-item \
  --cycle-id 2 \
  --work-item 5 \
  --memory-db /path/to/memory.db \
  --output json
```

**Output includes:**
- Work item task ID and status
- Linked issue information
- PR validation results
- Trace completion status

### Validate Commands

#### Validate Cycle

Generate comprehensive traceability compliance report for an entire cycle:

```bash
# Markdown report (default)
python scripts/validate_traceability.py validate cycle --cycle-id 2

# JSON report
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output json

# CSV report
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output csv

# Text report
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output text
```

**Validation modes:**

```bash
# SOFT mode: Log warnings, don't block (default)
python scripts/validate_traceability.py validate cycle --cycle-id 2 --mode soft

# HARD mode: Exit with error code if compliance < 100%
python scripts/validate_traceability.py validate cycle --cycle-id 2 --mode hard

# BATCH mode: Defer validation to checkpoint
python scripts/validate_traceability.py validate cycle --cycle-id 2 --mode batch
```

**Report includes:**
- Compliance rate (%)
- Total work items
- PRs created/with valid links/missing keywords/not created
- Quality gates passed/failed
- Average work-to-PR time
- Detailed validation failures
- Gate failure details

### Fix Commands

#### Auto-fix PR

Automatically add missing closing keywords to PRs:

```bash
# Add "Closes #123" to PR #456
python scripts/validate_traceability.py fix pr \
  --pr-number 456 \
  --issue-number 123
```

**Behavior:**
- Fetches current PR body
- Checks if closing keyword already exists
- Appends `Closes #<issue>` if missing
- Updates PR via GitHub API
- Reports success/failure

## Output Formats

### JSON Format

Machine-readable format for integration with other tools:

```bash
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output json
```

```json
{
  "cycle_id": 2,
  "validation_timestamp": "2026-06-19T12:00:00+00:00",
  "compliance_rate": 85.7,
  "total_work_items": 7,
  "prs_created": 6,
  "prs_with_valid_links": 6,
  "prs_missing_keywords": 0,
  "prs_not_created": 1,
  "validation_failures": [...]
}
```

### CSV Format

Spreadsheet-compatible format:

```bash
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output csv
```

Includes:
- Summary metrics
- Validation failures table

### Markdown Format

Human-readable report with tables:

```bash
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output markdown
```

Includes:
- Summary tables
- Quality gates
- Performance metrics
- Detailed failure list

### Text Format

Plain text report for terminal output:

```bash
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output text
```

## Validation Modes

### SOFT Mode (Default)

- Log warnings for validation failures
- Don't block completion
- Exit code 0 even if compliance < 100%
- Suitable for development and monitoring

```bash
python scripts/validate_traceability.py validate cycle --cycle-id 2 --mode soft
```

### HARD Mode

- Block completion on failures
- Exit code 1 if compliance < 100%
- Suitable for CI/CD gates and production

```bash
python scripts/validate_traceability.py validate cycle --cycle-id 2 --mode hard
```

### BATCH Mode

- Defer validation to checkpoint
- Collect all failures before reporting
- Suitable for batch processing

```bash
python scripts/validate_traceability.py validate cycle --cycle-id 2 --mode batch
```

## Examples

### Complete Workflow Example

```bash
# 1. Trace an issue to see what PRs reference it
python scripts/validate_traceability.py trace issue --issue-number 31

# 2. Trace a specific PR to see what issues it closes
python scripts/validate_traceability.py trace pr --pr-number 42

# 3. Fix PR if missing closing keyword
python scripts/validate_traceability.py fix pr --pr-number 42 --issue-number 31

# 4. Trace a work item through the cycle
python scripts/validate_traceability.py trace work-item --cycle-id 2 --work-item 5

# 5. Validate entire cycle compliance
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output markdown

# 6. Generate CSV report for analysis
python scripts/validate_traceability.py validate cycle --cycle-id 2 --output csv > cycle-2-report.csv

# 7. CI/CD gate with hard validation
python scripts/validate_traceability.py validate cycle --cycle-id 2 --mode hard || exit 1
```

### Integration with CI/CD

```yaml
# GitHub Actions example
- name: Validate Traceability
  run: |
    python scripts/validate_traceability.py validate cycle \
      --cycle-id ${{ github.event.inputs.cycle_id }} \
      --mode hard \
      --output json > traceability-report.json
  
- name: Upload Report
  uses: actions/upload-artifact@v3
  with:
    name: traceability-report
    path: traceability-report.json
```

### Scripting Examples

```bash
# Validate multiple cycles
for cycle_id in 1 2 3; do
  echo "Validating cycle $cycle_id"
  python scripts/validate_traceability.py validate cycle \
    --cycle-id $cycle_id \
    --output markdown > "reports/cycle-$cycle_id.md"
done

# Auto-fix all PRs missing keywords for an issue
python scripts/validate_traceability.py trace issue --issue-number 123 --output json | \
  jq -r '.linked_prs[] | select(.has_closing_keyword == false) | .number' | \
  while read pr_number; do
    python scripts/validate_traceability.py fix pr --pr-number $pr_number --issue-number 123
  done
```

## Architecture

### Class Structure

```
TraceabilityValidator
├── trace_issue() → IssueTraceResult
├── trace_pr() → PRTraceResult
├── trace_work_item() → dict
├── validate_pr_links_to_issue() → PRValidationResult
├── validate_quality_gates() → list[QualityGateResult]
├── validate_cycle_traceability() → TraceabilityReport
└── auto_fix_pr_body() → bool

OutputFormatter
├── format_report() → str
├── format_issue_trace() → str
└── format_pr_trace() → str
```

### Data Classes

- `PRValidationResult`: PR-to-issue link validation
- `QualityGateResult`: Quality gate validation
- `TraceabilityReport`: Cycle compliance report
- `IssueTraceResult`: Issue-to-PRs trace
- `PRTraceResult`: PR-to-issues trace

### Enumerations

- `ValidationMode`: SOFT, HARD, BATCH
- `PRState`: OPEN, CLOSED, MERGED, DRAFT, NOT_CREATED
- `OutputFormat`: JSON, CSV, MARKDOWN, TEXT

## Error Handling

The script includes comprehensive error handling:

- **GitHub API Failures**: Caught and logged with helpful messages
- **Rate Limiting**: Detected and reported
- **Database Errors**: Caught with transaction safety
- **Timeouts**: Configurable with `--timeout` flag
- **Missing Resources**: Clear error messages for missing issues/PRs/work items
- **Invalid Inputs**: Validated with argparse

## Logging

Structured logging to stderr:

```bash
# Default INFO level
python scripts/validate_traceability.py <command>

# Verbose DEBUG level
python scripts/validate_traceability.py --verbose <command>
```

Log format:
```
2026-06-19 12:00:00,000 - __main__ - INFO - Validating cycle 2 traceability
```

## Exit Codes

- `0`: Success
- `1`: Failure (validation errors, API errors, etc.)

In HARD mode:
- `0`: 100% compliance
- `1`: < 100% compliance or other errors

## GitHub API Usage

The script uses GitHub CLI (`gh`) for API access:

- **Issue queries**: `gh issue view`
- **PR queries**: `gh pr list`, `gh pr view`
- **Timeline queries**: `gh api repos/.../issues/.../timeline`
- **PR updates**: `gh pr edit`

Rate limiting is detected and reported.

## Database Schema

Expects SQLite database at `.claude/memory.db` with:

**agent_queue table:**
```sql
CREATE TABLE agent_queue (
  task_id TEXT PRIMARY KEY,
  metadata TEXT,  -- JSON with issue_number, work_item_number, agent_type, role
  status TEXT,
  started_at TEXT,
  completed_at TEXT
);
```

**cycle_checkpoints table:**
```sql
CREATE TABLE cycle_checkpoints (
  cycle_id INTEGER,
  health_ok BOOLEAN,
  stability_ok BOOLEAN,
  security_ok BOOLEAN,
  quality_ok BOOLEAN,
  created_at TEXT
);
```

## Type Hints

Full type hints throughout for IDE support and type checking:

```python
def validate_pr_links_to_issue(
    self,
    issue_number: int,
    work_item_number: int,
    agent_type: str,
    role: str = "primary"
) -> PRValidationResult:
    ...
```

## Testing

```bash
# Unit test individual functions
python -m pytest tests/test_validate_traceability.py

# Integration test with real repository
python scripts/validate_traceability.py trace issue --issue-number 1

# Verify error handling
python scripts/validate_traceability.py trace issue --issue-number 999999
```

## Troubleshooting

### GitHub CLI not authenticated

```bash
gh auth login
```

### Database not found

```bash
# Specify custom path
python scripts/validate_traceability.py validate cycle \
  --cycle-id 2 \
  --memory-db /path/to/memory.db
```

### Timeout errors

```bash
# Increase timeout
python scripts/validate_traceability.py --timeout 30 <command>
```

## License

MIT - Part of Workspace OS project

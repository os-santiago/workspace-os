# Traceability Metrics Collector

## Overview

The `traceability_metrics.py` script provides comprehensive metrics collection and analysis for the Workspace OS traceability system. It collects PR lifecycle metrics, calculates latencies, generates compliance reports, and creates interactive dashboards.

## Features

- **PR Lifecycle Metrics**: Track work item → PR and PR → merge latencies
- **Compliance Tracking**: Calculate PR creation rates, keyword compliance, and merge rates
- **Quality Gate Analysis**: Aggregate checkpoint data to track quality gate pass/fail rates
- **Multiple Export Formats**: JSON, Markdown, HTML, and CSV
- **Interactive Dashboards**: Generate HTML dashboards with visual metrics
- **Checkpoint Integration**: Pull data directly from cycle checkpoints

## Installation

The script requires Python 3.10+ and uses only standard library modules plus:
- `sqlite3` (built-in)
- `subprocess` (built-in)
- GitHub CLI (`gh`) must be installed and authenticated

## Usage

### Command Line Interface

The script provides four main commands:

#### 1. Collect PR Metrics

Collect raw PR metrics for a cycle and export to JSON or CSV:

```bash
python scripts/traceability_metrics.py collect \
    --cycle-id 2 \
    --output metrics.json \
    --format json
```

**Options:**
- `--cycle-id`: Cycle ID to collect metrics for (required)
- `--output`: Output file path (optional, defaults to stdout)
- `--format`: Output format (`json` or `csv`, default: `json`)
- `--workspace`: Workspace root directory (default: current directory)
- `--memory-db`: Path to memory.db (default: `.wos/memory.db`)

#### 2. Generate Compliance Report

Generate a comprehensive compliance report:

```bash
python scripts/traceability_metrics.py report \
    --cycle-id 2 \
    --format markdown \
    --output report.md
```

**Options:**
- `--cycle-id`: Cycle ID to report on (required)
- `--format`: Report format (`json`, `markdown`, or `html`, default: `markdown`)
- `--output`: Output file path (optional, defaults to stdout)
- `--workspace`: Workspace root directory
- `--memory-db`: Path to memory.db

**Example Output (Markdown):**

```markdown
# Traceability Metrics Report

**Cycle:** Cycle 2
**Compliance Rate:** 95.5%
**Merge Rate:** 88.2%

## Compliance Metrics

| Metric | Value |
|--------|-------|
| Total Work Items | 22 |
| PRs Created | 21 |
| PRs Merged | 19 |
...
```

#### 3. Create Interactive Dashboard

Generate an HTML dashboard with visual metrics:

```bash
python scripts/traceability_metrics.py dashboard \
    --cycle-id 2 \
    --output dashboard.html
```

The dashboard includes:
- Key metric cards with color-coded values
- Quality gate progress bars
- Latency comparison tables
- Responsive design for viewing on any device

#### 4. Calculate Latencies

Display latency metrics for a cycle:

```bash
python scripts/traceability_metrics.py latency \
    --cycle-id 2
```

**Example Output:**

```
Latency Metrics for Cycle 2:
  Work → PR:
    Average: 2.3m
    Median:  1.8m
    P95:     4.5m
  PR → Merge:
    Average: 15.2m
    Median:  12.1m
    P95:     28.7m
  Total Samples: 21
```

## Python API

The script can also be used as a library:

```python
from pathlib import Path
from traceability_metrics import MetricsCollector

# Initialize collector
collector = MetricsCollector(
    workspace_root=Path("/path/to/repo"),
    memory_db_path=Path("/path/to/memory.db")
)

# Collect PR metrics
pr_metrics = collector.collect_pr_metrics(cycle_id=2)

# Calculate latencies
latency_metrics = collector.calculate_latencies(pr_metrics)

# Calculate compliance
compliance_metrics = collector.calculate_compliance_metrics(
    cycle_id=2,
    pr_metrics=pr_metrics
)

# Calculate quality gates
quality_metrics = collector.calculate_quality_gate_metrics(cycle_id=2)

# Generate report
report = collector.generate_compliance_report(
    cycle_id=2,
    format="markdown"
)

# Create dashboard
collector.create_dashboard(
    cycle_id=2,
    output_path=Path("dashboard.html")
)

# Export metrics
collector.export_metrics(
    metrics=pr_metrics,
    output_path=Path("metrics.csv"),
    format="csv"
)
```

## Metrics Collected

### PR Metrics

For each PR in a cycle:
- PR number and issue number
- Work item ID
- Created, merged, and closed timestamps
- Work start and completion timestamps
- Work → PR latency (seconds)
- PR → merge latency (seconds)
- Has closing keyword (boolean)
- Is merged (boolean)
- PR state
- Agent type (claude/opencode)

### Latency Metrics

Aggregated statistics:
- Average, median, and P95 for work → PR latency
- Average, median, and P95 for PR → merge latency
- Total sample count

### Compliance Metrics

- Total work items
- PRs created
- PRs merged
- PRs with closing keywords
- PRs without closing keywords
- PRs not created
- Compliance rate (%)
- Merge rate (%)
- Keyword compliance rate (%)

### Quality Gate Metrics

From checkpoint data:
- Total checkpoints
- Health gate pass count and rate
- Stability gate pass count and rate
- Security gate pass count and rate
- Quality gate pass count and rate
- Overall pass count and rate

## Database Schema

The script expects the following tables in `memory.db`:

### `agent_queue` Table

```sql
CREATE TABLE agent_queue (
    task_id TEXT PRIMARY KEY,
    status TEXT,
    metadata TEXT,  -- JSON with issue_number, agent_type, etc.
    started_at TEXT,  -- ISO datetime
    completed_at TEXT  -- ISO datetime
);
```

### `cycles` Table

```sql
CREATE TABLE cycles (
    id INTEGER PRIMARY KEY,
    label TEXT,
    objective TEXT,
    started_at TEXT,
    ended_at TEXT
);
```

### `cycle_checkpoints` Table

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

## Error Handling

The script includes comprehensive error handling:

- **Missing database**: Raises `FileNotFoundError` with clear message
- **Missing tables**: Returns empty metrics rather than failing
- **GitHub API errors**: Logs warnings but continues processing
- **Invalid data**: Skips invalid records and logs warnings
- **Timeout protection**: All subprocess calls have configurable timeouts

## Performance

- Database queries use indexes on `task_id` and `cycle_id`
- GitHub API calls are rate-limited by `gh` CLI
- Large cycles (>100 work items) may take several minutes due to API calls
- Consider using `--output` to avoid flooding terminal with JSON

## Troubleshooting

### "Memory database not found"

Ensure the database path is correct:
```bash
python scripts/traceability_metrics.py report \
    --cycle-id 2 \
    --memory-db /path/to/.wos/memory.db
```

### "No PR metrics available"

Check that:
1. The cycle ID exists in the database
2. Work items have `issue_number` in their metadata
3. PRs exist for those issues in GitHub

### GitHub API rate limiting

The script uses `gh` CLI which respects GitHub rate limits. If you hit limits:
- Wait for the rate limit to reset (usually 1 hour)
- Use a GitHub token with higher limits
- Run the script less frequently

## Contributing

When modifying the script:
1. Maintain full type hints on all functions
2. Add docstrings for new methods
3. Handle errors gracefully (don't crash on bad data)
4. Add tests for new metric types
5. Update this README with new features

## License

Part of Workspace OS project.

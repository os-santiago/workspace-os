# Code Coverage Tracking and Enforcement

## Overview

The Workspace OS now includes automated code coverage tracking and enforcement integrated into the checkpoint system. This ensures that all code changes maintain or improve test coverage.

## Features

### 1. Coverage Tracking with pytest-cov

- Measures branch and statement coverage
- Generates HTML, XML, and terminal reports
- Configurable minimum thresholds
- Automatic enforcement during checkpoints

### 2. Security Scanning with Bandit

- Static analysis security testing (SAST)
- Detects common security issues
- Configurable severity thresholds
- Integrated into quality gates

## Configuration

### pyproject.toml

Coverage is configured in `pyproject.toml`:

```toml
[tool.coverage.run]
branch = true
source = ["src/workspace_os"]
omit = [
    "*/tests/*",
    "*/__pycache__/*",
]

[tool.coverage.report]
precision = 2
show_missing = true
fail_under = 80.0
```

### config/quality.json

Quality gates can be customized in `config/quality.json`:

```json
{
  "coverage": {
    "minimum_total": 80.0,
    "minimum_new_code": 80.0,
    "fail_under": 80.0,
    "enabled": true
  },
  "security": {
    "bandit_enabled": true,
    "severity_threshold": "medium"
  },
  "quality_gates": {
    "enforce_coverage": true,
    "enforce_security": true,
    "block_on_failure": true
  }
}
```

## Usage

### Running Coverage Manually

```bash
# Run tests with coverage
pytest --cov=src/workspace_os --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html
```

### Running Security Scan Manually

```bash
# Run bandit security scanner
bandit -r src/ -f json -ll

# Or with standard output
bandit -r src/
```

### Automated Quality Checks

Coverage and security checks run automatically during cycle checkpoints:

```bash
# Run a cycle with quality gates
workspace cycle run --iterations 1

# Skip coverage during high-utilization (fast-path mode)
# Coverage is automatically skipped when agent utilization > 50%
```

## Quality Gates

The checkpoint system enforces the following quality gates:

1. **Compilation**: All Python files must compile without errors
2. **Test Suite**: All tests must pass
3. **Coverage**: Code coverage must meet the minimum threshold (default: 80%)
4. **Security**: No medium or high severity security issues

### Gate Behavior

- **Pass**: All checks pass, checkpoint is recorded
- **Fail**: Quality gate violation, details are logged
- **Skip**: Check skipped (e.g., during fast-path mode or if tool not installed)

## Reports

### Coverage Reports

Coverage reports are generated in multiple formats:

- **Terminal**: Summary displayed after test run
- **HTML**: Interactive report in `htmlcov/` directory
- **XML**: Machine-readable `coverage.xml` for CI/CD integration

### Security Reports

Bandit outputs JSON format that can be integrated with dashboards:

```json
{
  "results": [
    {
      "issue_severity": "MEDIUM",
      "issue_confidence": "HIGH",
      "issue_text": "SQL injection detected",
      "line_number": 42,
      "filename": "src/workspace_os/database.py"
    }
  ]
}
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Run quality checks
  run: |
    pip install -e ".[dev]"
    pytest --cov=src/workspace_os --cov-report=xml --cov-fail-under=80
    bandit -r src/ -f json -o bandit-report.json -ll

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Best Practices

1. **Write Tests First**: Maintain coverage by writing tests for new features
2. **Review Coverage Reports**: Identify untested code paths
3. **Fix Security Issues**: Address bandit findings before merging
4. **Configure Thresholds**: Adjust thresholds based on project maturity
5. **Monitor Trends**: Track coverage over time in dashboards

## Troubleshooting

### Coverage Check Fails

```
Coverage check failed. Coverage: 75.50% (minimum: 80.0%)
```

**Solution**: Add tests to increase coverage above the threshold.

### Bandit Finds Issues

```
Bandit found 3 security issues (severity >= medium)
```

**Solution**: Review the bandit report and fix security vulnerabilities.

### Tools Not Installed

```
Skipped coverage check: No module named 'pytest_cov'
```

**Solution**: Install development dependencies:

```bash
pip install -e ".[dev]"
```

## Metrics and Dashboards

Coverage metrics are tracked in cycle checkpoints and can be visualized:

- **Coverage Trend**: Track coverage percentage over time
- **Security Issues**: Monitor security findings by severity
- **Quality Pass Rate**: Percentage of checkpoints passing all gates

Query checkpoint history:

```python
from workspace_os.memory import WorkspaceMemoryStore

store = WorkspaceMemoryStore("memory.sqlite3")
report = store.cycle_report()
print(f"Quality pass rate: {report['quality_pass_rate']:.1%}")
```

## Environment Variables

- `WOS_CHECKPOINT_FAST_PATH_THRESHOLD`: Utilization threshold for skipping coverage (default: 0.5)
- `WOS_ENABLE_AUTO_HEALING`: Enable auto-healing on quality failures (default: false)

## Related Documentation

- [Checkpoint System](../checkpoints.md)
- [Quality Gates](../quality-gates.md)
- [CI/CD Integration](../ci-cd.md)

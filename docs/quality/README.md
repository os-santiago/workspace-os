# Quality Assurance

## Overview

Workspace OS includes comprehensive quality assurance tools integrated into the checkpoint system:

- **Code Coverage**: Automated tracking with pytest-cov
- **Security Scanning**: Static analysis with Bandit
- **Quality Gates**: Enforce standards on every checkpoint
- **Automated Reporting**: HTML, XML, and dashboard integration

## Quick Start

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

This installs:
- `pytest-cov` - Coverage measurement
- `bandit` - Security scanner

### Run Quality Checks

```bash
# Run tests with coverage
pytest --cov=src/workspace_os --cov-report=html

# Run security scan
bandit -r src/

# Run full checkpoint (includes all quality checks)
workspace cycle run --iterations 1
```

## Quality Gates

Every checkpoint validates:

1. **Compilation**: Python syntax and imports
2. **Tests**: All tests pass
3. **Coverage**: ≥80% code coverage (configurable)
4. **Security**: No medium/high severity issues

## Configuration

Edit `config/quality.json`:

```json
{
  "coverage": {
    "fail_under": 80.0
  },
  "security": {
    "severity_threshold": "medium"
  }
}
```

## Documentation

- [Coverage Tracking](./coverage.md) - Detailed coverage guide
- [Security Scanning](./security.md) - Bandit integration
- [Quality Gates](./gates.md) - Checkpoint enforcement

## Metrics

Track quality metrics via checkpoint history:

```python
from workspace_os.memory import WorkspaceMemoryStore

store = WorkspaceMemoryStore("memory.sqlite3")
report = store.cycle_report()

print(f"Coverage pass rate: {report['quality_pass_rate']:.1%}")
print(f"Latest checkpoint: {report['latest_checkpoint']}")
```

## CI/CD Integration

Quality checks integrate seamlessly with GitHub Actions, GitLab CI, and other platforms.

See [CI/CD Integration](../ci-cd.md) for examples.

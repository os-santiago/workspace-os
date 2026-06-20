# Mutation Testing

Issue: #69 - Mutation Testing for Test Quality

## Overview

Mutation testing is a technique to evaluate the quality of our test suite by introducing small changes (mutations) to the source code and verifying that tests catch these changes. A high mutation score indicates that our tests effectively detect bugs.

## Setup

Mutation testing is configured in `pyproject.toml`:

```toml
[tool.mutmut]
paths_to_mutate = "src/workspace_os/"
backup = false
runner = "python -m pytest -x --tb=line -q"
tests_dir = "tests/"
dict_synonyms = "Struct, NamedStruct"
```

## Running Mutation Tests

### Quick Start

Run the mutation testing script:

```bash
# On Linux/Mac
./scripts/run-mutation-tests.sh

# On Windows
.\scripts\run-mutation-tests.ps1
```

### Manual Execution

```bash
# Install mutmut
pip install mutmut

# Run mutation tests
mutmut run

# View results
mutmut results

# Generate HTML report
mutmut html

# Open report in browser
open html/index.html  # Mac
xdg-open html/index.html  # Linux
start html/index.html  # Windows
```

## Mutation Score Threshold

**Minimum Required: 70%**

This threshold ensures that our test suite effectively catches mutations (code changes), indicating high test quality.

### What the Score Means

- **70%+**: Good test coverage and quality
- **50-69%**: Acceptable but needs improvement
- **<50%**: Insufficient test quality

## Understanding Results

### Mutation States

1. **Killed**: Test suite detected the mutation (good)
2. **Survived**: Mutation went undetected (needs better tests)
3. **Timeout**: Test took too long with the mutation
4. **Suspicious**: Unclear result, needs investigation

### Example Output

```
Total: 100
Killed: 75
Survived: 20
Timeout: 3
Suspicious: 2

Mutation Score: 75%
```

## Integration with CI/CD

Add mutation testing to your CI pipeline:

```yaml
- name: Run Mutation Tests
  run: |
    pip install mutmut
    ./scripts/run-mutation-tests.sh
```

The script will fail if the mutation score is below 70%, preventing merges of code with insufficient test quality.

## Interpreting Survived Mutations

When mutations survive, it indicates gaps in test coverage:

1. Review the survived mutations: `mutmut show <id>`
2. Add or improve tests to catch these mutations
3. Re-run mutation testing to verify improvements

## Performance Considerations

- Mutation testing is computationally intensive
- Run on a subset for quick feedback: `mutmut run --paths-to-mutate=src/workspace_os/specific_module.py`
- Full runs are recommended before releases

## Best Practices

1. **Run regularly**: Include in CI/CD for important modules
2. **Focus on critical code**: Prioritize mutation testing for security and core functionality
3. **Investigate survivors**: Each survived mutation represents a potential bug that tests won't catch
4. **Balance with development speed**: Use mutation testing strategically, not for every change

## Metrics and Monitoring

Track mutation score over time to ensure test quality improves:

- Initial baseline: Record current mutation score
- Target: Maintain or improve score with each release
- Report: Include mutation score in quality dashboards

## References

- [Mutmut Documentation](https://mutmut.readthedocs.io/)
- [Mutation Testing Concepts](https://en.wikipedia.org/wiki/Mutation_testing)
- Issue #69: Mutation Testing for Test Quality

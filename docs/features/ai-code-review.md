# AI-Powered Code Review

## Overview

The AI-powered code review module provides automated static analysis of Python code to detect quality issues, code smells, complexity problems, and anti-patterns.

## Features

### Code Quality Checks

1. **Code Smells**
   - Long functions (>50 statements)
   - Too many parameters (>7)
   - Magic numbers
   - Duplicate code blocks

2. **Complexity Metrics**
   - Cyclomatic complexity analysis
   - Configurable thresholds (default: 10)
   - Detection of deeply nested logic

3. **Naming Conventions**
   - PEP 8 compliance checks
   - snake_case for functions
   - PascalCase for classes
   - Minimum name length validation

4. **Documentation Completeness**
   - Docstring presence checks
   - Public API documentation requirements
   - Minimum documentation ratio (default: 50%)

5. **Performance Anti-patterns**
   - String concatenation in loops
   - Inefficient list building patterns
   - Suboptimal algorithm patterns

## Usage

### Programmatic API

```python
from pathlib import Path
from workspace_os.ai_code_review import AICodeReviewer, review_directory

# Review a single file
reviewer = AICodeReviewer(max_complexity=10, min_doc_ratio=0.5)
result = reviewer.review_file(Path("myfile.py"))

print(result.render_summary())
for issue in result.issues:
    print(issue.render())

# Review entire directory
results = review_directory(Path("src/"), extensions=('.py',))
```

### Integration with Cycle Quality Checks

The AI code review is automatically integrated into the quality gate checks when running cycle operations:

```bash
workspace cycle checkpoint
```

The review runs as part of the quality checks and reports:
- Total files reviewed
- Files passed vs failed
- Issue counts by severity (Critical, High, Medium, Low)

## Configuration

### Thresholds

Configure thresholds via `config/quality.json`:

```json
{
  "ai_review": {
    "max_complexity": 10,
    "min_doc_ratio": 0.5,
    "max_function_length": 50,
    "max_parameters": 7
  }
}
```

### Severity Levels

Issues are categorized by severity:

- **Critical**: Must be fixed immediately (blocks deployment)
- **High**: Should be fixed soon (may block deployment)
- **Medium**: Should be addressed in next iteration
- **Low**: Nice-to-have improvements

## Issue Categories

### code_smell
Issues related to code maintainability and readability.

**Examples:**
- Functions longer than 50 statements
- Magic numbers without named constants
- Duplicate code blocks

### complexity
Issues related to code complexity and maintainability.

**Examples:**
- High cyclomatic complexity (>10)
- Deeply nested conditionals
- Complex boolean logic

### naming
Issues related to naming conventions.

**Examples:**
- Non-PEP 8 compliant names
- Too-short variable names
- Inconsistent naming patterns

### documentation
Issues related to code documentation.

**Examples:**
- Missing docstrings on public functions
- Missing docstrings on classes
- Low documentation ratio

### performance
Issues related to code performance.

**Examples:**
- String concatenation in loops
- Inefficient list building
- Suboptimal algorithms

## Quality Gates

The AI review integrates with cycle quality gates using these criteria:

**Pass Conditions:**
- Zero critical issues
- ≤3 high-severity issues (or ≤10% of files)
- Reasonable number of medium/low issues

**Fail Conditions:**
- Any critical issues present
- >3 high-severity issues (or >10% of files)

## Reports

### File-level Report

```
✅ PASS - src/module.py
Issues: 2 (Critical: 0, High: 0)
Complexity: 5.2
Documentation: 80.00%
```

### Project-level Report

```
===============================================================================
AI CODE REVIEW REPORT
===============================================================================
Files reviewed: 45
Files passed: 42/45
Total issues: 127
  Critical: 0
  High: 2
  Medium: 45
  Low: 80

HIGH SEVERITY ISSUES:
-------------------------------------------------------------------------------
🔴 src/processor.py:156 [complexity] Function 'process_data' has high 
    cyclomatic complexity (15)
  Suggestion: Refactor to reduce branching and nesting
===============================================================================
```

## Examples

### Detecting Code Smells

```python
# Bad: Magic numbers
def calculate_discount(price):
    return price * 0.85  # ⚠️ Magic number

# Good: Named constants
DISCOUNT_RATE = 0.85
def calculate_discount(price):
    return price * DISCOUNT_RATE
```

### Detecting Complexity Issues

```python
# Bad: High complexity
def process(data, mode, validate, retry, cache):
    if mode == "fast":
        if validate:
            if retry:
                if cache:
                    # ... deeply nested logic
                    pass

# Good: Extracted functions
def process(data, config):
    if config.mode == "fast":
        return process_fast_mode(data, config)
    return process_standard_mode(data, config)
```

### Detecting Performance Issues

```python
# Bad: String concatenation in loop
result = ""
for item in items:
    result += str(item)  # ⚠️ Performance anti-pattern

# Good: Use join
result = "".join(str(item) for item in items)
```

## Integration Points

### CLI Integration

```bash
# Run quality checks including AI review
workspace cycle checkpoint

# View cycle report with AI review results
workspace cycle report
```

### CI/CD Integration

The AI review runs automatically during:
- Cycle checkpoints
- Quality gate checks
- Pre-merge validation

## Limitations

- Currently supports Python files only
- Heuristic-based analysis (not deep semantic analysis)
- May produce false positives in edge cases
- Does not replace human code review

## Future Enhancements

Planned improvements:
- Multi-language support (JavaScript, Go, etc.)
- Custom rule definitions
- Integration with external linters
- AI-powered fix suggestions
- Learning from codebase patterns

## See Also

- [Quality Coverage](../testing/quality-coverage.md)
- [Mutation Testing](../testing/mutation-testing.md)
- [Cycle Management](../features/cycle-management.md)

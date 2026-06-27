# Bandit SAST Integration

## Overview

Workspace OS integrates [Bandit](https://bandit.readthedocs.io/) for Python static application security testing (SAST). Bandit automatically scans source code for common security issues during cycle quality checks.

## What Bandit Checks

Bandit detects:
- **SQL Injection** vulnerabilities
- **Hardcoded secrets** (passwords, API keys, tokens)
- **Insecure cryptography** (weak hashing, DES, MD5)
- **Command injection** risks
- **Path traversal** vulnerabilities
- **XML vulnerabilities** (XXE, XPath injection)
- **Insecure deserialization**
- And many more security anti-patterns

## When It Runs

Bandit automatically runs during:
- `workspace cycle run` - Quality gate checks
- `workspace cycle work` - Work cycle quality validation
- `workspace cycle checkpoint` - Manual checkpoint validation

## Configuration

Configure Bandit via `config/quality.json`:

```json
{
  "security": {
    "bandit_enabled": true,
    "severity_threshold": "medium"
  },
  "quality_gates": {
    "enforce_security": true,
    "block_on_failure": true
  }
}
```

### Severity Levels

- `"low"` - Report all issues (noisy)
- `"medium"` - Report medium and high (default)
- `"high"` - Only critical issues

## Installation

Bandit is included in workspace-os dependencies:

```bash
pip install workspace-os
```

Or install separately:

```bash
pip install bandit
```

## Usage

### Automatic (Recommended)

Bandit runs automatically during cycle quality checks:

```bash
# Start a cycle - Bandit runs on each checkpoint
workspace cycle work --duration-minutes 30 --objective "feature development"
```

### Manual Execution

Run Bandit directly:

```bash
# Basic scan
bandit -r src/

# JSON output (same as WOS uses)
bandit -r src/ -f json -ll

# Exclude test files
bandit -r src/ --skip B101
```

## Suppressing False Positives

Use `# nosec` comments for verified false positives:

```python
# Hardcoded password detected (false positive - test fixture)
TEST_PASSWORD = "test123"  # nosec B105
```

**Important**: Document WHY you're suppressing each issue.

## Integration with CI/CD

Bandit is part of WOS quality gates, which means:

### ✅ Blocking Behavior

When `enforce_security: true` and `block_on_failure: true`:
- High/medium severity issues **FAIL** the checkpoint
- Low severity issues are reported but don't block

### 🔍 Reporting

Check results:

```bash
# View latest cycle report
workspace cycle status

# Check specific checkpoint
workspace cycle report --id 42
```

Example output:

```
quality checks:
- PASS quality:compilation: All files compiled successfully.
- PASS quality:test-suite: Test suite passed successfully.
- FAIL quality:bandit: Bandit found 3 security issues (severity >= medium)
```

## Common Issues

### 1. Hardcoded Secrets

**Bad:**
```python
API_KEY = "sk-1234567890abcdef"
```

**Good:**
```python
API_KEY = os.environ.get("API_KEY")
```

### 2. SQL Injection

**Bad:**
```python
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

**Good:**
```python
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### 3. Command Injection

**Bad:**
```python
os.system(f"ping {user_input}")
```

**Good:**
```python
subprocess.run(["ping", user_input], check=True)
```

### 4. Weak Cryptography

**Bad:**
```python
import hashlib
hashlib.md5(password.encode())
```

**Good:**
```python
import hashlib
hashlib.sha256(password.encode())
# Or better: use bcrypt/scrypt for passwords
```

## Metrics & Monitoring

Track security posture over time:

```bash
# View cycle history
workspace cycle history --limit 10

# Check security pass rate trend
workspace memory status
```

## Continuous Improvement

Bandit findings feed into WOS learning:
- Security patterns are tracked
- Recurring issues trigger alerts
- Learning model improves over time

## References

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Bandit GitHub](https://github.com/PyCQA/bandit)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Database](https://cwe.mitre.org/)

## Support

For issues with Bandit integration:

1. Check Bandit is installed: `bandit --version`
2. Verify config: `cat config/quality.json`
3. Run manually: `bandit -r src/ -f json -ll`
4. Report issues: https://github.com/os-santiago/workspace-os/issues

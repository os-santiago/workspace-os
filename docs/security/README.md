# Security Scanning System

## Overview

Workspace OS implements comprehensive dependency vulnerability scanning to proactively identify and remediate security issues in dependencies and code.

## Quick Start

### Install Security Tools

```bash
pip install pip-audit safety bandit cyclonedx-bom
```

### Run Security Scan

```bash
# Full security scan
./scripts/security/scan-dependencies.sh

# Install pre-commit hooks
./scripts/security/install-hooks.sh
```

### View Results

```bash
# View reports
cat .security-reports/pip-audit.json
cat .security-reports/safety.json
cat .security-reports/bandit.json
```

## Components

### 1. GitHub Actions Workflow

**File**: `.github/workflows/security-scan.yml`

Automated scanning on:
- Every push to main/develop
- Every pull request
- Daily at 2 AM UTC
- Manual trigger (workflow_dispatch)

**Jobs**:
- `dependency-scan`: pip-audit + safety
- `code-scan`: Bandit static analysis
- `supply-chain`: SBOM generation

### 2. Local Scanning Scripts

**scan-dependencies.sh**
- Runs pip-audit, safety, and bandit
- Generates reports in `.security-reports/`
- Exit code 1 if critical issues found

**pre-commit-scan.sh**
- Lightweight pre-commit security check
- Scans only changed files
- Blocks commits with vulnerabilities

**install-hooks.sh**
- Installs git pre-commit hook
- Automatic activation on commit

### 3. WOS Integration

**Module**: `src/workspace_os/security/`

Integrated with `wos validate` and cycle quality checks:

```bash
# Run validation including security
wos validate

# Skip security scan
wos validate --skip-security-scan

# Bandit runs automatically in cycle checkpoints
workspace cycle work --duration-minutes 30 --objective "development"
```

**Note**: Bandit SAST is automatically integrated into cycle quality gates. See [bandit-sast.md](./bandit-sast.md) for details.

### 4. Security Policy

**Document**: `docs/security/vulnerability-scanning-policy.md`

Defines:
- Scanning triggers and frequency
- Severity levels and remediation timelines
- Exception process
- Compliance requirements

### 5. Policy as Code

**File**: `config/security-policy.yml`

Declares the repository security policy used by `SecurityValidator`:
- Allowed dependencies from `pyproject.toml`
- Banned code patterns such as unsafe YAML loading and `shell=True`
- Required headers for security package modules and security validator tests
- Environment-backed secret handling for model provider configuration

The security dashboard exposes the resulting compliance summary through:
- `GET /api/security`
- `GET /api/security.md`

### 5. Exception Management

**File**: `.security-exceptions.yml`

Track approved exceptions:

```yaml
exceptions:
  - cve: CVE-2024-12345
    package: example-package
    severity: medium
    reason: "No patch available"
    mitigations: ["Input validation", "Network isolation"]
    expiry_date: "2026-09-20"
```

**Validator**: `scripts/security/check-exceptions.py`
- Checks expiry dates
- Flags expired exceptions
- Warns on upcoming reviews

## Scanning Tools

### pip-audit
- **Purpose**: Python dependency vulnerability scanning
- **Database**: Open Source Vulnerabilities (OSV)
- **Output**: JSON report with CVE details
- **Threshold**: Fails on any vulnerability

### Safety
- **Purpose**: PyPI-focused vulnerability detection
- **Database**: Safety DB
- **Output**: JSON report
- **Threshold**: Warning only (cross-reference)

### Bandit
- **Purpose**: Static code security analysis
- **Scope**: Python source files
- **Output**: JSON report
- **Threshold**: Fails on high severity

### CycloneDX
- **Purpose**: Software Bill of Materials (SBOM)
- **Format**: CycloneDX JSON
- **Retention**: 90 days in GitHub artifacts

## Workflow Integration

### Pull Request Flow

1. Developer opens PR
2. GitHub Actions runs security scan
3. If vulnerabilities found:
   - PR comment posted with details
   - Status check fails
   - PR blocked from merge
4. Developer remediates
5. Re-run scan until clean
6. PR approved and merged

### Daily Monitoring

1. Scheduled scan runs at 2 AM UTC
2. Checks all dependencies against latest CVE data
3. If new vulnerabilities:
   - GitHub Security tab notification
   - Email alert to team
   - Issue created automatically
4. Team reviews and remediates

### Local Development

1. Developer modifies `pyproject.toml`
2. Pre-commit hook detects change
3. Quick vulnerability scan runs
4. If issues found:
   - Commit blocked
   - Details shown in terminal
   - Developer fixes before committing

## Remediation Process

### Step 1: Identify

```bash
./scripts/security/scan-dependencies.sh
```

### Step 2: Assess

```bash
# Review detailed report
cat .security-reports/pip-audit.json | jq '.dependencies'

# Check CVE details
curl https://nvd.nist.gov/vuln/detail/CVE-2024-12345
```

### Step 3: Update

```bash
# Update vulnerable package
pip install --upgrade package-name

# Verify fix
./scripts/security/scan-dependencies.sh
```

### Step 4: Test

```bash
# Run tests
pytest

# Run validation
wos validate
```

### Step 5: Document

```bash
# Commit with CVE reference
git commit -m "security: update package-name to fix CVE-2024-12345"
```

## Exception Handling

### When to Use Exceptions

- No patch available from vendor
- Vulnerability not exploitable in our context
- Temporary workaround until patch released

### Creating Exception

1. Assess actual risk
2. Document mitigations
3. Add to `.security-exceptions.yml`
4. Set expiry date (max 90 days)
5. Get approval from tech lead

### Exception Review

```bash
# Check exception status
python scripts/security/check-exceptions.py

# Monthly review process
# - Verify mitigations still effective
# - Check for new patches
# - Extend or close exception
```

## Metrics and Reporting

### Real-time Status

```bash
# WOS integration
wos validate

# Direct scan
./scripts/security/scan-dependencies.sh
```

### Reports Location

- **Local**: `.security-reports/`
- **CI/CD**: GitHub Actions artifacts
- **SBOM**: GitHub Actions artifacts (90 day retention)

### Metrics Tracked

- Vulnerability count by severity
- Mean time to remediation
- Exception count and age
- Scan compliance rate

## Configuration

### pyproject.toml

Add security dependencies:

```toml
[project.optional-dependencies]
security = [
    "pip-audit>=2.6.0",
    "safety>=2.3.0",
    "bandit[toml]>=1.7.5",
    "cyclonedx-bom>=3.11.0",
]
```

Install:

```bash
pip install -e ".[security]"
```

### Bandit Configuration

Create `.bandit`:

```yaml
exclude_dirs:
  - /tests
  - /.venv
  - /build

skips:
  - B101  # assert_used
  - B601  # paramiko_calls
```

## Troubleshooting

### Scan Failing Locally

```bash
# Check tool installation
pip-audit --version
safety --version
bandit --version

# Reinstall if needed
pip install --upgrade pip-audit safety bandit
```

### False Positives

```bash
# Review specific CVE
cat .security-reports/pip-audit.json | jq '.dependencies[] | select(.name=="package-name")'

# If not applicable, add exception
# Edit .security-exceptions.yml
```

### CI/CD Failures

```bash
# Download artifact from GitHub Actions
gh run download <run-id> -n vulnerability-reports

# Review reports locally
cat pip-audit-report.json
```

## Best Practices

1. **Run scans before every PR**
   ```bash
   ./scripts/security/scan-dependencies.sh
   ```

2. **Keep dependencies up to date**
   ```bash
   pip list --outdated
   pip install --upgrade <package>
   ```

3. **Review security alerts promptly**
   - Check GitHub Security tab daily
   - Respond to alerts within SLA

4. **Use exception sparingly**
   - Only when no alternative
   - Always set expiry date
   - Document thoroughly

5. **Test after updates**
   - Run full test suite
   - Validate in staging environment
   - Monitor production after deployment

## References

- [Vulnerability Scanning Policy](./vulnerability-scanning-policy.md)
- [OSV Database](https://osv.dev/)
- [NIST NVD](https://nvd.nist.gov/)
- [CycloneDX](https://cyclonedx.org/)
- [Bandit Documentation](https://bandit.readthedocs.io/)

## Support

For questions or issues:
1. Check troubleshooting section above
2. Review policy documentation
3. Consult security team
4. Create GitHub issue with `security` label

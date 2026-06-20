#!/usr/bin/env bash
# Pre-commit hook for security scanning
# Runs lightweight security checks before commits

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Running pre-commit security checks..."

# Check if pyproject.toml changed
if git diff --cached --name-only | grep -q "pyproject.toml"; then
    echo "Dependencies changed - running quick vulnerability scan..."
    
    # Quick scan with pip-audit only
    if command -v pip-audit &> /dev/null; then
        if pip-audit --quiet 2>&1; then
            echo -e "${GREEN}✓ No known vulnerabilities in dependencies${NC}"
        else
            echo -e "${RED}✗ Vulnerabilities detected in dependencies${NC}"
            echo "Run './scripts/security/scan-dependencies.sh' for details"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠ pip-audit not installed - skipping dependency scan${NC}"
        echo "Install with: pip install pip-audit"
    fi
fi

# Scan Python files for security issues
PYTHON_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)

if [ -n "$PYTHON_FILES" ]; then
    echo "Scanning modified Python files..."
    
    if command -v bandit &> /dev/null; then
        if echo "$PYTHON_FILES" | xargs bandit -ll 2>&1 > /dev/null; then
            echo -e "${GREEN}✓ No security issues in code${NC}"
        else
            echo -e "${YELLOW}⚠ Potential security issues detected${NC}"
            echo "$PYTHON_FILES" | xargs bandit -ll || true
            echo ""
            echo "Review issues above. Use --skip-verify to bypass if needed."
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠ bandit not installed - skipping code scan${NC}"
        echo "Install with: pip install bandit"
    fi
fi

echo -e "${GREEN}✓ Pre-commit security checks passed${NC}"
exit 0

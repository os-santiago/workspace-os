#!/usr/bin/env bash
# Dependency Vulnerability Scanner
# Scans Python dependencies for known security vulnerabilities

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="$PROJECT_ROOT/.security-reports"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "Workspace OS - Dependency Vulnerability Scanner"
echo "=================================================="
echo ""

# Create reports directory
mkdir -p "$REPORT_DIR"

# Ensure tools are installed
echo "Checking security tools..."
pip install -q pip-audit safety bandit 2>/dev/null || {
    echo "Installing security tools..."
    pip install pip-audit safety bandit
}

echo ""
echo "=== Running pip-audit (OSV Database) ==="
echo ""

if pip-audit --format json --output "$REPORT_DIR/pip-audit.json" 2>&1; then
    echo -e "${GREEN}✓ pip-audit: No vulnerabilities found${NC}"
    AUDIT_STATUS=0
else
    echo -e "${RED}✗ pip-audit: Vulnerabilities detected${NC}"
    pip-audit --format text || true
    AUDIT_STATUS=1
fi

echo ""
echo "=== Running Safety Check ==="
echo ""

if safety check --json --output "$REPORT_DIR/safety.json" 2>&1; then
    echo -e "${GREEN}✓ Safety: No vulnerabilities found${NC}"
    SAFETY_STATUS=0
else
    echo -e "${RED}✗ Safety: Vulnerabilities detected${NC}"
    safety check || true
    SAFETY_STATUS=1
fi

echo ""
echo "=== Running Bandit (Code Analysis) ==="
echo ""

if bandit -r "$PROJECT_ROOT/src" -f json -o "$REPORT_DIR/bandit.json" 2>&1; then
    echo -e "${GREEN}✓ Bandit: No security issues found${NC}"
    BANDIT_STATUS=0
else
    echo -e "${YELLOW}⚠ Bandit: Potential issues detected${NC}"
    bandit -r "$PROJECT_ROOT/src" -ll || true
    BANDIT_STATUS=1
fi

echo ""
echo "=== Scan Summary ==="
echo ""
echo "Reports saved to: $REPORT_DIR"
echo ""
echo "| Tool       | Status |"
echo "|------------|--------|"
[ $AUDIT_STATUS -eq 0 ] && echo "| pip-audit  | ${GREEN}PASS${NC}   |" || echo "| pip-audit  | ${RED}FAIL${NC}   |"
[ $SAFETY_STATUS -eq 0 ] && echo "| Safety     | ${GREEN}PASS${NC}   |" || echo "| Safety     | ${RED}FAIL${NC}   |"
[ $BANDIT_STATUS -eq 0 ] && echo "| Bandit     | ${GREEN}PASS${NC}   |" || echo "| Bandit     | ${YELLOW}WARN${NC}   |"
echo ""

# Exit with error if critical issues found
if [ $AUDIT_STATUS -ne 0 ] || [ $SAFETY_STATUS -ne 0 ]; then
    echo -e "${RED}FAILED: Critical vulnerabilities detected${NC}"
    exit 1
else
    echo -e "${GREEN}SUCCESS: No critical vulnerabilities found${NC}"
    exit 0
fi

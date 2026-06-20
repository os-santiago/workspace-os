#!/usr/bin/env bash
# One-time setup script for security scanning infrastructure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=================================================="
echo "Security Scanning Setup"
echo "=================================================="
echo ""

# Install security tools
echo "Step 1: Installing security scanning tools..."
pip install -q pip-audit safety "bandit[toml]" cyclonedx-bom pyyaml
echo "✓ Tools installed"
echo ""

# Install git hooks
echo "Step 2: Installing pre-commit hooks..."
"$SCRIPT_DIR/install-hooks.sh"
echo ""

# Create reports directory
echo "Step 3: Creating reports directory..."
mkdir -p "$PROJECT_ROOT/.security-reports"
echo "✓ Created .security-reports/"
echo ""

# Add to .gitignore if not present
echo "Step 4: Updating .gitignore..."
if ! grep -q ".security-reports" "$PROJECT_ROOT/.gitignore" 2>/dev/null; then
    echo ".security-reports/" >> "$PROJECT_ROOT/.gitignore"
    echo "✓ Added .security-reports/ to .gitignore"
else
    echo "✓ .gitignore already configured"
fi
echo ""

# Run initial scan
echo "Step 5: Running initial security scan..."
if "$SCRIPT_DIR/scan-dependencies.sh"; then
    echo ""
    echo "=================================================="
    echo "✓ Setup Complete - No Vulnerabilities Found"
    echo "=================================================="
else
    echo ""
    echo "=================================================="
    echo "⚠ Setup Complete - Vulnerabilities Detected"
    echo "=================================================="
    echo ""
    echo "Please review the scan results above and remediate"
    echo "before proceeding with development."
fi

echo ""
echo "Next Steps:"
echo "1. Review security policy: docs/security/vulnerability-scanning-policy.md"
echo "2. Review scan results: .security-reports/"
echo "3. Configure GitHub Actions workflow (if not already done)"
echo "4. Run 'wos validate' to verify integration"
echo ""

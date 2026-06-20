#!/usr/bin/env bash
# Install security scanning git hooks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo "Installing security scanning git hooks..."

# Create pre-commit hook
cat > "$HOOKS_DIR/pre-commit" << 'HOOKEOF'
#!/usr/bin/env bash
# Security scanning pre-commit hook

SCRIPT_DIR="$(git rev-parse --show-toplevel)"

if [ -f "$SCRIPT_DIR/scripts/security/pre-commit-scan.sh" ]; then
    exec "$SCRIPT_DIR/scripts/security/pre-commit-scan.sh"
else
    echo "Warning: pre-commit-scan.sh not found"
    exit 0
fi
HOOKEOF

chmod +x "$HOOKS_DIR/pre-commit"

echo "✓ Pre-commit hook installed"
echo ""
echo "The hook will run automatically on 'git commit'"
echo "To bypass: git commit --no-verify"
echo "To uninstall: rm $HOOKS_DIR/pre-commit"

#!/usr/bin/env bash
#
# Lightweight issue status checker
# Queries GitHub directly - no stale state
#

cd D:/git/homedir

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Homedir Issues - Live Status                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

OPEN_ISSUES=$(gh issue list --state open | wc -l)
OPEN_PRS=$(gh pr list --state open | wc -l)

echo "📊 Summary:"
echo "   Open Issues: $OPEN_ISSUES"
echo "   Open PRs: $OPEN_PRS"
echo ""

echo "🎯 Priority Issues (P0/P1):"
gh issue list --state open --label P0,P1 --limit 5
echo ""

echo "🔄 Open PRs:"
gh pr list --state open --limit 3
echo ""

echo "⏱️  Live query at: $(date '+%Y-%m-%d %H:%M:%S')"

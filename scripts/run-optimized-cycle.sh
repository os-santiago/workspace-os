#!/usr/bin/env bash
#
# Quick launcher for optimized high-throughput WOS cycle
#
# Usage:
#   ./scripts/run-optimized-cycle.sh [duration_minutes] [target_workspace]
#
# Examples:
#   ./scripts/run-optimized-cycle.sh 60 homedir
#   ./scripts/run-optimized-cycle.sh 30 workspace-os

set -euo pipefail

# Parse arguments
DURATION_MINUTES=${1:-60}
TARGET_WORKSPACE=${2:-homedir}
WORKSPACE_ROOT="/d/git"

# Detect CPU cores for optimal configuration
if command -v nproc &> /dev/null; then
    CORES=$(nproc)
elif command -v sysctl &> /dev/null; then
    CORES=$(sysctl -n hw.ncpu)
else
    CORES=8  # Conservative default
fi

# Calculate optimal workers
OPTIMAL_WORKERS=$((CORES * 2))
if [ $OPTIMAL_WORKERS -gt 32 ]; then
    OPTIMAL_WORKERS=32
fi
if [ $OPTIMAL_WORKERS -lt 8 ]; then
    OPTIMAL_WORKERS=8
fi

echo "=================================================="
echo "WOS High-Throughput Cycle Launcher"
echo "=================================================="
echo ""
echo "Configuration:"
echo "  Target: $TARGET_WORKSPACE"
echo "  Duration: $DURATION_MINUTES minutes"
echo "  CPU Cores: $CORES"
echo "  Max Workers: $OPTIMAL_WORKERS"
echo ""
echo "Expected Performance:"
echo "  Baseline: 1-5 PRs/hour"
echo "  Optimized: 15-30 PRs/hour"
echo "  Aggressive: 30-40 PRs/hour"
echo ""
echo "This run should produce: ~$((DURATION_MINUTES * 15 / 60))-$((DURATION_MINUTES * 30 / 60)) PRs"
echo ""
echo "=================================================="
echo ""

# Verify target workspace exists
TARGET_PATH="$WORKSPACE_ROOT/$TARGET_WORKSPACE"
if [ ! -d "$TARGET_PATH" ]; then
    echo "ERROR: Workspace not found: $TARGET_PATH"
    exit 1
fi

# Check if gh CLI is available and authenticated
if ! command -v gh &> /dev/null; then
    echo "ERROR: gh CLI not found. Install: https://cli.github.com/"
    exit 1
fi

if ! gh auth status &> /dev/null; then
    echo "ERROR: gh CLI not authenticated. Run: gh auth login"
    exit 1
fi

# Check available issues
cd "$TARGET_PATH"
ISSUE_COUNT=$(gh issue list --limit 100 --json number | jq '. | length')
echo "Available issues: $ISSUE_COUNT"

if [ "$ISSUE_COUNT" -lt "$OPTIMAL_WORKERS" ]; then
    echo "WARNING: Only $ISSUE_COUNT issues available, but $OPTIMAL_WORKERS workers configured."
    echo "         Reducing workers to $ISSUE_COUNT for optimal utilization."
    OPTIMAL_WORKERS=$ISSUE_COUNT
fi

if [ "$ISSUE_COUNT" -eq 0 ]; then
    echo "ERROR: No issues available to work on."
    exit 1
fi

echo ""
echo "Workspace status:"
git status --short
echo ""

# Confirm before proceeding
read -p "Start optimized cycle? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Set optimal environment variables
export WOS_MAX_WORKERS=$OPTIMAL_WORKERS
export WOS_CHECKPOINT_INTERVAL_SECONDS=600
export WOS_MIN_ITEMS_PER_CHECKPOINT=$((OPTIMAL_WORKERS * 2))
export WOS_MAX_HEALING_ATTEMPTS=1
export WOS_ENABLE_ISSUE_ASSIGNMENT=true

echo ""
echo "Environment configured:"
echo "  WOS_MAX_WORKERS=$WOS_MAX_WORKERS"
echo "  WOS_CHECKPOINT_INTERVAL_SECONDS=$WOS_CHECKPOINT_INTERVAL_SECONDS"
echo "  WOS_MIN_ITEMS_PER_CHECKPOINT=$WOS_MIN_ITEMS_PER_CHECKPOINT"
echo "  WOS_MAX_HEALING_ATTEMPTS=$WOS_MAX_HEALING_ATTEMPTS"
echo "  WOS_ENABLE_ISSUE_ASSIGNMENT=$WOS_ENABLE_ISSUE_ASSIGNMENT"
echo ""
echo "Starting cycle..."
echo "=================================================="
echo ""

# Generate unique label with timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LABEL="optimized-${DURATION_MINUTES}m-${TIMESTAMP}"

# Start the cycle
python -m workspace_os cycle work \
  --continuous \
  --duration-minutes "$DURATION_MINUTES" \
  --label "$LABEL" \
  --objective "High-throughput issue resolution for $TARGET_WORKSPACE"

CYCLE_EXIT_CODE=$?

echo ""
echo "=================================================="
echo "Cycle Complete"
echo "=================================================="
echo ""

if [ $CYCLE_EXIT_CODE -eq 0 ]; then
    echo "✓ Cycle completed successfully"
else
    echo "✗ Cycle exited with error code: $CYCLE_EXIT_CODE"
fi

echo ""
echo "Results:"
echo "--------"

# Show cycle status
python -m workspace_os cycle status

echo ""
echo "Pull Requests created:"
gh pr list --limit 50 | head -20

echo ""
echo "To review detailed results:"
echo "  wos cycle status"
echo "  wos batch summary"
echo "  wos journal report"
echo ""
echo "To review PRs:"
echo "  cd $TARGET_PATH && gh pr list"
echo ""
echo "=================================================="

exit $CYCLE_EXIT_CODE

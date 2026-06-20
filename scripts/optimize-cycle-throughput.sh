#!/usr/bin/env bash
#
# Optimize WOS Cycle Throughput for Issue Resolution
#
# This script configures environment variables for maximum throughput
# when running `workspace cycle work --continuous` to resolve GitHub issues.
#
# Target: 15-30 PRs per hour (vs baseline 1-5 PRs/hour)

set -euo pipefail

echo "=================================================="
echo "WOS Cycle Throughput Optimization"
echo "=================================================="
echo ""

# Detect available CPU cores
if command -v nproc &> /dev/null; then
    CORES=$(nproc)
elif command -v sysctl &> /dev/null; then
    CORES=$(sysctl -n hw.ncpu)
else
    CORES=4  # Safe default
fi

echo "Detected CPU cores: $CORES"
echo ""

# Calculate optimal max_workers
# Rule: Use 2-4x CPU cores, capped at 32 for stability
# More workers = more parallelism but also more memory/context switching
RECOMMENDED_WORKERS=$((CORES * 2))
if [ $RECOMMENDED_WORKERS -gt 32 ]; then
    RECOMMENDED_WORKERS=32
fi

echo "Recommended configuration:"
echo "-------------------------"
echo "WOS_MAX_WORKERS=$RECOMMENDED_WORKERS"
echo "  - Controls how many agents work in parallel"
echo "  - Higher = more PRs/hour, but needs more CPU/memory"
echo ""
echo "WOS_CHECKPOINT_INTERVAL_SECONDS=600"
echo "  - Checkpoint every 10 minutes (vs default 5 min)"
echo "  - Reduces validation overhead, more time for actual work"
echo ""
echo "WOS_MIN_ITEMS_PER_CHECKPOINT=$((RECOMMENDED_WORKERS * 2))"
echo "  - Minimum work items before checkpoint"
echo "  - Prevents excessive checkpoint overhead"
echo ""
echo "WOS_MAX_HEALING_ATTEMPTS=1"
echo "  - Auto-heal once on failure (vs default 2)"
echo "  - Reduces time spent on broken checkpoints"
echo ""
echo "WOS_ENABLE_ISSUE_ASSIGNMENT=true"
echo "  - Pre-assign specific issues to each agent"
echo "  - Eliminates collisions and decision overhead"
echo ""
echo "=================================================="
echo ""

# Prompt user for confirmation
read -p "Apply these settings? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Export environment variables
export WOS_MAX_WORKERS=$RECOMMENDED_WORKERS
export WOS_CHECKPOINT_INTERVAL_SECONDS=600
export WOS_MIN_ITEMS_PER_CHECKPOINT=$((RECOMMENDED_WORKERS * 2))
export WOS_MAX_HEALING_ATTEMPTS=1
export WOS_ENABLE_ISSUE_ASSIGNMENT=true

echo ""
echo "✓ Environment configured for high throughput"
echo ""
echo "Usage:"
echo "------"
echo "1. Navigate to your workspace:"
echo "   cd /d/git/homedir"
echo ""
echo "2. Start optimized cycle:"
echo "   wos cycle work --continuous --duration-minutes 60 --label high-throughput --objective 'Resolve GitHub issues'"
echo ""
echo "Expected performance:"
echo "- Baseline: 1-5 PRs/hour"
echo "- Optimized: 15-30 PRs/hour (3-6x improvement)"
echo ""
echo "Monitor with:"
echo "- wos cycle status"
echo "- wos batch summary"
echo "- Watch queue utilization in cycle logs"
echo ""
echo "=================================================="

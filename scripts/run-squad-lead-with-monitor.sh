#!/usr/bin/env bash
#
# WOS Squad Lead Self-Improvement with Animated Progress Monitor
# Launches cycle in background and shows beautiful real-time progress
#

set -euo pipefail

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  WOS Squad Lead Self-Improvement Mission                     ║"
echo "║  Target: 95%+ Success Rate | World-Class Development Team   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
DURATION_MINUTES=${1:-45}
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LABEL="squad-lead-improvement-${TIMESTAMP}"
OUTPUT_FILE="/tmp/wos-cycle-${TIMESTAMP}.output"

# Squad Lead Mode - Intelligent coordination
export WOS_SQUAD_LEAD_MODE=true
export WOS_ROLE_ROTATION_CYCLE=9
export WOS_SQUAD_CONTEXT_WINDOW=5
export WOS_DYNAMIC_REBALANCING=true

# High Performance - Balanced throughput and quality
export WOS_MAX_WORKERS=16
export WOS_CHECKPOINT_INTERVAL_SECONDS=300
export WOS_MIN_ITEMS_PER_CHECKPOINT=24
export WOS_ENABLE_ISSUE_ASSIGNMENT=true

# Quality First - Strict gates
export WOS_ENABLE_AUTO_HEALING=true
export WOS_MAX_HEALING_ATTEMPTS=2
export WOS_CHECKPOINT_FAST_PATH_THRESHOLD=0.8

echo "Configuration:"
echo "  Squad Lead Mode: ✓ ENABLED"
echo "  Max Workers: 16 (balanced quality/throughput)"
echo "  Auto-Healing: ✓ ENABLED (2 attempts max)"
echo "  Role Rotation: Every 9 work items"
echo "  Quality Gates: STRICT (80% threshold for full tests)"
echo ""
echo "Duration: ${DURATION_MINUTES} minutes"
echo "Label: ${LABEL}"
echo "Output: ${OUTPUT_FILE}"
echo ""

# Start WOS cycle in background
echo "🚀 Launching WOS cycle in background..."

python -m workspace_os cycle work \
  --duration-minutes "${DURATION_MINUTES}" \
  --label "${LABEL}" \
  --objective "Improve WOS workspace-os to achieve 95%+ success rate on implementations. Focus on: 1) Analyzing current failure patterns 2) Implementing validation improvements 3) Enhancing test coverage 4) Improving error handling 5) Following world-class development practices. Reference standard: https://github.com/os-santiago/homedir/actions/runs/27854239830 (100% success). Each work item must thoroughly validate changes before committing." \
  > "${OUTPUT_FILE}" 2>&1 &

CYCLE_PID=$!

echo "✓ Cycle started (PID: ${CYCLE_PID})"
echo ""

# Wait a moment for cycle to initialize
sleep 3

# Launch animated monitor
echo "📊 Starting progress monitor..."
echo ""
sleep 1

# Determine which monitor to use
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "Error: Python not found. Falling back to basic monitor."
    bash "$(dirname "$0")/monitor-cycle-progress.sh" "${OUTPUT_FILE}" "${DURATION_MINUTES}"
    exit $?
fi

# Run animated monitor
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${PYTHON_CMD}" "${SCRIPT_DIR}/monitor-cycle-animated.py" "${OUTPUT_FILE}" "${DURATION_MINUTES}"

# Wait for cycle to complete
echo ""
echo "Waiting for cycle to complete..."
wait ${CYCLE_PID}
CYCLE_EXIT_CODE=$?

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Cycle Complete - Analyzing Results                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [ $CYCLE_EXIT_CODE -eq 0 ]; then
    echo "✅ Cycle completed successfully"
else
    echo "⚠️  Cycle exited with code: $CYCLE_EXIT_CODE"
fi

echo ""
echo "Results Summary:"
python -m workspace_os cycle status

echo ""
echo "Performance Metrics:"
python -m workspace_os journal report

echo ""
echo "Output saved to: ${OUTPUT_FILE}"
echo ""
echo "Next steps:"
echo "  1. Review PRs: gh pr list --limit 20"
echo "  2. Check CI/CD: gh run list --limit 10"
echo "  3. Analyze failures and run next iteration"
echo ""

exit $CYCLE_EXIT_CODE

#!/usr/bin/env bash
#
# WOS Squad Lead Self-Improvement Cycle
# Mission: Achieve 95%+ success rate through iterative improvements
#

set -euo pipefail

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  WOS Squad Lead Self-Improvement Mission                     ║"
echo "║  Target: 95%+ Success Rate | World-Class Development Team   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Squad Lead Mode - Intelligent coordination
export WOS_SQUAD_LEAD_MODE=true
export WOS_ROLE_ROTATION_CYCLE=9
export WOS_SQUAD_CONTEXT_WINDOW=5
export WOS_DYNAMIC_REBALANCING=true

# High Performance - Balanced throughput and quality
export WOS_MAX_WORKERS=16  # Moderate parallelism for quality
export WOS_CHECKPOINT_INTERVAL_SECONDS=300  # Frequent validation
export WOS_MIN_ITEMS_PER_CHECKPOINT=24  # 1.5x workers
export WOS_ENABLE_ISSUE_ASSIGNMENT=true

# Quality First - Strict gates
export WOS_ENABLE_AUTO_HEALING=true  # Fix issues immediately
export WOS_MAX_HEALING_ATTEMPTS=2  # Persistent correction
export WOS_CHECKPOINT_FAST_PATH_THRESHOLD=0.8  # Run full tests often

echo "Configuration:"
echo "  Squad Lead Mode: ENABLED"
echo "  Max Workers: 16 (balanced quality/throughput)"
echo "  Auto-Healing: ENABLED (2 attempts max)"
echo "  Role Rotation: Every 9 work items"
echo "  Quality Gates: STRICT (80% threshold for full tests)"
echo ""

# Generate timestamp for this improvement cycle
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LABEL="squad-lead-improvement-${TIMESTAMP}"

echo "Objective: Improve WOS to achieve 95%+ success rate"
echo "Label: ${LABEL}"
echo ""
echo "Press ENTER to start improvement cycle..."
read

# Start WOS self-improvement cycle
python -m workspace_os cycle work \
  --duration-minutes 45 \
  --label "${LABEL}" \
  --objective "Improve WOS workspace-os to achieve 95%+ success rate on implementations. Focus on: 1) Analyzing current failure patterns 2) Implementing validation improvements 3) Enhancing test coverage 4) Improving error handling 5) Following world-class development practices. Reference standard: https://github.com/os-santiago/homedir/actions/runs/27854239830 (100% success). Each work item must thoroughly validate changes before committing."

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
echo "Next steps:"
echo "  1. Review PRs created in this cycle"
echo "  2. Check CI/CD results for success rate"
echo "  3. Analyze any failures to identify patterns"
echo "  4. Run another improvement cycle with learnings"
echo ""
echo "To view PRs:"
echo "  gh pr list --limit 20"
echo ""

exit $CYCLE_EXIT_CODE

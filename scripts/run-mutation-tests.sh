#!/bin/bash
# Mutation Testing Script for WOS Quality Enhancement
# Issue: #69
# Minimum mutation score threshold: 70%

set -e

echo "=== WOS Mutation Testing ==="
echo "Running mutation tests to verify test quality..."
echo

# Check if mutmut is installed
if ! command -v mutmut &> /dev/null; then
    echo "Installing mutmut..."
    pip install mutmut
fi

# Run mutation testing
echo "Starting mutation testing..."
mutmut run --paths-to-mutate=src/workspace_os/ --tests-dir=tests/ || true

# Generate results
echo
echo "=== Mutation Testing Results ==="
mutmut results

# Generate HTML report
echo
echo "Generating HTML report..."
mutmut html || true

# Check mutation score
MUTATION_SCORE=$(mutmut results | grep -oP 'Survived: \K\d+' || echo "0")
TOTAL_MUTATIONS=$(mutmut results | grep -oP 'Total: \K\d+' || echo "1")

# Calculate percentage (avoiding division by zero)
if [ "$TOTAL_MUTATIONS" -gt 0 ]; then
    KILLED_MUTATIONS=$((TOTAL_MUTATIONS - MUTATION_SCORE))
    SCORE_PERCENT=$((KILLED_MUTATIONS * 100 / TOTAL_MUTATIONS))
else
    SCORE_PERCENT=0
fi

echo
echo "=== Mutation Score ==="
echo "Killed mutations: $KILLED_MUTATIONS / $TOTAL_MUTATIONS"
echo "Mutation Score: $SCORE_PERCENT%"
echo "Threshold: 70%"
echo

# Enforce minimum threshold
if [ "$SCORE_PERCENT" -lt 70 ]; then
    echo "ERROR: Mutation score ($SCORE_PERCENT%) is below threshold (70%)"
    echo "Please improve test quality to meet the minimum requirement."
    exit 1
else
    echo "SUCCESS: Mutation score ($SCORE_PERCENT%) meets threshold (70%)"
fi

echo
echo "View detailed results: html/index.html"

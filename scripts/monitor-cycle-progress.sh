#!/usr/bin/env bash
#
# WOS Cycle Progress Monitor
# Shows real-time progress of background WOS cycles
#

set -euo pipefail

# Configuration
OUTPUT_FILE="${1:-}"
DURATION_MINUTES="${2:-45}"
REFRESH_INTERVAL=5  # seconds

if [ -z "$OUTPUT_FILE" ]; then
    echo "Usage: $0 <output_file> [duration_minutes]"
    echo ""
    echo "Example:"
    echo "  $0 /tmp/wos-cycle.output 45"
    exit 1
fi

if [ ! -f "$OUTPUT_FILE" ]; then
    echo "Error: Output file not found: $OUTPUT_FILE"
    exit 1
fi

# ANSI color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Progress bar function
draw_progress_bar() {
    local progress=$1
    local width=50
    local filled=$((progress * width / 100))
    local empty=$((width - filled))

    printf "["
    printf "%${filled}s" | tr ' ' '█'
    printf "%${empty}s" | tr ' ' '░'
    printf "]"
}

# Format duration
format_duration() {
    local seconds=$1
    local hours=$((seconds / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))

    if [ $hours -gt 0 ]; then
        printf "%dh %dm %ds" $hours $minutes $secs
    elif [ $minutes -gt 0 ]; then
        printf "%dm %ds" $minutes $secs
    else
        printf "%ds" $secs
    fi
}

# Extract metrics from output
extract_metrics() {
    local output_file=$1

    # Count completed work items
    local completed=$(grep -c "Completed work item" "$output_file" 2>/dev/null || echo "0")

    # Count failed work items
    local failed=$(grep -c "Failed work item" "$output_file" 2>/dev/null || echo "0")

    # Count checkpoints
    local checkpoints=$(grep -c "Checkpointing" "$output_file" 2>/dev/null || echo "0")

    # Extract queue utilization (latest)
    local util_raw=$(grep -o "[0-9]*% util" "$output_file" 2>/dev/null | tail -1 | grep -o "[0-9]*" || echo "0")

    # Extract running agents count (latest)
    local running=$(grep -o "[0-9]*/[0-9]* agents busy" "$output_file" 2>/dev/null | tail -1 | cut -d'/' -f1 || echo "0")
    local max_agents=$(grep -o "[0-9]*/[0-9]* agents busy" "$output_file" 2>/dev/null | tail -1 | cut -d'/' -f2 | cut -d' ' -f1 || echo "16")

    # Check if cycle is done
    local is_done=0
    if grep -q "Cycle Complete" "$output_file" 2>/dev/null; then
        is_done=1
    fi

    echo "$completed|$failed|$checkpoints|$util_raw|$running|$max_agents|$is_done"
}

# Main monitoring loop
START_TIME=$(date +%s)
DURATION_SECONDS=$((DURATION_MINUTES * 60))

echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║          WOS Cycle Progress Monitor                          ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Output file:${NC} $OUTPUT_FILE"
echo -e "${CYAN}Duration:${NC} $DURATION_MINUTES minutes"
echo ""

# Initial wait for cycle to start
echo "Waiting for cycle to start..."
while [ ! -s "$OUTPUT_FILE" ] && [ $(($(date +%s) - START_TIME)) -lt 30 ]; do
    sleep 1
done

clear

while true; do
    # Calculate elapsed time
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    REMAINING=$((DURATION_SECONDS - ELAPSED))

    # Extract metrics
    IFS='|' read -r completed failed checkpoints util running max_agents is_done <<< "$(extract_metrics "$OUTPUT_FILE")"

    # Calculate progress (based on time)
    PROGRESS=$((ELAPSED * 100 / DURATION_SECONDS))
    if [ $PROGRESS -gt 100 ]; then
        PROGRESS=100
    fi

    # Clear screen and draw dashboard
    clear
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║          WOS Cycle Progress Monitor                          ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Time progress
    echo -e "${CYAN}${BOLD}Time Progress:${NC}"
    echo -ne "  "
    draw_progress_bar $PROGRESS
    echo -e " ${BOLD}${PROGRESS}%${NC}"
    echo ""
    echo -e "  ${GRAY}Elapsed:${NC}   $(format_duration $ELAPSED)"
    if [ $REMAINING -gt 0 ]; then
        echo -e "  ${GRAY}Remaining:${NC} $(format_duration $REMAINING)"
    else
        echo -e "  ${YELLOW}Overtime:${NC}  $(format_duration $((ELAPSED - DURATION_SECONDS)))"
    fi
    echo ""

    # Work items progress
    echo -e "${CYAN}${BOLD}Work Items:${NC}"
    total=$((completed + failed))
    if [ $total -gt 0 ]; then
        success_rate=$((completed * 100 / total))
    else
        success_rate=0
    fi
    echo -e "  ${GREEN}Completed:${NC} $completed"
    echo -e "  ${YELLOW}Failed:${NC}    $failed"
    echo -e "  ${GRAY}Success:${NC}   ${success_rate}%"
    echo ""

    # Checkpoints
    echo -e "${CYAN}${BOLD}Checkpoints:${NC}"
    echo -e "  ${GRAY}Completed:${NC} $checkpoints"
    echo ""

    # Agent utilization
    echo -e "${CYAN}${BOLD}Agent Status:${NC}"
    echo -e "  ${GRAY}Running:${NC}      $running / $max_agents agents"
    echo -e "  ${GRAY}Utilization:${NC}  ${util}%"

    # Utilization bar
    echo -ne "  "
    draw_progress_bar $util
    echo ""
    echo ""

    # Estimated completion
    if [ $total -gt 0 ] && [ $ELAPSED -gt 0 ] && [ $REMAINING -gt 0 ]; then
        # Estimate work items per minute
        items_per_min=$(echo "scale=2; $total * 60 / $ELAPSED" | bc)
        estimated_total=$(echo "scale=0; $items_per_min * $DURATION_MINUTES / 1" | bc)
        echo -e "${CYAN}${BOLD}Estimates:${NC}"
        echo -e "  ${GRAY}Rate:${NC}           $items_per_min items/min"
        echo -e "  ${GRAY}Projected Total:${NC} ~$estimated_total work items"
        echo ""
    fi

    # Status indicator
    if [ $is_done -eq 1 ]; then
        echo -e "${GREEN}${BOLD}✓ CYCLE COMPLETE${NC}"
        echo ""
        echo "Final results:"
        echo "  Total work items: $total"
        echo "  Success rate: ${success_rate}%"
        echo "  Duration: $(format_duration $ELAPSED)"
        echo ""
        break
    else
        echo -e "${BLUE}${BOLD}◉ CYCLE IN PROGRESS${NC}"
        echo ""
        echo -e "${GRAY}Refreshing in $REFRESH_INTERVAL seconds... (Ctrl+C to exit)${NC}"
    fi

    # Wait before next refresh
    sleep $REFRESH_INTERVAL
done

# Show final output location
echo ""
echo "Full output available at: $OUTPUT_FILE"
echo ""
echo "To view cycle status:"
echo "  wos cycle status"
echo ""
echo "To view journal report:"
echo "  wos journal report"

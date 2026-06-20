#!/usr/bin/env bash
#
# Workspace OS Quickstart Demo
#
# This script demonstrates the basic workflow documented in the Getting Started guide.
# Run this after installing workspace-os to see the system in action.
#

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Workspace OS Quickstart Demo ===${NC}\n"

# Check if workspace command is available
if ! command -v workspace &> /dev/null; then
    echo -e "${YELLOW}Warning: 'workspace' command not found.${NC}"
    echo "Please install with: pip install -e ."
    echo "Or use: python -m workspace_os"
    exit 1
fi

# Use the example config or local config if it exists
if [ -f "config/workspace.sources.local.json" ]; then
    CONFIG="config/workspace.sources.local.json"
    echo -e "${GREEN}Using local configuration: ${CONFIG}${NC}\n"
else
    CONFIG="config/workspace.sources.example.json"
    echo -e "${YELLOW}Using example configuration: ${CONFIG}${NC}"
    echo "Consider creating config/workspace.sources.local.json for your environment"
    echo ""
fi

# Demo Step 1: Status
echo -e "${BLUE}Step 1: Check workspace status${NC}"
echo "Command: workspace --config ${CONFIG} status"
echo ""
workspace --config "${CONFIG}" status
echo ""

# Demo Step 2: Search
echo -e "${BLUE}Step 2: Search across sources${NC}"
echo "Command: workspace --config ${CONFIG} search 'agent'"
echo ""
workspace --config "${CONFIG}" search "agent" --max-results 5
echo ""

# Demo Step 3: Classify
echo -e "${BLUE}Step 3: Classify content${NC}"
echo "Command: workspace classify 'Agents must validate scripts before release.'"
echo ""
workspace classify "Agents must validate scripts before release."
echo ""

# Demo Step 4: Context
echo -e "${BLUE}Step 4: Build context for a task${NC}"
echo "Command: workspace --config ${CONFIG} context 'testing' --max-matches 3"
echo ""
workspace --config "${CONFIG}" context "testing" --max-matches 3
echo ""

# Demo Step 5: Validate
echo -e "${BLUE}Step 5: Validate workspace${NC}"
echo "Command: workspace --config ${CONFIG} validate --skip-housekeeping"
echo ""
workspace --config "${CONFIG}" validate --skip-housekeeping
echo ""

# Demo Step 6: Housekeeping
echo -e "${BLUE}Step 6: Check for temporary artifacts${NC}"
echo "Command: workspace --config ${CONFIG} housekeeping --max-results 5"
echo ""
workspace --config "${CONFIG}" housekeeping --max-results 5
echo ""

echo -e "${GREEN}=== Demo Complete ===${NC}\n"
echo "Next steps:"
echo "  1. Review docs/GETTING_STARTED.md for detailed guidance"
echo "  2. Create your own config/workspace.sources.local.json"
echo "  3. Try capturing a session: workspace capture --help"
echo "  4. Explore the web interface: workspace web"
echo ""

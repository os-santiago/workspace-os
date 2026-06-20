# Workspace OS Quickstart Demo (PowerShell)
#
# This script demonstrates the basic workflow documented in the Getting Started guide.
# Run this after installing workspace-os to see the system in action.
#

$ErrorActionPreference = "Stop"

Write-Host "=== Workspace OS Quickstart Demo ===" -ForegroundColor Blue
Write-Host ""

# Check if workspace command is available
try {
    Get-Command workspace -ErrorAction Stop | Out-Null
} catch {
    Write-Host "Warning: 'workspace' command not found." -ForegroundColor Yellow
    Write-Host "Please install with: pip install -e ."
    Write-Host "Or use: python -m workspace_os"
    exit 1
}

# Use the example config or local config if it exists
if (Test-Path "config/workspace.sources.local.json") {
    $Config = "config/workspace.sources.local.json"
    Write-Host "Using local configuration: $Config" -ForegroundColor Green
    Write-Host ""
} else {
    $Config = "config/workspace.sources.example.json"
    Write-Host "Using example configuration: $Config" -ForegroundColor Yellow
    Write-Host "Consider creating config/workspace.sources.local.json for your environment"
    Write-Host ""
}

# Demo Step 1: Status
Write-Host "Step 1: Check workspace status" -ForegroundColor Blue
Write-Host "Command: workspace --config $Config status"
Write-Host ""
workspace --config $Config status
Write-Host ""

# Demo Step 2: Search
Write-Host "Step 2: Search across sources" -ForegroundColor Blue
Write-Host "Command: workspace --config $Config search 'agent' --max-results 5"
Write-Host ""
workspace --config $Config search "agent" --max-results 5
Write-Host ""

# Demo Step 3: Classify
Write-Host "Step 3: Classify content" -ForegroundColor Blue
Write-Host "Command: workspace classify 'Agents must validate scripts before release.'"
Write-Host ""
workspace classify "Agents must validate scripts before release."
Write-Host ""

# Demo Step 4: Context
Write-Host "Step 4: Build context for a task" -ForegroundColor Blue
Write-Host "Command: workspace --config $Config context 'testing' --max-matches 3"
Write-Host ""
workspace --config $Config context "testing" --max-matches 3
Write-Host ""

# Demo Step 5: Validate
Write-Host "Step 5: Validate workspace" -ForegroundColor Blue
Write-Host "Command: workspace --config $Config validate --skip-housekeeping"
Write-Host ""
workspace --config $Config validate --skip-housekeeping
Write-Host ""

# Demo Step 6: Housekeeping
Write-Host "Step 6: Check for temporary artifacts" -ForegroundColor Blue
Write-Host "Command: workspace --config $Config housekeeping --max-results 5"
Write-Host ""
workspace --config $Config housekeeping --max-results 5
Write-Host ""

Write-Host "=== Demo Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Review docs/GETTING_STARTED.md for detailed guidance"
Write-Host "  2. Create your own config/workspace.sources.local.json"
Write-Host "  3. Try capturing a session: workspace capture --help"
Write-Host "  4. Explore the web interface: workspace web"
Write-Host ""

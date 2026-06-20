# Workspace OS Examples

This directory contains example scripts and configurations to help you get started with Workspace OS.

## Quickstart Demos

### Bash/Zsh (Linux, macOS, Git Bash on Windows)

```bash
chmod +x examples/quickstart_demo.sh
./examples/quickstart_demo.sh
```

### PowerShell (Windows)

```powershell
.\examples\quickstart_demo.ps1
```

### What the Demo Shows

The quickstart demo walks through the basic workflow:

1. **Status** - Check the health of all configured repositories
2. **Search** - Find content across all workspace sources
3. **Classify** - Determine where content belongs in your workspace model
4. **Context** - Build a governed context pack for agent work
5. **Validate** - Run validation checks across sources
6. **Housekeeping** - Find temporary artifacts

## Available Examples

### progress_demo.py

Demonstrates the progress bar and ETA functionality added for long-running commands.

**Usage:**
```bash
python examples/progress_demo.py
```

**Features demonstrated:**
- Simple progress bar with percentage and ETA
- Indeterminate progress (spinner for unknown totals)
- Batch progress tracking (multiple concurrent operations)
- Dynamic total (discovered during execution)
- Custom configuration options
- Real-world validation scenario

**Requirements:**
- `rich` library (installed automatically with workspace-os)

**Expected output:**
The script runs 6 different demo scenarios showing various progress tracking patterns. Each demo includes:
- Visual progress bars
- Percentage complete
- Estimated time remaining
- Time elapsed
- Spinner animations for indeterminate operations

## Configuration Examples

### Minimal Configuration

The simplest possible configuration with just Workspace OS itself:

```json
{
  "sources": [
    {
      "name": "workspace-os",
      "type": "product",
      "responsibility": "Product roadmap, architecture, and workspace controller implementation.",
      "path": ".",
      "search": true
    }
  ]
}
```

### Full Configuration

A complete configuration with all repository types:

```json
{
  "sources": [
    {
      "name": "adev",
      "type": "doctrine",
      "responsibility": "Operating doctrine, validation standards, and delivery guardrails.",
      "path": "/path/to/adev",
      "search": true
    },
    {
      "name": "scanales-kb",
      "type": "evidence",
      "responsibility": "Sanitized evidence, implementation notes, decisions, and verified lessons.",
      "path": "/path/to/scanales-knowledge-base",
      "search": true
    },
    {
      "name": "homedir",
      "type": "execution",
      "responsibility": "Local workstation automation, scripts, and execution assets.",
      "path": "/path/to/homedir",
      "search": true
    },
    {
      "name": "workspace-os",
      "type": "product",
      "responsibility": "Product roadmap, architecture, and workspace controller implementation.",
      "path": ".",
      "search": true
    }
  ]
}
```

## Common Usage Patterns

### Daily Workflow

```bash
# Morning: Check workspace status
workspace status

# Search for related work before starting
workspace search "topic"

# Build context for agent delegation
workspace context "task description"

# Do your work...

# Evening: Capture learnings
workspace capture --type session --title "Daily work" --text "Today I learned..." --write

# Validate before committing
workspace validate
```

### Agent Delegation

```bash
# 1. Build context
workspace context "implement feature X" > context.md

# 2. Share context.md with your AI assistant

# 3. After agent completes work, capture the session
workspace capture --type session \
  --title "Agent implemented feature X" \
  --text "Agent successfully implemented feature X with tests." \
  --write

# 4. Promote reusable patterns to doctrine
workspace promote \
  --to adev \
  --rule "Feature implementations must include integration tests." \
  --evidence "scanales-kb:sessions/2024-06-15.md"
```

### Before Deliverables

```bash
# Run full validation
workspace validate

# Check for cleanup needed
workspace housekeeping

# Search for similar work
workspace search "delivery topic"

# Classify new content
workspace classify --path docs/new-content.md
```

## Advanced Examples

### Using Environment Variables

```bash
# Set default config
export WORKSPACE_CONFIG=config/workspace.sources.local.json

# Now commands work without --config
workspace status
workspace search "query"
```

### Shell Alias

Add to `.bashrc` or `.zshrc`:

```bash
alias wos='workspace --config config/workspace.sources.local.json'
```

Usage:

```bash
wos status
wos search "query"
wos validate
```

### Programmatic Usage

You can also use Workspace OS from Python:

```python
from pathlib import Path
from workspace_os.config import load_sources
from workspace_os.search import search_sources

# Load configuration
config_path = Path("config/workspace.sources.local.json")
sources = load_sources(config_path)

# Search
matches = search_sources(
    sources=sources,
    query="agent",
    max_results=10
)

for match in matches:
    print(f"{match.source_name}:{match.path}:{match.line_number}")
```

## Running Examples

All examples can be run directly from the repository root:

```bash
# Install workspace-os in development mode
pip install -e .

# Run an example
python examples/progress_demo.py
```

## Next Steps

After running the quickstart demo:

1. Review [Getting Started Guide](../docs/GETTING_STARTED.md)
2. Create your own `config/workspace.sources.local.json`
3. Explore the web interface with `workspace web`
4. Read the [Product Vision](../docs/product/vision.md)
5. Check the [Roadmap](../docs/product/roadmap.md)

## Adding New Examples

When adding new example scripts:

1. Create the script in this directory
2. Add appropriate documentation header
3. Include usage instructions
4. Update this README
5. Test the example in a clean environment

## Troubleshooting

See the [Troubleshooting section](../docs/GETTING_STARTED.md#troubleshooting) in the Getting Started guide.

## See Also

- [Progress Tracking Documentation](../docs/features/progress-tracking.md)
- [Progress Module Source](../src/workspace_os/progress.py)
- [Progress Tests](../tests/test_progress.py)

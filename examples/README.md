# Workspace OS Examples

This directory contains example scripts and demonstrations of Workspace OS features.

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

## Running Examples

All examples can be run directly from the repository root:

```bash
# Install workspace-os in development mode
pip install -e .

# Run an example
python examples/progress_demo.py
```

## Adding New Examples

When adding new example scripts:

1. Create the script in this directory
2. Add appropriate documentation header
3. Include usage instructions
4. Update this README
5. Test the example in a clean environment

## See Also

- [Progress Tracking Documentation](../docs/features/progress-tracking.md)
- [Progress Module Source](../src/workspace_os/progress.py)
- [Progress Tests](../tests/test_progress.py)

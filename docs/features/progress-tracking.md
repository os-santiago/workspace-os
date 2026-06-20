# Progress Tracking and ETA

This document describes the progress bar and ETA (Estimated Time to Arrival) features added to Workspace OS for all long-running commands.

## Overview

Workspace OS now provides visual progress indicators with percentage complete and estimated time remaining for all long-running operations. This includes:

- **Validation** (`workspace validate`)
- **Search** (`workspace search`)
- **Housekeeping** (`workspace housekeeping`)
- **Cycle operations** (future integration with `workspace cycle run`, `workspace cycle work`)
- **Context building** (`workspace context`)

## Features

### Visual Progress Bars

- **Determinate Progress**: Shows a progress bar when the total number of steps is known
- **Indeterminate Progress**: Shows a spinner when the total is unknown
- **Multi-task Progress**: Displays multiple concurrent operations with individual progress bars

### ETA Calculation

- Automatically calculates estimated time remaining based on work completed
- Updates dynamically as operations progress
- Shows time elapsed for completed operations

### Rich Terminal UI

Built on the [Rich](https://github.com/Textualize/rich) library, providing:

- Smooth, non-flickering progress bars
- Color-coded status indicators
- Clean, professional terminal output
- Automatic terminal width detection

## Usage

### Basic Usage

Progress tracking is **enabled by default** for all long-running commands. No configuration is required.

```bash
# Validation with progress bar
workspace validate

# Search with progress tracking
workspace search "ADEV" --source-type doctrine

# Housekeeping scan with progress
workspace housekeeping
```

### Configuration

Progress display can be customized programmatically:

```python
from workspace_os.progress import configure_progress

# Disable progress bars entirely
configure_progress(enabled=False)

# Customize display options
configure_progress(
    show_eta=True,           # Show estimated time remaining
    show_percentage=True,    # Show percentage complete
    show_elapsed=True,       # Show elapsed time
    refresh_per_second=10    # Update frequency
)
```

### Programmatic Usage

For custom scripts and automation:

```python
from workspace_os.progress import progress

# Simple progress tracking
with progress("Processing items", total=100) as tracker:
    for i in range(100):
        # Do work
        process_item(i)
        # Update progress
        tracker.update()

# Indeterminate progress (unknown total)
with progress("Searching files") as tracker:
    for file in find_files():
        process_file(file)
        tracker.update()

# Dynamic total (discovered during execution)
with progress("Scanning workspace") as tracker:
    files = discover_files()
    tracker.set_total(len(files))
    for file in files:
        process_file(file)
        tracker.update()
```

### Batch Progress Tracking

For operations with multiple concurrent tasks:

```python
from workspace_os.progress import batch_progress

with batch_progress() as tracker:
    # Add tasks
    tracker.add_task("validation", "Validating sources", total=10)
    tracker.add_task("search", "Searching files", total=50)
    
    # Update tasks as work progresses
    for i in range(10):
        validate_source(i)
        tracker.update("validation")
    
    for i in range(50):
        search_file(i)
        tracker.update("search")
    
    # Mark tasks complete
    tracker.complete("validation")
    tracker.complete("search")
```

## Implementation Details

### Architecture

The progress tracking system consists of:

1. **ProgressTracker**: Manages single progress bars
2. **BatchProgressTracker**: Manages multiple concurrent progress bars
3. **SimpleProgressLogger**: Fallback when Rich is not available
4. **ProgressConfig**: Global configuration settings

### Graceful Degradation

- If the `rich` library is not installed, operations continue without progress bars
- A simple text-based logger provides periodic updates as a fallback
- All commands work normally even when progress display is disabled

### Performance Impact

- Minimal overhead: progress updates are throttled to configurable refresh rates
- Non-blocking: progress updates don't slow down operations
- Memory efficient: only tracks current state, not full history

## Integration with Commands

### Validation (`workspace validate`)

Shows progress through:
1. Source registry check
2. Individual source validation (one bar per source)
3. Housekeeping check

### Search (`workspace search`)

Shows progress through:
1. Number of sources searched
2. Current source being searched
3. Real-time match count

### Housekeeping (`workspace housekeeping`)

Shows progress through:
1. Number of patterns checked
2. Current source and pattern being scanned
3. Real-time finding count

### Cycle Operations (future)

Progress tracking is designed to support:
- `workspace cycle run`: Shows iteration progress, checkpoint status
- `workspace cycle work`: Displays agent work item progress
- Checkpoint validation: Shows gate checks (health, stability, security, quality)

## Examples

### Example 1: Validation

```bash
$ workspace validate
⠋ Checking source registry                    ━━━━━━━━━━━━━━━━━━━━━━━━━━ 1/5  20%  ⏱ 0:00:02 ⏳ 0:00:08
```

### Example 2: Search

```bash
$ workspace search "agent alignment" --source-type doctrine
⠙ Searching ADEV                               ━━━━━━━━━━━━━━━━━━━━━━━━━━ 2/4  50%  ⏱ 0:00:03 ⏳ 0:00:03
```

### Example 3: Housekeeping

```bash
$ workspace housekeeping
⠹ Checking workspace-os for *.tmp              ━━━━━━━━━━━━━━━━━━━━━━━━━━ 15/40 38%  ⏱ 0:00:05 ⏳ 0:00:08
```

### Example 4: Batch Operations

```bash
$ workspace cycle run --iterations 5
⠸ Validation                                   ━━━━━━━━━━━━━━━━━━━━━━━━━━ 3/5  60%  ⏱ 0:00:12 ⏳ 0:00:08
⠼ Checkpoint evaluation                        ━━━━━━━━━━━━━━━━━━━━━━━━━━ 3/5  60%  ⏱ 0:00:12 ⏳ 0:00:08
⠴ Quality checks                                ━━━━━━━━━━━━━━━━━━━━━━━━━━ 2/4  50%  ⏱ 0:00:08 ⏳ 0:00:08
```

## Testing

Run the included demo script to see all progress bar features:

```bash
python examples/progress_demo.py
```

Run the test suite:

```bash
pytest tests/test_progress.py -v
```

## Troubleshooting

### Progress bars not showing

1. Check if Rich is installed: `pip install rich`
2. Verify progress is enabled: `python -c "from workspace_os.progress import is_progress_enabled; print(is_progress_enabled())"`
3. Check terminal compatibility: Rich requires a terminal that supports ANSI escape codes

### Terminal output garbled

- Some terminals may not support all Rich features
- Try updating your terminal emulator
- Disable progress: `configure_progress(enabled=False)`

### Performance issues

- Reduce refresh rate: `configure_progress(refresh_per_second=5)`
- Disable ETA calculation: `configure_progress(show_eta=False)`

## Future Enhancements

Planned improvements:

- [ ] Integration with `workspace cycle run` command
- [ ] Integration with `workspace cycle work` command
- [ ] Checkpoint progress visualization
- [ ] Agent work queue progress tracking
- [ ] Export progress data for analysis
- [ ] Web UI progress streaming
- [ ] Custom progress themes

## References

- [Rich Documentation](https://rich.readthedocs.io/)
- [Issue #52: Add progress bars and ETA](https://github.com/your-org/workspace-os/issues/52)
- [Progress Module Source](../../src/workspace_os/progress.py)
- [Progress Tests](../../tests/test_progress.py)

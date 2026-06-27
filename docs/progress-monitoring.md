# WOS Cycle Progress Monitoring

Beautiful real-time visualization of WOS cycle progress with animated terminal dashboard.

## Web Dashboard

The local web app now exposes a live cycle monitor at `/api/cycle-monitor` and a WebSocket feed at `/api/cycle-monitor/ws`.

- Shows the active or latest cycle
- Streams checkpoint history and pass/fail gate status
- Surfaces agent utilization and the next recommended action
- Falls back to polling if WebSocket support is unavailable

Open the main UI and keep the cycle monitor panel visible to watch a run in real time.

## Features

### 🎨 Animated Dashboard

- **Real-time progress bar** - Visual time and completion tracking
- **Live metrics** - Work items, success rate, agent utilization
- **Smooth animations** - Spinners, pulse effects, and wave animations
- **Color-coded status** - Easy to see at a glance
- **Squad Lead indicators** - Shows when Squad Lead mode is active

### 📊 Metrics Displayed

1. **Time Progress**
   - Elapsed time
   - Remaining time
   - Progress percentage with color-coded bar

2. **Work Items**
   - Completed count
   - Failed count
   - Success rate percentage
   - Current work item number

3. **Agent Status**
   - Active agents (X/Y)
   - Queue utilization percentage
   - Visual utilization bar

4. **Quality Gates**
   - Checkpoints completed
   - Visual checkpoint indicators (●○○○○)

5. **Projections**
   - Items per minute rate
   - Projected total work items

## Quick Start

### Option 1: Run with Automatic Monitoring (Recommended)

The easiest way - launches cycle and shows animated progress automatically:

```bash
cd /d/git/workspace-os
./scripts/run-squad-lead-with-monitor.sh [duration_minutes]
```

**Example**:
```bash
# 45-minute improvement cycle with live monitoring
./scripts/run-squad-lead-with-monitor.sh 45
```

This will:
1. ✓ Configure Squad Lead mode
2. ✓ Start WOS cycle in background
3. ✓ Show beautiful animated progress dashboard
4. ✓ Display final results when complete

### Option 2: Monitor Existing Cycle

If you already have a cycle running in background:

```bash
# Python animated monitor (recommended)
python scripts/monitor-cycle-animated.py <output_file> [duration_minutes]

# Bash text monitor (fallback)
bash scripts/monitor-cycle-progress.sh <output_file> [duration_minutes]
```

**Example**:
```bash
# Monitor a running cycle
python scripts/monitor-cycle-animated.py /tmp/wos-cycle.output 45
```

## Dashboard Preview

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 WOS Cycle Progress Monitor 🚀                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

  ⠋ Status: RUNNING

  ⏱️  Time Progress
  [████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 42%
  Elapsed:   19m 05s
  Remaining: 25m 55s

  📊 Work Items
  ┌────────────────────────────────────────────────────────────┐
  │ ✓ Completed:  32  ✗ Failed:   2  Success:  94% │
  │ ◐ Current work item: #28                                │
  └────────────────────────────────────────────────────────────┘

  🤖 Agent Status
  [███████████████████████████████████████░░░░░░░░] 88%
  Active Agents: 14/16  Utilization: 88%
  🎯 Squad Lead Mode: ACTIVE

  🎯 Quality Gates
  ●●●○○  3 checkpoints completed

  📈 Projections
  Rate:           1.7 items/min
  Projected Total: ~76 work items

  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄

  Press Ctrl+C to exit monitor (cycle continues in background)
```

## Animation Elements

### 🎭 Visual Indicators

| Element | Meaning |
|---------|---------|
| ⠋⠙⠹⠸⠼⠴⠦⠧ | Spinner - cycle is running |
| ◐◓◑◒ | Pulse - current work item |
| ▁▂▃▄▅▆▇█ | Wave - activity indicator |
| ●○○○○ | Checkpoint progress |
| █░ | Progress bars (filled/empty) |

### 🎨 Color Coding

| Color | Meaning |
|-------|---------|
| 🟢 Green | Good (>70% progress, high success rate) |
| 🟡 Yellow | Warning (30-70% progress, moderate success) |
| 🔴 Red | Critical (<30% progress, low success) |
| 🔵 Blue | Info (running status) |
| ⚪ Gray | Neutral (labels, timestamps) |

## Features by Monitor Type

### Python Animated Monitor (`monitor-cycle-animated.py`)

**Pros**:
- ✓ Beautiful animations and colors
- ✓ Smooth updates (500ms refresh)
- ✓ Rich metrics and projections
- ✓ Squad Lead mode detection
- ✓ Clean, professional dashboard

**Requirements**:
- Python 3.x
- Terminal with ANSI color support

### Bash Text Monitor (`monitor-cycle-progress.sh`)

**Pros**:
- ✓ Works anywhere with bash
- ✓ No Python dependency
- ✓ Simple and reliable
- ✓ Good for headless environments

**Refresh**: 5 seconds

## Usage Examples

### Example 1: Quick Test Run

```bash
# 15-minute test with monitoring
./scripts/run-squad-lead-with-monitor.sh 15
```

### Example 2: Full Production Run

```bash
# 45-minute improvement cycle
./scripts/run-squad-lead-with-monitor.sh 45
```

### Example 3: Extended Session

```bash
# 90-minute deep improvement session
./scripts/run-squad-lead-with-monitor.sh 90
```

### Example 4: Monitor Existing Cycle

```bash
# Start cycle in background manually
python -m workspace_os cycle work --duration-minutes 45 > /tmp/wos.output 2>&1 &

# Then monitor it
python scripts/monitor-cycle-animated.py /tmp/wos.output 45
```

## Keyboard Controls

| Key | Action |
|-----|--------|
| Ctrl+C | Exit monitor (cycle continues) |

**Note**: Exiting the monitor does NOT stop the cycle. The cycle continues running in the background.

## Monitoring Multiple Cycles

To monitor multiple cycles, use different output files:

```bash
# Terminal 1
./scripts/run-squad-lead-with-monitor.sh 45

# Terminal 2 (different workspace)
cd /path/to/other/workspace
python -m workspace_os cycle work --duration-minutes 30 > /tmp/wos2.output 2>&1 &
python /d/git/workspace-os/scripts/monitor-cycle-animated.py /tmp/wos2.output 30
```

## Troubleshooting

### Monitor shows "Waiting for cycle to start..."

**Cause**: Output file is empty or doesn't exist yet.

**Solution**: 
- Wait a few seconds for cycle to initialize
- Verify output file path is correct
- Check if cycle started successfully

### No colors/animations

**Cause**: Terminal doesn't support ANSI colors.

**Solution**: 
- Use modern terminal (Windows Terminal, iTerm2, etc.)
- Or fall back to bash monitor: `./scripts/monitor-cycle-progress.sh`

### Python not found

**Cause**: Python not installed or not in PATH.

**Solution**: 
- Install Python 3.x
- Or use bash monitor: `./scripts/monitor-cycle-progress.sh`

### Monitor exits immediately

**Cause**: Cycle already completed.

**Solution**: 
- Check cycle status: `wos cycle status`
- View output file directly: `cat <output_file>`

## Integration with Scripts

You can integrate the monitor into your own scripts:

```bash
#!/usr/bin/env bash

# Start WOS cycle
OUTPUT="/tmp/wos-${TIMESTAMP}.output"
python -m workspace_os cycle work --duration-minutes 45 > "$OUTPUT" 2>&1 &
CYCLE_PID=$!

# Monitor progress
python /d/git/workspace-os/scripts/monitor-cycle-animated.py "$OUTPUT" 45

# Wait for completion
wait $CYCLE_PID

# Analyze results
wos cycle status
```

## Advanced Configuration

### Custom Refresh Rate

Edit `monitor-cycle-animated.py`:

```python
# Change from 0.5 to desired seconds
time.sleep(0.5)  # Update every 500ms
```

### Custom Animations

Edit the animation frames:

```python
SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
PULSE_FRAMES = ['◐', '◓', '◑', '◒']
WAVE_FRAMES = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
```

## Performance Impact

**Monitor overhead**: Negligible
- CPU: <1% (reading log file every 500ms)
- Memory: <10MB
- No impact on WOS cycle performance

**Log file growth**: 
- ~1-2MB per 45-minute cycle
- Automatically managed by WOS

## See Also

- [Squad Lead Mode](squad-lead-mode.md) - Intelligent agent coordination
- [World-Class Team Profile](world-class-team-profile.md) - Operating principles
- [High-Throughput Guide](runbooks/high-throughput-issue-resolution.md) - Performance optimization

---

**Pro Tip**: Run monitor in a dedicated terminal tab for best experience. Leave it running while you work on other tasks - you can glance at it to see progress without interrupting your flow.

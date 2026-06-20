# WOS Squad Lead Mode

## Overview

Squad Lead Mode transforms WOS from simple round-robin agent assignment into an intelligent squad coordinator that:

1. **Maximizes agent utilization** - Keeps agents busy through load balancing and dynamic rebalancing
2. **Coordinates agents as a team** - Agents share context about recent work and learn from each other
3. **Rotates responsibilities** - Agents cycle through primary, cross-check, and observer roles
4. **Integrates feedback and learning** - Performance history guides agent selection
5. **Adapts strategy** - Learns which agents perform best for specific task types

## Quick Start

Enable Squad Lead Mode with environment variables:

```bash
export WOS_SQUAD_LEAD_MODE=true
export WOS_ROLE_ROTATION_CYCLE=9
export WOS_SQUAD_CONTEXT_WINDOW=5
export WOS_DYNAMIC_REBALANCING=true
```

Then run a cycle:

```bash
wos cycle work --duration-minutes 30 --label squad-lead-test
```

## Features

### 1. Intelligent Agent Selection

Instead of simple round-robin, Squad Lead Mode:

- **Uses performance history**: Recommends agents based on past success rates
- **Balances queue load**: Distributes work to less-loaded agents
- **Adapts by role**: Different selection logic for primary vs cross-check vs observer

**Implementation**: `_squad_lead_choose_agent_and_role()` in `cycle.py`

### 2. Role Rotation

Agents rotate through three roles over a 9-work-item cycle:

- **Primary (work items 3,6,9,...)**: Lead implementation, focus on getting it done
- **Cross-check (work items 1,4,7,...)**: Review recent work, verify correctness
- **Observer (work items 2,5,8,...)**: Provide feedback, identify patterns

This ensures diverse perspectives and continuous improvement.

**Example rotation**:
```
Work item 1: claude (cross-check)
Work item 2: antigravity (observer)  
Work item 3: opencode (primary)
Work item 4: opencode (cross-check)
Work item 5: claude (observer)
Work item 6: antigravity (primary)
...
```

### 3. Inter-Agent Context Sharing

Agents receive summaries of recent teammate work:

```
Recent team activity:
- opencode (primary) completed work item 5 in 45.2s
- claude (cross-check) completed work item 6 in 32.1s
- antigravity (observer) completed work item 7 in 28.5s
```

This creates squad awareness and prevents duplicate effort.

**Configuration**: `WOS_SQUAD_CONTEXT_WINDOW` (default: 5 items)

### 4. Dynamic Queue Rebalancing

Adjusts batch sizes based on current utilization:

- **Low utilization (<30%)**: Fill queue aggressively
- **Medium (30-70%)**: Gradual fill
- **High (>70%)**: One at a time to avoid overwhelming

This keeps agents busy without overloading the queue.

**Configuration**: `WOS_DYNAMIC_REBALANCING=true` (default: enabled)

### 5. Performance-Based Learning

At each checkpoint, WOS:

1. Analyzes recent agent performance from queue tracker
2. Records feedback for failed tasks
3. Updates performance metrics
4. Uses metrics for future agent selection

**Implementation**: `update_agent_performance_from_queue()` in `learning.py`

### 6. Squad-Aware Logging

Enhanced logging shows team coordination:

```
[squad] Agent opencode assigned to role 'primary' for work item 10 | 
        team: [opencode=2, claude=1, antigravity=3] | 
        queue: 6/16 (38% util)

[squad] Health @ 450s: team [opencode=3, claude=2, antigravity=1] | 
        75% util | 45 done, 2 failed | 
        perf: claude: 92% success, 38s avg | opencode: 88% success, 42s avg
```

## Configuration Reference

### WOS_SQUAD_LEAD_MODE

**Default**: `false` (disabled for backward compatibility)

**Values**: `true` | `false`

Enable all Squad Lead features. When disabled, falls back to simple round-robin.

### WOS_ROLE_ROTATION_CYCLE

**Default**: `9`

**Values**: Any positive integer (recommend 9 = 3 agents × 3 roles)

Work items per full rotation cycle.

### WOS_SQUAD_CONTEXT_WINDOW

**Default**: `5`

**Values**: Positive integer

Number of recent work summaries to share with agents.

### WOS_DYNAMIC_REBALANCING

**Default**: `true`

**Values**: `true` | `false`

Enable dynamic batch sizing based on queue utilization.

## Performance Impact

### Expected Improvements

**Utilization**:
- Baseline: 50-60% success rate, agents chosen randomly
- Squad Lead: 70-80% success rate, intelligent selection
- Idle ratio: <20% (down from 81% in early versions)

**Learning**:
- Agents learn from performance history
- Better agent-task matching over time
- Continuous feedback loop

**Quality**:
- Cross-check roles catch issues before checkpoints
- Observer roles identify process improvements
- Diverse perspectives reduce blind spots

### Metrics to Track

Monitor these in WOS output:

- Success rate per agent
- Average work item duration per agent
- Queue utilization over time
- Idle ratio improvement
- PRs created per hour

## Testing

Run the test suite:

```bash
cd /d/git/workspace-os
python test_squad_lead.py
```

Tests verify:
- Role rotation logic
- Environment variable configuration
- Context window management
- Prompt role integration

## Implementation Details

### Files Modified

1. **`src/workspace_os/cycle.py`**
   - `_choose_continuous_work_item()`: Added squad lead mode check and queue_tracker parameter
   - `_squad_lead_choose_agent_and_role()`: New intelligent selection function
   - `_build_cycle_work_prompt()`: Added role and recent_work parameters
   - Continuous mode loop: Added context tracking and squad-aware logging
   - Checkpoint logic: Added performance learning updates

2. **`src/workspace_os/learning.py`**
   - `update_agent_performance_from_queue()`: New function to learn from queue tracker

3. **`test_squad_lead.py`**
   - Test suite for squad lead features

4. **`docs/squad-lead-mode.md`**
   - This documentation

### Backward Compatibility

All changes are **opt-in** via `WOS_SQUAD_LEAD_MODE`:
- Default behavior unchanged (simple round-robin)
- Existing tests continue to pass
- Gradual migration path for users

## Troubleshooting

### Squad Lead mode not activating

Check environment variable:
```bash
echo $WOS_SQUAD_LEAD_MODE
```

Should output `true`. If not, export it:
```bash
export WOS_SQUAD_LEAD_MODE=true
```

### Performance not improving

1. Verify enough work items have completed for learning
2. Check queue utilization in logs (should be >70%)
3. Ensure agents are actually different (not all same agent)
4. Monitor success rates in squad health logs

### Excessive logging

Squad-aware logging only appears when `WOS_SQUAD_LEAD_MODE=true`. 

To reduce verbosity:
- Keep mode enabled but filter logs: `wos cycle work ... 2>&1 | grep -v "^\[squad\]"`
- Or disable mode: `export WOS_SQUAD_LEAD_MODE=false`

## Future Enhancements

Potential improvements (not yet implemented):

1. **Work stealing**: Observers can steal work from overloaded primaries
2. **Skill specialization**: Learn which agents excel at specific issue types
3. **Cross-agent feedback**: Agents directly critique each other's work
4. **Adaptive rotation**: Change rotation cycle based on team size
5. **Performance dashboards**: Web UI for real-time squad metrics

## See Also

- [High-Throughput Issue Resolution](runbooks/high-throughput-issue-resolution.md) - Throughput optimization guide
- [WOS Learning](../src/workspace_os/learning.py) - Agent performance tracking
- [Agent Policy](../src/workspace_os/agent_policy.py) - Agent selection logic
- [Agent Queue](../src/workspace_os/agent_queue.py) - Queue tracking

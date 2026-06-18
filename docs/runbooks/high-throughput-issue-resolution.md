# High-Throughput Issue Resolution with WOS

## Problem Statement

Default WOS cycle configuration generates 1-5 PRs per hour when resolving GitHub issues. For large issue backlogs, this is too slow.

**Goal**: Achieve 15-30 PRs per hour through optimized parallel agent orchestration.

## Root Causes of Low Throughput

### 1. Limited Parallelism
- **Default**: `max_workers = 2 * num_agents` (~6 workers)
- **Impact**: Only 6 tasks can run simultaneously
- **Fix**: Increase to 16-32 workers based on CPU cores

### 2. Frequent Checkpoints
- **Default**: Checkpoint every 5 minutes + 12 items
- **Impact**: Validation overhead blocks agent pool
- **Fix**: Checkpoint every 10 minutes + 24+ items

### 3. Issue Selection Overhead
- **Default**: Each agent chooses an issue from the list
- **Impact**: Decision overhead + risk of collisions
- **Fix**: Pre-assign specific issues to each agent with work stealing
  - Fresh issues are preferred
  - When issue count < worker count, allows multiple agents per issue
  - Prevents idle agents when work queue is dry

### 4. Auto-Healing Overhead
- **Default**: Up to 2 healing attempts per checkpoint failure
- **Impact**: Blocks cycle until healing completes
- **Fix**: Reduce to 1 healing attempt

## Quick Start

### Option 1: Using the Configuration Script

```bash
cd /d/git/workspace-os

# Run optimization script
source ./scripts/optimize-cycle-throughput.sh

# Navigate to target repository
cd /d/git/homedir

# Start high-throughput cycle
wos cycle work --continuous \
  --duration-minutes 60 \
  --label high-throughput-run-1 \
  --objective "Resolve GitHub issues with maximum throughput"
```

### Option 2: Manual Configuration

```bash
# Set environment variables
export WOS_MAX_WORKERS=16
export WOS_CHECKPOINT_INTERVAL_SECONDS=600
export WOS_MIN_ITEMS_PER_CHECKPOINT=24
export WOS_MAX_HEALING_ATTEMPTS=1
export WOS_ENABLE_ISSUE_ASSIGNMENT=true

# Start cycle
cd /d/git/homedir
wos cycle work --continuous --duration-minutes 60
```

## Configuration Reference

### WOS_MAX_WORKERS

**Controls**: Maximum parallel agent tasks

**Values**:
- `6` - Default (2x number of agents)
- `8-16` - Recommended for high throughput
- `24-32` - Maximum (requires powerful machine)

**Trade-offs**:
- Higher = more PRs/hour but higher CPU/memory usage
- Lower = more stable but slower throughput

**Recommendation**: `2 * CPU_CORES`, capped at 32

### WOS_CHECKPOINT_INTERVAL_SECONDS

**Controls**: Minimum time between checkpoints

**Values**:
- `300` - Default (5 minutes)
- `600` - Recommended for high throughput (10 minutes)
- `900` - Maximum (15 minutes, risky)

**Trade-offs**:
- Higher = less overhead, but issues detected later
- Lower = faster feedback, but more overhead

**Recommendation**: `600` (10 minutes)

### WOS_MIN_ITEMS_PER_CHECKPOINT

**Controls**: Minimum work items completed before checkpoint

**Values**:
- `12` - Default (2x default max_workers)
- `24` - Recommended for WOS_MAX_WORKERS=16
- `48` - For WOS_MAX_WORKERS=32

**Formula**: `2 * WOS_MAX_WORKERS`

**Recommendation**: Keep ratio at 2:1 with max_workers

### WOS_MAX_HEALING_ATTEMPTS

**Controls**: Auto-healing retries on checkpoint failure

**Values**:
- `2` - Default
- `1` - Recommended for high throughput
- `0` - Disable auto-healing (fast but risky)

**Trade-offs**:
- Lower = faster but may miss fixable issues
- Higher = more robust but slower

**Recommendation**: `1`

### WOS_ENABLE_ISSUE_ASSIGNMENT

**Controls**: Pre-assign specific issues to agents

**Values**:
- `true` - Recommended (default)
- `false` - Let agents choose (old behavior)

**Benefits when enabled**:
- Eliminates issue selection decision time
- Prevents multiple agents working on same issue
- Reduces prompt size (1 issue vs list of 20)

**Recommendation**: `true` (always)

## Performance Expectations

### Baseline (Default Configuration)
```
WOS_MAX_WORKERS=6
WOS_CHECKPOINT_INTERVAL_SECONDS=300
WOS_MIN_ITEMS_PER_CHECKPOINT=12
WOS_MAX_HEALING_ATTEMPTS=2
WOS_ENABLE_ISSUE_ASSIGNMENT=false
```

**Expected**: 1-5 PRs/hour (6 PRs/hour theoretical max)

### Optimized (Recommended Configuration)
```
WOS_MAX_WORKERS=16
WOS_CHECKPOINT_INTERVAL_SECONDS=600
WOS_MIN_ITEMS_PER_CHECKPOINT=24
WOS_MAX_HEALING_ATTEMPTS=1
WOS_ENABLE_ISSUE_ASSIGNMENT=true
```

**Expected**: 15-25 PRs/hour (30 PRs/hour theoretical max)

**Improvement**: 3-5x throughput increase

### Aggressive (Maximum Configuration)
```
WOS_MAX_WORKERS=32
WOS_CHECKPOINT_INTERVAL_SECONDS=900
WOS_MIN_ITEMS_PER_CHECKPOINT=48
WOS_MAX_HEALING_ATTEMPTS=1
WOS_ENABLE_ISSUE_ASSIGNMENT=true
```

**Expected**: 25-40 PRs/hour (50+ PRs/hour theoretical max)

**Requirements**: High-end machine (16+ cores, 32GB+ RAM)

**Risk**: Higher memory usage, potential stability issues

## Monitoring

### During Execution

Watch for these metrics in console output:

```
[cycle] Starting work item 23 (primary/opencode) | queue: 15/16 (94% util)
[cycle] Completed work item 19 (primary/claude) in 247.3s
[cycle] Queue health check @ 1234s: 15/16 agents busy (94% util), 8 done, 0 failed
```

**Key Indicators**:
- **Queue utilization**: Want >80% consistently
- **Agents busy**: Should be near max_workers
- **Failed count**: Should stay at 0 or very low

### After Completion

```bash
# View cycle report
wos cycle status

# View batch summary
wos batch summary

# Check journal
wos journal report
```

**Success Metrics**:
- `idle_ratio < 0.20` (< 20% idle time)
- `queue_utilization_ratio > 0.85` (> 85% utilized)
- `delegation_count > 40` for 1-hour run
- `quality_pass_rate > 0.90` (90%+ quality gate pass)

## Troubleshooting

### Low Queue Utilization (< 70%)

**Symptoms**: `[cycle] Queue health check: 4/16 agents busy (25% util)`

**Causes**:
- Issues running out (fewer than max_workers available)
- Agents failing early
- Git conflicts blocking checkouts

**Solutions**:
```bash
# Check available issues
cd /d/git/homedir && gh issue list | wc -l

# If < max_workers, reduce workers
export WOS_MAX_WORKERS=8

# Check for failures
wos cycle status | grep failed
```

### High Failure Rate (> 10%)

**Symptoms**: `[cycle] Queue health check: 16/16 busy, 20 done, 5 failed`

**Causes**:
- Quality gates too strict
- Auto-healing not fixing issues
- Agent errors (API limits, auth, etc.)

**Solutions**:
```bash
# Review failing checkpoints
wos cycle status

# Increase healing attempts
export WOS_MAX_HEALING_ATTEMPTS=2

# Check agent logs
tail -f ~/.workspace-os/workspace-memory/agent_queue.jsonl
```

### Memory/CPU Exhaustion

**Symptoms**: System slowdown, OOM kills, agent timeouts

**Causes**:
- Too many workers for available resources
- Memory leaks in agents

**Solutions**:
```bash
# Reduce max workers
export WOS_MAX_WORKERS=8

# Monitor resource usage
top -b -n 1 | grep python
```

### Git Conflicts

**Symptoms**: Agents failing with "branch already exists" or merge conflicts

**Causes**:
- Multiple agents checking out same branch name
- Dirty working directory from previous run

**Solutions**:
```bash
# Clean workspace before run
cd /d/git/homedir
git checkout main
git pull
git clean -fd

# Ensure issue assignment is enabled
export WOS_ENABLE_ISSUE_ASSIGNMENT=true
```

## Advanced: Custom Agent Pool

By default, WOS uses all available agents (opencode, claude, antigravity). You can customize:

```python
# In agent_policy.py or via config
SUPPORTED_WORK_AGENTS = ["opencode", "claude"]  # Exclude antigravity
```

**Use Cases**:
- Exclude slow agents for speed
- Exclude expensive agents for cost
- Test specific agent combinations

## Best Practices

### 1. Start Conservative, Scale Up

```bash
# First run: baseline
export WOS_MAX_WORKERS=8
wos cycle work --continuous --duration-minutes 15

# Monitor results, then scale
export WOS_MAX_WORKERS=16
wos cycle work --continuous --duration-minutes 60
```

### 2. Pre-flight Checks

```bash
# Ensure clean state
cd /d/git/homedir
git status  # Should be clean
gh auth status  # Should be authenticated
gh issue list | wc -l  # Should have enough issues

# Verify WOS is healthy
wos validate
```

### 3. Monitor First 5 Minutes

Watch console output for first few work items:
- Are issues being assigned? (look for "ASSIGNED ISSUE:")
- Is queue filling up? (look for "queue: N/M (X% util)")
- Are tasks completing? (look for "Completed work item")

If issues detected in first 5 min, stop (Ctrl+C) and adjust.

### 4. Save Successful Configurations

```bash
# Export to file for reuse
cat > ~/.wos-high-throughput.env <<EOF
export WOS_MAX_WORKERS=16
export WOS_CHECKPOINT_INTERVAL_SECONDS=600
export WOS_MIN_ITEMS_PER_CHECKPOINT=24
export WOS_MAX_HEALING_ATTEMPTS=1
export WOS_ENABLE_ISSUE_ASSIGNMENT=true
EOF

# Load before runs
source ~/.wos-high-throughput.env
```

## FAQs

### Q: Why not set max_workers to 100?

**A**: Diminishing returns. Each agent needs:
- CPU cycles for execution
- Memory for context/state
- API rate limits (if using cloud agents)

Beyond 32 workers, you hit resource constraints and see no improvement.

### Q: Can I run multiple cycles in parallel?

**A**: Not recommended. WOS uses a single memory store, and parallel cycles would conflict. Instead, increase max_workers in a single cycle.

### Q: What if I run out of issues mid-cycle?

**A**: Agents will fall back to choosing from available issues (or fail gracefully if none left). The queue will drain and utilization will drop. This is normal end-of-work behavior.

### Q: How do I know if my machine can handle N workers?

**A**: Rule of thumb:
- 8 workers: 4 CPU cores, 8GB RAM
- 16 workers: 8 CPU cores, 16GB RAM
- 32 workers: 16 CPU cores, 32GB RAM

Monitor `top` during a run to verify.

## Summary

**To achieve 15-30 PRs/hour**:

1. Run optimization script: `source ./scripts/optimize-cycle-throughput.sh`
2. Start high-throughput cycle: `wos cycle work --continuous --duration-minutes 60`
3. Monitor queue utilization and idle ratio
4. Adjust `WOS_MAX_WORKERS` based on your machine's resources

**Key optimizations**:
- Increase parallelism (16 workers vs 6)
- Reduce checkpoint frequency (10 min vs 5 min)
- Pre-assign issues (eliminate decision overhead)
- Reduce healing attempts (1 vs 2)

**Expected improvement**: 3-6x throughput increase

# Agent Routing Validation

## Overview

Agent routing validation provides pre-assignment validation and cross-check routing to ensure work is routed to the most appropriate agent based on task type, learning model feedback, and agent capabilities.

## Problem Statement

The learning model showed recurring `wrong_agent` errors with 0.97 confidence, indicating systematic agent routing issues. Without pre-validation and cross-checking:
- Work types could be mismatched to agent capabilities
- Agent specialization was not consistently respected
- Ambiguous work routing lacked a clarification pass
- Learning model detected errors but couldn't prevent them

## Solution

Two-tier routing system:

1. **Pre-validation**: `validate_agent_assignment()` function performs validation before task delegation
2. **Cross-check routing**: Automatic validation pass when learning model detects high-confidence wrong_agent patterns

### Validation Checks

1. **Agent Availability**: Verifies agent is supported and available on the system
2. **Task-Capability Matching**: Matches task keywords to agent specializations
3. **Learning Model Alignment**: Checks assignment against learning model bias

### Agent Specializations

| Agent | Specialization | Keywords |
|-------|---------------|----------|
| **opencode** | Refactoring, cleanup, mechanical changes | refactor, cleanup, rename, delete, format, lint, remove, move |
| **claude** | Analysis, planning, reasoning, cross-checking | analyze, review, plan, design, explain, cross-check, verify, evaluate |
| **antigravity** | Architectural work, gap discovery, leverage analysis | gap, architectural, leverage, discover, audit, assess, strategic |

## Usage

### Basic Validation

```python
from workspace_os.agent_policy import validate_agent_assignment

# Validate agent assignment
result = validate_agent_assignment(
    agent='opencode',
    task_hint='refactor the auth module',
    learning_bias='opencode'
)

if not result.is_valid:
    print(f"Invalid assignment: {result.reason}")
    if result.suggested_agent:
        print(f"Suggested agent: {result.suggested_agent}")
elif result.suggested_agent:
    # Soft warning: task suggests different agent
    print(f"Warning: {result.reason} (confidence: {result.confidence})")
```

### Validation Result

The `AgentRoutingValidation` dataclass contains:

- **is_valid**: Boolean indicating if assignment is valid
- **suggested_agent**: Alternative agent suggestion (if any)
- **reason**: Human-readable explanation
- **confidence**: Confidence level (0.0 to 1.0)

### Routing Decision Logging

Enable structured logging of routing decisions:

```bash
# Enable routing logs to stderr
export WOS_ROUTING_LOG=true

# Log to file
export WOS_ROUTING_LOG=true
export WOS_ROUTING_LOG_FILE=/path/to/routing.log
```

Log entries include:
- Timestamp
- Primary agent selected
- Task hint
- Learning bias
- Task suggestion
- Preferred primary
- Routing reason (learning_bias, bias, random)

### Example Log Entry

```json
{
  "timestamp": "2026-06-22T14:30:00.123456",
  "primary_agent": "opencode",
  "task_hint": "refactor the auth module",
  "learning_bias": "opencode",
  "task_suggestion": "opencode",
  "preferred_primary": null,
  "routing_reason": "learning_bias"
}
```

### Cross-Check Routing

When the learning model detects high-confidence wrong_agent errors, automatic cross-check routing is enabled:

```python
from workspace_os.agent_policy import choose_work_agent_pair

# Automatic cross-check when learning confidence >= 0.7
pair = choose_work_agent_pair(
    rng=rng,
    preferred_primary="claude",
    learning_bias="claude",
    task_hint="refactor authentication module",
    cross_check=True,              # Enabled by learning model
    learning_confidence=0.97,       # High confidence wrong_agent detection
)
```

**How it works:**

1. Initial agent selection (learning_bias, task_hint, or random)
2. If `cross_check=True` and `learning_confidence >= 0.7`:
   - Validate selection with `validate_agent_assignment()`
   - If validation suggests different agent with confidence >= 0.6:
     - Override to suggested agent
     - Log override reason
3. Return final agent pair

**Benefits:**

- Automatically corrects wrong_agent errors before they happen
- Catches task-capability mismatches even when learning_bias is set
- Provides audit trail of override decisions
- Reduces wrong_agent error rate in production

**Example:**

```python
# Learning bias suggests claude, but task is refactoring work
# Cross-check detects mismatch and routes to opencode instead
primary, secondary = choose_work_agent_pair(
    learning_bias="claude",           # From learning model
    task_hint="cleanup deprecated functions",  # Clearly opencode work
    cross_check=True,                 # Learning detected wrong_agent pattern
    learning_confidence=0.97,
)
# Result: primary="opencode" (cross-check override)
# Reason: "Task keywords suggest 'opencode' but 'claude' assigned"
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WOS_TASK_AWARE_ROUTING` | `true` | Enable task-aware keyword matching |
| `WOS_ROUTING_DEBUG` | `false` | Enable debug output for routing decisions and cross-check validation |
| `WOS_ROUTING_LOG` | `false` | Enable structured routing decision logging |
| `WOS_ROUTING_LOG_FILE` | - | Path to routing log file (logs to stderr if not set) |

## Integration with Learning Model

The validation function integrates with the learning model:

1. Learning model detects `wrong_agent` errors from historical feedback
2. Builds confidence score (e.g., 0.97 for dominant wrong_agent pattern)
3. Sets `detail_level_hint="cross_check"` when wrong_agent is dominant
4. `choose_work_agent_pair()` receives `cross_check=True` from cycle
5. Cross-check validation triggers for high-confidence scenarios
6. Routing decisions logged for continuous learning

## Testing

Run the comprehensive test suite:

```bash
pytest tests/test_agent_routing.py -v
```

Test coverage includes:
- Unsupported agent detection
- Valid agent assignment
- Task-capability mismatch detection
- Learning bias mismatch detection
- Routing decision logging
- Cross-check routing with high confidence
- Cross-check override behavior
- Cross-check with aligned agents (no override)
- Cross-check low confidence (no trigger)

## Impact

### Before
- `wrong_agent` errors: 97% confidence
- No pre-validation
- Silent routing mismatches
- No routing decision audit trail
- Errors detected but not prevented

### After
- Pre-validation catches mismatches before delegation
- Cross-check automatically corrects high-confidence errors
- Task-capability alignment validated
- Complete routing audit trail
- Proactive error prevention (not just detection)
- Soft warnings for sub-optimal routing
- Structured logging for learning
- Reduced wrong_agent error rate

## References

- Issue #97: [Learning] Implement cross-check routing for wrong_agent errors
- Learning model: `src/workspace_os/learning.py`
- Agent policy: `src/workspace_os/agent_policy.py`
- Tests: `tests/test_agent_routing.py`

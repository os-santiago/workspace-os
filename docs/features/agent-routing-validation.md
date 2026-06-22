# Agent Routing Validation

## Overview

Agent routing validation provides pre-assignment validation to ensure work is routed to the most appropriate agent based on task type, learning model feedback, and agent capabilities.

## Problem Statement

The learning model showed recurring `wrong_agent` errors with 0.97 confidence, indicating systematic agent routing issues. Without pre-validation:
- Work types could be mismatched to agent capabilities
- Agent specialization was not consistently respected
- Ambiguous work routing lacked a clarification pass

## Solution

Added `validate_agent_assignment()` function that performs pre-validation before task delegation:

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

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WOS_TASK_AWARE_ROUTING` | `true` | Enable task-aware keyword matching |
| `WOS_ROUTING_DEBUG` | `false` | Enable debug output for routing decisions |
| `WOS_ROUTING_LOG` | `false` | Enable structured routing decision logging |
| `WOS_ROUTING_LOG_FILE` | - | Path to routing log file (logs to stderr if not set) |

## Integration with Learning Model

The validation function integrates with the learning model:

1. Learning model detects `wrong_agent` errors
2. Builds confidence score (e.g., 0.97 for wrong_agent)
3. Suggests preferred agent via `learning_bias`
4. Validation function checks assignment against bias
5. Logs decisions for continuous improvement

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

## Impact

### Before
- `wrong_agent` errors: 97% confidence
- No pre-validation
- Silent routing mismatches
- No routing decision audit trail

### After
- Pre-validation catches mismatches
- Soft warnings for sub-optimal routing
- Structured logging for learning
- Reduced wrong_agent error rate

## References

- Issue #918: [WOS] Implement agent routing validation to reduce wrong_agent errors
- Learning model: `src/workspace_os/learning.py`
- Agent policy: `src/workspace_os/agent_policy.py`
- Tests: `tests/test_agent_routing.py`

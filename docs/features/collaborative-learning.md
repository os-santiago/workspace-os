# Collaborative Learning System

## Overview

The Collaborative Learning System enables agents in Squad Lead mode to learn from each other's successes and failures, share knowledge, and continuously improve coordination through pattern extraction and insight sharing.

## Features

### 1. Shared Knowledge Base

A persistent knowledge base that stores:

- **Learning Patterns**: Extracted from task history (successes, failures, antipatterns, best practices)
- **Agent Insights**: Observations and recommendations from agents during execution
- **Best Practices**: Validated approaches that consistently work well
- **Common Pitfalls**: Known issues to avoid

### 2. Pattern Extraction

Automatically extracts patterns from task history and operator feedback.

### 3. Knowledge Broadcasting

At each checkpoint, the system extracts patterns from recent work and updates the shared knowledge base.

### 4. Context-Aware Learning

Agents receive role-specific learning context based on their current role.

## Quick Start

The Collaborative Learning System is automatically enabled when Squad Lead mode is active:

```bash
export WOS_SQUAD_LEAD_MODE=true
wos cycle work --duration-minutes 30 --label learning-test
```

## Storage

Knowledge is persisted in `.workspace/shared_knowledge/`:

- `patterns.jsonl`: Learning patterns
- `insights.jsonl`: Agent insights

## Testing

Run the test suite:

```bash
cd /d/git/workspace-os
pytest tests/test_collaborative_learning.py -v
```

from __future__ import annotations

import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from workspace_os.collaborative_learning import (
    LearningPattern,
    AgentInsight,
    SharedKnowledgeBase,
    PatternExtractor,
    create_shared_knowledge_base,
    get_learning_context_for_agent,
    broadcast_learning,
    collect_agent_insights,
)
from workspace_os.agent_queue import AgentTaskTrace, AgentTaskState
from workspace_os.memory import WorkspaceMemoryStore


@pytest.fixture
def temp_knowledge_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def knowledge_base(temp_knowledge_dir):
    return SharedKnowledgeBase(knowledge_dir=temp_knowledge_dir / "shared_knowledge")


@pytest.fixture
def memory_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WorkspaceMemoryStore(Path(tmpdir) / "memory")
        yield store


def test_learning_pattern_creation():
    pattern = LearningPattern(
        pattern_id="test_pattern_1",
        pattern_type="success",
        description="Test pattern",
        context="Testing",
        frequency=5,
        confidence=0.8,
        first_seen="2024-01-01T00:00:00Z",
        last_seen="2024-01-02T00:00:00Z",
        examples=("ex1", "ex2"),
        agent_sources=("claude", "opencode"),
    )

    assert pattern.pattern_id == "test_pattern_1"
    assert pattern.pattern_type == "success"
    assert pattern.frequency == 5
    assert pattern.confidence == 0.8

    summary = pattern.render_summary()
    assert "success" in summary
    assert "claude" in summary


def test_shared_knowledge_base_persistence(temp_knowledge_dir):
    kb1 = SharedKnowledgeBase(knowledge_dir=temp_knowledge_dir / "kb")

    pattern = LearningPattern(
        pattern_id="p1",
        pattern_type="best_practice",
        description="Always validate inputs",
        context="Testing",
        frequency=10,
        confidence=0.9,
        first_seen="2024-01-01T00:00:00Z",
        last_seen="2024-01-02T00:00:00Z",
        examples=("e1",),
        agent_sources=("system",),
    )
    kb1.add_pattern(pattern)

    # Reload knowledge base
    kb2 = SharedKnowledgeBase(knowledge_dir=temp_knowledge_dir / "kb")
    assert "p1" in kb2.patterns
    assert kb2.patterns["p1"].description == "Always validate inputs"


def test_get_learning_context_for_agent(knowledge_base):
    # Add some patterns and insights
    knowledge_base.add_pattern(
        LearningPattern(
            pattern_id="bp1",
            pattern_type="best_practice",
            description="Always write tests first",
            context="Testing",
            frequency=10,
            confidence=0.9,
            first_seen="2024-01-01T00:00:00Z",
            last_seen="2024-01-02T00:00:00Z",
            examples=(),
            agent_sources=("system",),
        )
    )

    context = get_learning_context_for_agent(knowledge_base, "claude", "primary", limit=5)

    assert "Best Practices" in context
    assert "tests first" in context


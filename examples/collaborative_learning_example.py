#!/usr/bin/env python3
"""
Example: Using Collaborative Learning System

This example demonstrates how to use the collaborative learning features
to track agent performance and share knowledge across the squad.
"""

from pathlib import Path
import tempfile

from workspace_os.collaborative_learning import (
    create_shared_knowledge_base,
    PatternExtractor,
    get_learning_context_for_agent,
    collect_learning_metrics,
    LearningPattern,
    AgentInsight,
)
from workspace_os.agent_queue import AgentTaskTrace, AgentTaskState
from workspace_os.memory import WorkspaceMemoryStore


def main():
    # Create temporary workspace for demo
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_root = Path(tmpdir)
        
        # Initialize knowledge base
        print("=== Initializing Collaborative Learning System ===\n")
        knowledge_base = create_shared_knowledge_base(workspace_root)
        
        # Simulate some agent task history
        print("Simulating agent task execution...")
        tasks = [
            AgentTaskTrace(
                task_id=f"task-{i}",
                agent="claude" if i % 2 == 0 else "opencode",
                workspace="demo",
                prompt=f"Work item {i}",
                state=AgentTaskState.COMPLETED if i % 3 != 0 else AgentTaskState.FAILED,
                queued_at="2024-01-01T00:00:00Z",
                completed_at="2024-01-01T00:01:00Z",
                returncode=0 if i % 3 != 0 else 1,
                error="Test error" if i % 3 == 0 else None,
            )
            for i in range(10)
        ]
        
        # Extract patterns from task history
        print("\n=== Extracting Patterns from Task History ===\n")
        extractor = PatternExtractor(knowledge_base)
        patterns = extractor.extract_from_task_history(tasks, min_frequency=2, min_confidence=0.5)
        
        print(f"Extracted {len(patterns)} patterns:")
        for pattern in patterns:
            print(f"  - {pattern.render_summary()}")
            knowledge_base.add_pattern(pattern)
        
        # Add some manual best practices
        print("\n=== Adding Best Practices ===\n")
        best_practice = LearningPattern(
            pattern_id="bp_tests_first",
            pattern_type="best_practice",
            description="Always write tests before implementation",
            context="Development process",
            frequency=15,
            confidence=0.95,
            first_seen="2024-01-01T00:00:00Z",
            last_seen="2024-01-10T00:00:00Z",
            examples=("task-5", "task-8", "task-12"),
            agent_sources=("system", "claude", "opencode"),
        )
        knowledge_base.add_pattern(best_practice)
        print(f"  - {best_practice.render_summary()}")
        
        # Add agent insights
        print("\n=== Collecting Agent Insights ===\n")
        insight = AgentInsight(
            insight_id="insight_1",
            agent="claude",
            role="primary",
            task_id="task-1",
            category="efficiency",
            observation="Completed task with minimal file changes",
            recommendation="Focus on minimal change surface to reduce errors",
            impact="high",
            created_at="2024-01-01T00:00:00Z",
        )
        knowledge_base.add_insight(insight)
        print(f"  - {insight.render_summary()}")
        
        # Get learning context for different roles
        print("\n=== Learning Context for Agents ===\n")
        
        for role in ["primary", "cross-check", "observer"]:
            print(f"\n{role.upper()} Agent Context:")
            context = get_learning_context_for_agent(knowledge_base, "claude", role, limit=3)
            if context:
                for line in context.split('\n'):
                    print(f"  {line}")
            else:
                print("  (No context available)")
        
        # Show metrics
        print("\n=== Collaborative Learning Metrics ===\n")
        metrics = collect_learning_metrics(knowledge_base)
        print(metrics.render_summary())
        
        # Show knowledge base summary
        print("\n" + "="*60)
        print(knowledge_base.render_knowledge_summary())


if __name__ == "__main__":
    main()

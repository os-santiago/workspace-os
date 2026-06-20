from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
from collections import defaultdict

from workspace_os.memory import WorkspaceMemoryStore


@dataclass(frozen=True)
class LearningPattern:
    pattern_id: str
    pattern_type: str  # success, failure, antipattern, best_practice
    description: str
    context: str
    frequency: int
    confidence: float
    first_seen: str
    last_seen: str
    examples: tuple[str, ...]
    agent_sources: tuple[str, ...]  # Which agents contributed to this pattern

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "context": self.context,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "examples": list(self.examples),
            "agent_sources": list(self.agent_sources),
        }

    def render_summary(self) -> str:
        agents = ", ".join(sorted(set(self.agent_sources)))
        return (
            f"[{self.pattern_type}] {self.description} "
            f"(freq={self.frequency}, conf={self.confidence:.2f}, agents={agents})"
        )


@dataclass(frozen=True)
class AgentInsight:
    insight_id: str
    agent: str
    role: str  # primary, cross-check, observer
    task_id: str
    category: str  # efficiency, quality, correctness, coordination
    observation: str
    recommendation: str | None
    impact: str  # low, medium, high
    created_at: str
    applied: bool = False
    applied_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "agent": self.agent,
            "role": self.role,
            "task_id": self.task_id,
            "category": self.category,
            "observation": self.observation,
            "recommendation": self.recommendation,
            "impact": self.impact,
            "created_at": self.created_at,
            "applied": self.applied,
            "applied_at": self.applied_at,
        }

    def render_summary(self) -> str:
        status = "✓ applied" if self.applied else "pending"
        rec = self.recommendation[:50] + "..." if self.recommendation and len(self.recommendation) > 50 else (self.recommendation or "")
        return (
            f"[{self.impact}] {self.agent} ({self.role}): {self.observation[:60]}... "
            f"→ {rec} [{status}]"
        )


@dataclass
class SharedKnowledgeBase:
    knowledge_dir: Path
    patterns: dict[str, LearningPattern] = field(default_factory=dict)
    insights: dict[str, AgentInsight] = field(default_factory=dict)
    best_practices: list[str] = field(default_factory=list)
    common_pitfalls: list[str] = field(default_factory=list)
    effective_patterns: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self._load_knowledge()

    def _load_knowledge(self) -> None:
        patterns_file = self.knowledge_dir / "patterns.jsonl"
        insights_file = self.knowledge_dir / "insights.jsonl"

        if patterns_file.exists():
            with open(patterns_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        pattern = LearningPattern(
                            pattern_id=data["pattern_id"],
                            pattern_type=data["pattern_type"],
                            description=data["description"],
                            context=data["context"],
                            frequency=data["frequency"],
                            confidence=data["confidence"],
                            first_seen=data["first_seen"],
                            last_seen=data["last_seen"],
                            examples=tuple(data["examples"]),
                            agent_sources=tuple(data["agent_sources"]),
                        )
                        self.patterns[pattern.pattern_id] = pattern

        if insights_file.exists():
            with open(insights_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        insight = AgentInsight(
                            insight_id=data["insight_id"],
                            agent=data["agent"],
                            role=data["role"],
                            task_id=data["task_id"],
                            category=data["category"],
                            observation=data["observation"],
                            recommendation=data.get("recommendation"),
                            impact=data["impact"],
                            created_at=data["created_at"],
                            applied=data.get("applied", False),
                            applied_at=data.get("applied_at"),
                        )
                        self.insights[insight.insight_id] = insight

    def add_pattern(self, pattern: LearningPattern) -> None:
        self.patterns[pattern.pattern_id] = pattern
        patterns_file = self.knowledge_dir / "patterns.jsonl"
        with open(patterns_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(pattern.to_dict()) + "\n")

    def add_insight(self, insight: AgentInsight) -> None:
        self.insights[insight.insight_id] = insight
        insights_file = self.knowledge_dir / "insights.jsonl"
        with open(insights_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(insight.to_dict()) + "\n")

    def mark_insight_applied(self, insight_id: str) -> None:
        if insight_id in self.insights:
            old_insight = self.insights[insight_id]
            updated_insight = AgentInsight(
                insight_id=old_insight.insight_id,
                agent=old_insight.agent,
                role=old_insight.role,
                task_id=old_insight.task_id,
                category=old_insight.category,
                observation=old_insight.observation,
                recommendation=old_insight.recommendation,
                impact=old_insight.impact,
                created_at=old_insight.created_at,
                applied=True,
                applied_at=datetime.now(timezone.utc).isoformat(),
            )
            self.insights[insight_id] = updated_insight
            self._save_all_insights()

    def _save_all_insights(self) -> None:
        insights_file = self.knowledge_dir / "insights.jsonl"
        with open(insights_file, "w", encoding="utf-8") as f:
            for insight in self.insights.values():
                f.write(json.dumps(insight.to_dict()) + "\n")

    def get_patterns_by_type(self, pattern_type: str) -> list[LearningPattern]:
        return [p for p in self.patterns.values() if p.pattern_type == pattern_type]

    def get_insights_by_category(self, category: str, applied: bool | None = None) -> list[AgentInsight]:
        insights = [i for i in self.insights.values() if i.category == category]
        if applied is not None:
            insights = [i for i in insights if i.applied == applied]
        return sorted(insights, key=lambda x: x.created_at, reverse=True)

    def get_top_insights(self, limit: int = 10, applied: bool = False) -> list[AgentInsight]:
        unapplied = [i for i in self.insights.values() if i.applied == applied]
        # Sort by impact (high > medium > low) then by recency
        impact_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            unapplied,
            key=lambda x: (impact_order.get(x.impact, 3), x.created_at),
            reverse=False,
        )[:limit]

    def render_knowledge_summary(self) -> str:
        lines = ["Shared Knowledge Base Summary:"]
        lines.append(f"Patterns: {len(self.patterns)} total")
        for ptype in ["success", "failure", "antipattern", "best_practice"]:
            count = len(self.get_patterns_by_type(ptype))
            if count > 0:
                lines.append(f"  - {ptype}: {count}")

        lines.append(f"\nInsights: {len(self.insights)} total")
        for category in ["efficiency", "quality", "correctness", "coordination"]:
            count = len(self.get_insights_by_category(category))
            applied = len(self.get_insights_by_category(category, applied=True))
            if count > 0:
                lines.append(f"  - {category}: {count} ({applied} applied)")

        top_insights = self.get_top_insights(limit=5, applied=False)
        if top_insights:
            lines.append("\nTop Unapplied Insights:")
            for insight in top_insights:
                lines.append(f"  - {insight.render_summary()}")

        return "\n".join(lines) + "\n"


class PatternExtractor:
    def __init__(self, knowledge_base: SharedKnowledgeBase):
        self.knowledge_base = knowledge_base

    def extract_from_task_history(
        self,
        tasks: list[Any],
        min_frequency: int = 3,
        min_confidence: float = 0.6,
    ) -> list[LearningPattern]:
        """Extract patterns from task history (successes and failures)."""
        patterns: list[LearningPattern] = []

        # Group tasks by outcome
        successes = [t for t in tasks if hasattr(t, "state") and t.state.value == "completed" and t.returncode == 0]
        failures = [t for t in tasks if hasattr(t, "state") and t.state.value == "failed"]

        # Extract success patterns
        if len(successes) >= min_frequency:
            success_agents = [t.agent for t in successes]
            agent_counts = defaultdict(int)
            for agent in success_agents:
                agent_counts[agent] += 1

            for agent, count in agent_counts.items():
                if count >= min_frequency:
                    confidence = count / len(successes)
                    if confidence >= min_confidence:
                        pattern_id = f"success_{agent}_{datetime.now(timezone.utc).timestamp()}"
                        pattern = LearningPattern(
                            pattern_id=pattern_id,
                            pattern_type="success",
                            description=f"Agent {agent} consistently completes tasks successfully",
                            context="Task completion",
                            frequency=count,
                            confidence=confidence,
                            first_seen=successes[0].queued_at if successes else "",
                            last_seen=successes[-1].completed_at or successes[-1].queued_at if successes else "",
                            examples=tuple([t.task_id for t in successes if t.agent == agent][:5]),
                            agent_sources=tuple([agent]),
                        )
                        patterns.append(pattern)

        # Extract failure patterns
        if len(failures) >= min_frequency:
            failure_agents = [t.agent for t in failures]
            agent_counts = defaultdict(int)
            for agent in failure_agents:
                agent_counts[agent] += 1

            for agent, count in agent_counts.items():
                if count >= min_frequency:
                    confidence = count / len(failures)
                    if confidence >= min_confidence:
                        pattern_id = f"failure_{agent}_{datetime.now(timezone.utc).timestamp()}"
                        pattern = LearningPattern(
                            pattern_id=pattern_id,
                            pattern_type="failure",
                            description=f"Agent {agent} experiencing repeated failures",
                            context="Task completion",
                            frequency=count,
                            confidence=confidence,
                            first_seen=failures[0].queued_at if failures else "",
                            last_seen=failures[-1].completed_at or failures[-1].queued_at if failures else "",
                            examples=tuple([f"{t.task_id}: {t.error}" for t in failures if t.agent == agent][:5]),
                            agent_sources=tuple([agent]),
                        )
                        patterns.append(pattern)

        return patterns

    def extract_from_feedback(
        self,
        memory_store: WorkspaceMemoryStore,
        min_frequency: int = 2,
    ) -> list[LearningPattern]:
        """Extract patterns from operator feedback."""
        patterns: list[LearningPattern] = []
        metrics = memory_store.feedback_metrics()

        error_types = [
            "too_verbose",
            "wrong_agent",
            "missing_repo_resolution",
            "missing_clarification",
            "ignored_preference",
            "generic_fallback",
        ]

        for error_type in error_types:
            count = metrics.get(f"{error_type}_count", 0)
            if count >= min_frequency:
                total = metrics.get("total", 1)
                confidence = count / total if total > 0 else 0.0

                pattern_id = f"antipattern_{error_type}_{datetime.now(timezone.utc).timestamp()}"
                pattern = LearningPattern(
                    pattern_id=pattern_id,
                    pattern_type="antipattern",
                    description=f"Recurring {error_type.replace('_', ' ')} issues",
                    context="Operator feedback",
                    frequency=count,
                    confidence=confidence,
                    first_seen=datetime.now(timezone.utc).isoformat(),
                    last_seen=datetime.now(timezone.utc).isoformat(),
                    examples=tuple([error_type]),
                    agent_sources=tuple(["system"]),
                )
                patterns.append(pattern)

        return patterns


def create_shared_knowledge_base(memory_root: Path) -> SharedKnowledgeBase:
    """Create or load the shared knowledge base."""
    knowledge_dir = memory_root / "shared_knowledge"
    return SharedKnowledgeBase(knowledge_dir=knowledge_dir)


def broadcast_learning(
    knowledge_base: SharedKnowledgeBase,
    pattern: LearningPattern,
) -> None:
    """Broadcast a learned pattern to the knowledge base."""
    knowledge_base.add_pattern(pattern)


def collect_agent_insights(
    knowledge_base: SharedKnowledgeBase,
    agent: str,
    role: str,
    task_id: str,
    observations: list[dict[str, str]],
) -> None:
    """Collect insights from an agent's observations."""
    for obs in observations:
        insight_id = f"insight_{agent}_{task_id}_{datetime.now(timezone.utc).timestamp()}"
        insight = AgentInsight(
            insight_id=insight_id,
            agent=agent,
            role=role,
            task_id=task_id,
            category=obs.get("category", "general"),
            observation=obs.get("observation", ""),
            recommendation=obs.get("recommendation"),
            impact=obs.get("impact", "medium"),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        knowledge_base.add_insight(insight)


def get_learning_context_for_agent(
    knowledge_base: SharedKnowledgeBase,
    agent: str,
    role: str,
    limit: int = 5,
) -> str:
    """Get relevant learning context for an agent based on role."""
    lines = []

    # Add relevant best practices
    best_practices = knowledge_base.get_patterns_by_type("best_practice")
    if best_practices:
        lines.append("Best Practices:")
        for pattern in best_practices[:limit]:
            lines.append(f"  - {pattern.description}")

    # Add common pitfalls to avoid
    pitfalls = knowledge_base.get_patterns_by_type("antipattern")
    if pitfalls:
        lines.append("\nCommon Pitfalls to Avoid:")
        for pattern in pitfalls[:limit]:
            lines.append(f"  - {pattern.description}")

    # Add role-specific insights
    if role == "primary":
        category = "efficiency"
    elif role == "cross-check":
        category = "quality"
    elif role == "observer":
        category = "coordination"
    else:
        category = "general"

    insights = knowledge_base.get_insights_by_category(category, applied=False)
    if insights:
        lines.append(f"\n{category.title()} Insights:")
        for insight in insights[:limit]:
            if insight.recommendation:
                lines.append(f"  - {insight.observation} → {insight.recommendation}")

    return "\n".join(lines) if lines else ""


@dataclass(frozen=True)
class CollaborativeLearningMetrics:
    total_patterns: int
    success_patterns: int
    failure_patterns: int
    antipatterns: int
    best_practices: int
    total_insights: int
    applied_insights: int
    unapplied_insights: int
    high_impact_insights: int
    insights_by_category: dict[str, int]
    patterns_by_agent: dict[str, int]
    
    def render_summary(self) -> str:
        lines = ["Collaborative Learning Metrics:"]
        lines.append(f"  Total Patterns: {self.total_patterns}")
        lines.append(f"    Success: {self.success_patterns}")
        lines.append(f"    Failure: {self.failure_patterns}")
        lines.append(f"    Antipatterns: {self.antipatterns}")
        lines.append(f"    Best Practices: {self.best_practices}")
        lines.append(f"  Total Insights: {self.total_insights}")
        lines.append(f"    Applied: {self.applied_insights}")
        lines.append(f"    Unapplied: {self.unapplied_insights}")
        lines.append(f"    High Impact: {self.high_impact_insights}")
        
        if self.insights_by_category:
            lines.append("  Insights by Category:")
            for category, count in sorted(self.insights_by_category.items()):
                lines.append(f"    {category}: {count}")
        
        if self.patterns_by_agent:
            lines.append("  Patterns by Agent:")
            for agent, count in sorted(self.patterns_by_agent.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"    {agent}: {count}")
        
        return "\n".join(lines)


def collect_learning_metrics(knowledge_base: SharedKnowledgeBase) -> CollaborativeLearningMetrics:
    """Collect metrics on collaborative learning system."""
    patterns_by_type = {
        "success": len(knowledge_base.get_patterns_by_type("success")),
        "failure": len(knowledge_base.get_patterns_by_type("failure")),
        "antipattern": len(knowledge_base.get_patterns_by_type("antipattern")),
        "best_practice": len(knowledge_base.get_patterns_by_type("best_practice")),
    }
    
    insights_by_category: dict[str, int] = defaultdict(int)
    for insight in knowledge_base.insights.values():
        insights_by_category[insight.category] += 1
    
    patterns_by_agent: dict[str, int] = defaultdict(int)
    for pattern in knowledge_base.patterns.values():
        for agent in pattern.agent_sources:
            patterns_by_agent[agent] += 1
    
    applied = sum(1 for i in knowledge_base.insights.values() if i.applied)
    unapplied = sum(1 for i in knowledge_base.insights.values() if not i.applied)
    high_impact = sum(1 for i in knowledge_base.insights.values() if i.impact == "high")
    
    return CollaborativeLearningMetrics(
        total_patterns=len(knowledge_base.patterns),
        success_patterns=patterns_by_type["success"],
        failure_patterns=patterns_by_type["failure"],
        antipatterns=patterns_by_type["antipattern"],
        best_practices=patterns_by_type["best_practice"],
        total_insights=len(knowledge_base.insights),
        applied_insights=applied,
        unapplied_insights=unapplied,
        high_impact_insights=high_impact,
        insights_by_category=dict(insights_by_category),
        patterns_by_agent=dict(patterns_by_agent),
    )

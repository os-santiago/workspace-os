# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Issue complexity detection and classification.

This module analyzes GitHub issues to determine their complexity level
and identify what phases are needed for successful resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any


class ComplexityLevel(Enum):
    """Issue complexity levels."""

    SIMPLE = "simple"  # Straightforward implementation, no research needed
    MODERATE = "moderate"  # Requires some research or minor decisions
    COMPLEX = "complex"  # Needs deep research and architecture decisions


@dataclass(frozen=True)
class ComplexityClassification:
    """Result of issue complexity analysis."""

    level: ComplexityLevel
    score: float  # 0-10 scale
    requires_research: bool
    requires_architecture_decision: bool
    has_ambiguities: list[str]
    detected_dependencies: list[str]
    estimated_agents: int  # Number of agents recommended
    estimated_duration_minutes: int
    reasoning: str  # Human-readable explanation


# Keyword indicators for complexity detection
COMPLEXITY_INDICATORS = {
    "architecture": [
        "architecture",
        "design",
        "strategy",
        "approach",
        "pattern",
        "refactor",
        "restructure",
        "rewrite",
        "migrate",
        "migration",
    ],
    "research_needed": [
        "bug",
        "leak",
        "issue",
        "problem",
        "investigate",
        "diagnose",
        "why",
        "cause",
        "root cause",
        "analyze",
    ],
    "external_dependencies": [
        "API",
        "external",
        "third-party",
        "integration",
        "webhook",
        "SDK",
        "library",
        "package",
        "install",
        "configure",
    ],
    "ambiguous": [
        "improve",
        "better",
        "optimize",
        "enhance",
        "update",
        "sometime",
        "should",
        "could",
        "maybe",
        "consider",
    ],
    "scale_complexity": [
        "performance",
        "scale",
        "scalability",
        "throughput",
        "latency",
        "concurrent",
        "distributed",
        "async",
    ],
}

# Patterns that indicate complexity
COMPLEX_PATTERNS = [
    r"multiple\s+\w+",  # "multiple options", "multiple approaches"
    r"various\s+\w+",  # "various ways", "various solutions"
    r"different\s+\w+",  # "different strategies"
    r"several\s+\w+",  # "several alternatives"
    r"\d+x\s+(faster|slower|better)",  # "10x faster"
    r"(?:better|worse)\s+than",  # Comparisons
]


def classify_issue(issue_data: dict[str, Any]) -> ComplexityClassification:
    """Classify an issue's complexity based on its content.

    Args:
        issue_data: GitHub issue data with 'title', 'body', 'labels', etc.

    Returns:
        ComplexityClassification with detected level and requirements.
    """
    title = issue_data.get("title", "")
    body = issue_data.get("body", "")
    labels = [label.get("name", "") for label in issue_data.get("labels", [])]

    # Combine all text for analysis
    full_text = f"{title} {body}".lower()

    # Calculate scores for different aspects
    architecture_score = _score_keywords(full_text, COMPLEXITY_INDICATORS["architecture"])
    research_score = _score_keywords(full_text, COMPLEXITY_INDICATORS["research_needed"])
    dependency_score = _score_keywords(full_text, COMPLEXITY_INDICATORS["external_dependencies"])
    ambiguity_score = _score_keywords(full_text, COMPLEXITY_INDICATORS["ambiguous"])
    scale_score = _score_keywords(full_text, COMPLEXITY_INDICATORS["scale_complexity"])

    # Check for complex patterns
    pattern_score = sum(1 for pattern in COMPLEX_PATTERNS if re.search(pattern, full_text))

    # Label-based scoring
    label_score = 0.0
    if any("architecture" in label.lower() for label in labels):
        label_score += 3.0
    if any("enhancement" in label.lower() for label in labels):
        label_score += 0.5
    if any("bug" in label.lower() for label in labels):
        research_score += 1.0  # Reduced from 2.0

    # Aggregate complexity score (0-10 scale)
    total_score = (
        architecture_score * 1.5  # Reduced from 2.0
        + research_score * 1.0  # Reduced from 1.5
        + dependency_score * 1.5
        + ambiguity_score * 1.5  # Increased from 1.0
        + scale_score * 1.5
        + pattern_score * 0.5
        + label_score
    )

    # Normalize to 0-10
    total_score = min(10.0, total_score)

    # Determine level
    if total_score >= 7.0:
        level = ComplexityLevel.COMPLEX
    elif total_score >= 4.0:
        level = ComplexityLevel.MODERATE
    else:
        level = ComplexityLevel.SIMPLE

    # Determine requirements
    requires_research = research_score >= 2.0 or level in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX)
    requires_architecture = architecture_score >= 2.0 or level == ComplexityLevel.COMPLEX

    # Detect ambiguities
    ambiguities = _detect_ambiguities(title, body, ambiguity_score)

    # Detect dependencies
    dependencies = _detect_dependencies(full_text)

    # Estimate resources
    if level == ComplexityLevel.COMPLEX:
        estimated_agents = 8
        estimated_duration = 90
    elif level == ComplexityLevel.MODERATE:
        estimated_agents = 5
        estimated_duration = 60
    else:
        estimated_agents = 3
        estimated_duration = 30

    # Generate reasoning
    reasoning = _generate_reasoning(
        level, total_score, architecture_score, research_score, dependency_score, ambiguity_score, scale_score
    )

    return ComplexityClassification(
        level=level,
        score=total_score,
        requires_research=requires_research,
        requires_architecture_decision=requires_architecture,
        has_ambiguities=ambiguities,
        detected_dependencies=dependencies,
        estimated_agents=estimated_agents,
        estimated_duration_minutes=estimated_duration,
        reasoning=reasoning,
    )


def _score_keywords(text: str, keywords: list[str]) -> float:
    """Score text based on keyword presence.

    Returns a score based on how many keywords are found.
    """
    score = 0.0
    for keyword in keywords:
        if keyword in text:
            # Weight based on keyword length (longer = more specific)
            weight = 1.0 + (len(keyword.split()) - 1) * 0.5
            score += weight

    return score


def _detect_ambiguities(title: str, body: str, ambiguity_score: float) -> list[str]:
    """Detect specific ambiguities in the issue description."""
    ambiguities = []

    title_lower = title.lower()
    body_lower = body.lower()

    # Check for vague goals
    if any(word in title_lower for word in ["improve", "better", "optimize", "enhance"]):
        if not any(metric in body_lower for metric in ["2x", "10x", "ms", "seconds", "%", "percent"]):
            ambiguities.append("Goal is vague - no specific target metric defined")

    # Check for missing scope
    if any(word in title_lower for word in ["performance", "scale"]):
        if not any(scope in body_lower for scope in ["api", "database", "frontend", "backend", "query"]):
            ambiguities.append("Scope unclear - which component to optimize?")

    # Check for decision points
    if ambiguity_score >= 3.0:
        ambiguities.append("Multiple approaches mentioned - decision needed")

    return ambiguities


def _detect_dependencies(text: str) -> list[str]:
    """Detect external dependencies mentioned in text."""
    dependencies = []

    # Common dependency indicators
    dependency_patterns = [
        (r"stripe", "Stripe payment processing"),
        (r"redis", "Redis cache"),
        (r"postgres|postgresql", "PostgreSQL database"),
        (r"elasticsearch", "Elasticsearch"),
        (r"kafka", "Apache Kafka"),
        (r"rabbitmq", "RabbitMQ"),
        (r"aws|amazon web services", "AWS services"),
        (r"gcp|google cloud", "Google Cloud Platform"),
        (r"docker", "Docker containerization"),
        (r"kubernetes|k8s", "Kubernetes orchestration"),
    ]

    for pattern, dependency_name in dependency_patterns:
        if re.search(pattern, text):
            dependencies.append(dependency_name)

    return dependencies


def _generate_reasoning(
    level: ComplexityLevel,
    total_score: float,
    architecture_score: float,
    research_score: float,
    dependency_score: float,
    ambiguity_score: float,
    scale_score: float,
) -> str:
    """Generate human-readable explanation of complexity classification."""
    reasons = []

    if architecture_score >= 2.0:
        reasons.append("requires architectural decisions")
    if research_score >= 2.0:
        reasons.append("needs investigation/research")
    if dependency_score >= 2.0:
        reasons.append("has external dependencies")
    if ambiguity_score >= 2.0:
        reasons.append("contains ambiguous requirements")
    if scale_score >= 2.0:
        reasons.append("involves performance/scale considerations")

    if not reasons:
        reasoning = "Straightforward implementation with clear requirements"
    else:
        reasoning = f"Classified as {level.value.upper()} because: {', '.join(reasons)}"

    reasoning += f" (score: {total_score:.1f}/10)"

    return reasoning

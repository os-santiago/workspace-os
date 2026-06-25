# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Architecture Decision workflow for complex issues.

This module helps generate and evaluate architectural options before implementation.
Implements Architecture Decision Records (ADR) pattern.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class RiskLevel(Enum):
    """Risk level for an architectural option."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ArchitectureOption:
    """Single architectural approach option."""

    name: str
    description: str
    pros: list[str]
    cons: list[str]
    estimated_effort_hours: float
    risk_level: RiskLevel
    dependencies: list[str] = field(default_factory=list)
    implementation_steps: list[str] = field(default_factory=list)
    confidence: float = 0.5  # How confident are we this will work


@dataclass
class ArchitectureDecision:
    """Final architecture decision record."""

    issue_number: int
    issue_title: str
    options: list[ArchitectureOption]
    recommended_option: ArchitectureOption
    recommendation_reasoning: str
    decision_date: str
    decided_by: str  # "ai" or "user"
    user_override: ArchitectureOption | None = None  # If user chose different option
    research_summary: str = ""


def generate_architecture_prompt(issue_data: dict[str, Any], research_summary: str = "") -> str:
    """Generate prompt for architecture option generation.

    Args:
        issue_data: GitHub issue data
        research_summary: Optional research findings to inform options

    Returns:
        Prompt for generating 3 architecture options
    """
    title = issue_data.get("title", "")
    body = issue_data.get("body", "")

    prompt = f"""Generate 3 DISTINCT architectural approaches for this issue:

**Issue**: {title}
**Description**: {body}
"""

    if research_summary:
        prompt += f"""
**Research Findings**:
{research_summary}
"""

    prompt += """

For EACH option, provide:

1. **Name**: Short, descriptive name (e.g., "Redis Cache-Aside", "Event-Driven Architecture")
2. **Description**: 2-3 sentences explaining the approach
3. **Pros**: List of advantages (3-5 items)
4. **Cons**: List of disadvantages (3-5 items)
5. **Estimated Effort**: Hours to implement (be realistic)
6. **Risk Level**: low, medium, or high
7. **Dependencies**: External libraries/services needed
8. **Implementation Steps**: High-level steps (3-7 items)

**Important**: Options should be DISTINCT approaches, not variations of the same idea.
Examples of distinct options:
- Option A: Client-side caching
- Option B: Server-side caching
- Option C: No caching, optimize queries instead

Output JSON:
{
    "options": [
        {
            "name": "Option name",
            "description": "Detailed description",
            "pros": ["Pro 1", "Pro 2", "Pro 3"],
            "cons": ["Con 1", "Con 2"],
            "estimated_effort_hours": 8.0,
            "risk_level": "medium",
            "dependencies": ["redis", "redis-py"],
            "implementation_steps": ["Step 1", "Step 2", "Step 3"],
            "confidence": 0.8
        }
    ]
}
"""

    return prompt


def evaluate_options(options: list[ArchitectureOption], context: dict[str, Any]) -> ArchitectureOption:
    """Evaluate options and recommend the best one.

    Args:
        options: List of architecture options to evaluate
        context: Additional context (team size, timeline, risk tolerance, etc.)

    Returns:
        Recommended option
    """
    if not options:
        raise ValueError("No options to evaluate")

    # Scoring criteria (weighted)
    weights = {
        "effort": 0.3,  # Lower effort = better
        "risk": 0.25,  # Lower risk = better
        "confidence": 0.25,  # Higher confidence = better
        "dependencies": 0.2,  # Fewer deps = better
    }

    scored_options = []

    for option in options:
        # Effort score (normalize to 0-1, inverted so lower effort = higher score)
        max_effort = max(opt.estimated_effort_hours for opt in options)
        effort_score = 1.0 - (option.estimated_effort_hours / max_effort if max_effort > 0 else 0)

        # Risk score (low=1.0, medium=0.6, high=0.2)
        risk_scores = {RiskLevel.LOW: 1.0, RiskLevel.MEDIUM: 0.6, RiskLevel.HIGH: 0.2}
        risk_score = risk_scores.get(option.risk_level, 0.5)

        # Confidence score (already 0-1)
        confidence_score = option.confidence

        # Dependencies score (fewer = better)
        max_deps = max(len(opt.dependencies) for opt in options) if options else 1
        deps_score = 1.0 - (len(option.dependencies) / max_deps if max_deps > 0 else 0)

        # Weighted total
        total_score = (
            weights["effort"] * effort_score
            + weights["risk"] * risk_score
            + weights["confidence"] * confidence_score
            + weights["dependencies"] * deps_score
        )

        scored_options.append((option, total_score))

    # Sort by score (descending)
    scored_options.sort(key=lambda x: x[1], reverse=True)

    # Return best option
    return scored_options[0][0]


def generate_recommendation_reasoning(
    recommended: ArchitectureOption, all_options: list[ArchitectureOption]
) -> str:
    """Generate human-readable reasoning for recommendation.

    Args:
        recommended: The recommended option
        all_options: All options considered

    Returns:
        Reasoning explanation
    """
    reasons = [f"**Recommended: {recommended.name}**\n"]

    # Why this option?
    reasons.append("**Why this option:**")

    if recommended.risk_level == RiskLevel.LOW:
        reasons.append("- ✓ Low risk - safe choice")
    if recommended.estimated_effort_hours < 24:
        reasons.append(f"- ✓ Reasonable effort - ~{recommended.estimated_effort_hours:.0f} hours")
    if recommended.confidence >= 0.7:
        reasons.append(f"- ✓ High confidence - {recommended.confidence:.0%} certainty")
    if len(recommended.dependencies) == 0:
        reasons.append("- ✓ No external dependencies")

    # Key pros
    if recommended.pros:
        reasons.append("\n**Key advantages:**")
        for pro in recommended.pros[:3]:  # Top 3
            reasons.append(f"- {pro}")

    # Tradeoffs
    if recommended.cons:
        reasons.append("\n**Tradeoffs:**")
        for con in recommended.cons[:2]:  # Top 2
            reasons.append(f"- ⚠️  {con}")

    # Comparison to alternatives
    other_options = [opt for opt in all_options if opt != recommended]
    if other_options:
        reasons.append("\n**Why not alternatives:**")
        for other in other_options[:2]:  # Top 2 alternatives
            if other.risk_level == RiskLevel.HIGH:
                reasons.append(f"- {other.name}: Too risky ({other.risk_level.value} risk)")
            elif other.estimated_effort_hours > recommended.estimated_effort_hours * 2:
                reasons.append(
                    f"- {other.name}: Too much effort ({other.estimated_effort_hours:.0f}h vs {recommended.estimated_effort_hours:.0f}h)"
                )
            elif len(other.dependencies) > len(recommended.dependencies) + 2:
                reasons.append(f"- {other.name}: Too many dependencies ({len(other.dependencies)} vs {len(recommended.dependencies)})")

    return "\n".join(reasons)


def create_architecture_decision_record(decision: ArchitectureDecision, workspace_dir: Path) -> Path:
    """Create ADR (Architecture Decision Record) file.

    Args:
        decision: Architecture decision to document
        workspace_dir: Workspace root directory

    Returns:
        Path to created ADR file
    """
    adr_dir = workspace_dir / ".workspace-os" / "architecture-decisions"
    adr_dir.mkdir(parents=True, exist_ok=True)

    # ADR filename: NNNN-kebab-case-title.md
    adr_number = len(list(adr_dir.glob("*.md"))) + 1
    title_kebab = decision.issue_title.lower().replace(" ", "-")[:50]
    adr_path = adr_dir / f"{adr_number:04d}-{title_kebab}.md"

    # Selected option (user override or recommended)
    selected = decision.user_override or decision.recommended_option

    # Generate ADR content
    content = f"""# ADR {adr_number}: {decision.issue_title}

**Issue**: #{decision.issue_number}
**Date**: {decision.decision_date}
**Status**: Accepted
**Decided By**: {decision.decided_by}

---

## Context

{decision.research_summary if decision.research_summary else "No research summary available."}

Related to GitHub issue #{decision.issue_number}: {decision.issue_title}

---

## Decision

**Selected Approach**: {selected.name}

{selected.description}

### Effort Estimate

- **Hours**: {selected.estimated_effort_hours:.1f}
- **Risk Level**: {selected.risk_level.value.upper()}
- **Confidence**: {selected.confidence:.0%}

### Dependencies

{chr(10).join(f"- {dep}" for dep in selected.dependencies) if selected.dependencies else "None"}

### Implementation Steps

{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(selected.implementation_steps))}

---

## Rationale

{decision.recommendation_reasoning}

---

## Options Considered

"""

    for i, option in enumerate(decision.options, 1):
        is_selected = option == selected
        status = "✓ SELECTED" if is_selected else ""

        content += f"""
### Option {i}: {option.name} {status}

{option.description}

**Pros**:
{chr(10).join(f"- {pro}" for pro in option.pros)}

**Cons**:
{chr(10).join(f"- {con}" for con in option.cons)}

**Effort**: {option.estimated_effort_hours:.1f}h | **Risk**: {option.risk_level.value} | **Confidence**: {option.confidence:.0%}

"""

    if decision.user_override:
        content += f"""
---

## User Override

User selected **{decision.user_override.name}** instead of AI recommendation **{decision.recommended_option.name}**.

This override indicates user preference or additional context not captured in automated evaluation.
"""

    content += """
---

## Consequences

### Positive

TBD - To be filled after implementation

### Negative

TBD - To be filled after implementation

### Neutral

TBD - To be filled after implementation

---

## Notes

- This ADR was generated automatically by WOS Architecture Decision workflow
- Review and update after implementation completes
- Document actual vs. estimated effort and risk

"""

    # Write file
    adr_path.write_text(content, encoding="utf-8")

    # Also save JSON version
    json_path = adr_dir / f"{adr_number:04d}-{title_kebab}.json"
    json_data = {
        "adr_number": adr_number,
        "issue_number": decision.issue_number,
        "issue_title": decision.issue_title,
        "decision_date": decision.decision_date,
        "decided_by": decision.decided_by,
        "selected_option": {
            "name": selected.name,
            "description": selected.description,
            "estimated_effort_hours": selected.estimated_effort_hours,
            "risk_level": selected.risk_level.value,
            "dependencies": selected.dependencies,
            "implementation_steps": selected.implementation_steps,
        },
        "all_options": [
            {
                "name": opt.name,
                "description": opt.description,
                "pros": opt.pros,
                "cons": opt.cons,
                "estimated_effort_hours": opt.estimated_effort_hours,
                "risk_level": opt.risk_level.value,
                "confidence": opt.confidence,
                "dependencies": opt.dependencies,
            }
            for opt in decision.options
        ],
        "recommendation_reasoning": decision.recommendation_reasoning,
    }
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

    return adr_path


def parse_architecture_options_from_json(json_data: dict[str, Any]) -> list[ArchitectureOption]:
    """Parse architecture options from agent JSON response.

    Args:
        json_data: JSON response containing options

    Returns:
        List of ArchitectureOption objects
    """
    options = []

    for opt_data in json_data.get("options", []):
        risk_str = opt_data.get("risk_level", "medium").lower()
        risk_level = RiskLevel.MEDIUM
        if risk_str == "low":
            risk_level = RiskLevel.LOW
        elif risk_str == "high":
            risk_level = RiskLevel.HIGH

        options.append(
            ArchitectureOption(
                name=opt_data.get("name", "Unnamed option"),
                description=opt_data.get("description", ""),
                pros=opt_data.get("pros", []),
                cons=opt_data.get("cons", []),
                estimated_effort_hours=opt_data.get("estimated_effort_hours", 8.0),
                risk_level=risk_level,
                dependencies=opt_data.get("dependencies", []),
                implementation_steps=opt_data.get("implementation_steps", []),
                confidence=opt_data.get("confidence", 0.5),
            )
        )

    return options

# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Research phase for complex issues.

This module coordinates parallel research agents to gather information
before implementation begins.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from workspace_os.issue_complexity import ComplexityClassification


@dataclass
class ResearchFinding:
    """Single research finding from an agent."""

    category: str  # "pattern", "dependency", "precedent", "tradeoff"
    title: str
    description: str
    file_paths: list[str] = field(default_factory=list)
    confidence: float = 1.0  # 0.0-1.0
    agent: str = "unknown"


@dataclass
class ResearchReport:
    """Consolidated research results."""

    issue_number: int
    issue_title: str
    complexity: ComplexityClassification
    findings: list[ResearchFinding]
    similar_issues: list[dict[str, Any]]
    identified_dependencies: list[str]
    recommended_approach: str
    duration_seconds: float
    agents_used: int


def generate_research_prompts(
    complexity: ComplexityClassification, issue_data: dict[str, Any]
) -> list[tuple[str, str]]:
    """Generate research prompts based on issue complexity.

    Args:
        complexity: Complexity classification of the issue
        issue_data: GitHub issue data

    Returns:
        List of (category, prompt) tuples for parallel research
    """
    prompts = []
    title = issue_data.get("title", "")
    body = issue_data.get("body", "")

    # Pattern research (always)
    prompts.append(
        (
            "pattern",
            f"""Search the codebase for similar patterns to this issue:
Title: {title}
Description: {body}

Find:
1. Similar implementations or fixes
2. Existing patterns we should follow
3. Anti-patterns to avoid

Output JSON:
{{
    "patterns": [
        {{
            "title": "Pattern name",
            "description": "What it does",
            "file_paths": ["path/to/file.py"],
            "confidence": 0.8
        }}
    ]
}}
""",
        )
    )

    # Dependency research (if dependencies detected)
    if complexity.detected_dependencies:
        deps_text = ", ".join(complexity.detected_dependencies)
        prompts.append(
            (
                "dependency",
                f"""Analyze dependencies for this issue:
Required: {deps_text}

Check:
1. Are these dependencies already installed?
2. What versions are compatible?
3. Configuration needed?
4. Known issues or gotchas?

Output JSON:
{{
    "dependencies": [
        {{
            "name": "Dependency name",
            "status": "installed" | "missing" | "outdated",
            "current_version": "1.2.3" | null,
            "recommended_version": "2.0.0",
            "notes": "Additional configuration needed"
        }}
    ]
}}
""",
            )
        )

    # Architecture research (if complex)
    if complexity.requires_architecture_decision:
        prompts.append(
            (
                "architecture",
                f"""Research architectural approaches for:
Title: {title}
Description: {body}

Find:
1. How is similar functionality currently implemented?
2. What architectural patterns exist in this codebase?
3. What constraints should we consider?

Output JSON:
{{
    "existing_architecture": "Description of current approach",
    "constraints": ["Technical constraint 1", "Constraint 2"],
    "relevant_files": ["path/to/file.py"]
}}
""",
            )
        )

    # Bug investigation (if research needed)
    if complexity.requires_research and any(
        keyword in (title + body).lower() for keyword in ["bug", "issue", "problem", "leak", "error", "fail"]
    ):
        prompts.append(
            (
                "investigation",
                f"""Investigate this bug:
Title: {title}
Description: {body}

Find:
1. Related error logs or stack traces in code
2. Similar bugs fixed previously (git history)
3. Test files that might reproduce this
4. Files likely involved based on description

Output JSON:
{{
    "related_files": ["path/to/file.py"],
    "similar_fixes": [
        {{
            "commit": "abc123",
            "summary": "Fixed similar issue",
            "files": ["path/to/file.py"]
        }}
    ],
    "test_files": ["tests/test_related.py"]
}}
""",
            )
        )

    # Precedent research (for moderate+ complexity)
    if complexity.level.value in ("moderate", "complex"):
        prompts.append(
            (
                "precedent",
                f"""Find precedents for this type of issue:
Title: {title}

Search git history and closed issues for:
1. How were similar issues resolved?
2. What patterns worked well?
3. What approaches failed?

Output JSON:
{{
    "precedents": [
        {{
            "type": "issue" | "commit",
            "reference": "#123" | "abc123",
            "summary": "Brief description",
            "outcome": "success" | "reverted" | "incomplete",
            "lessons": "What we learned"
        }}
    ]
}}
""",
            )
        )

    return prompts


def synthesize_research_report(
    issue_data: dict[str, Any],
    complexity: ComplexityClassification,
    research_results: list[tuple[str, dict[str, Any]]],
    duration_seconds: float,
) -> ResearchReport:
    """Synthesize research results into a coherent report.

    Args:
        issue_data: GitHub issue data
        complexity: Complexity classification
        research_results: List of (category, result_json) from research agents
        duration_seconds: Total research duration

    Returns:
        Consolidated research report
    """
    findings = []
    similar_issues = []
    all_dependencies = set(complexity.detected_dependencies)

    for category, result in research_results:
        if result is None:
            continue

        # Extract findings based on category
        if category == "pattern" and "patterns" in result:
            for pattern in result["patterns"]:
                findings.append(
                    ResearchFinding(
                        category="pattern",
                        title=pattern.get("title", "Unknown pattern"),
                        description=pattern.get("description", ""),
                        file_paths=pattern.get("file_paths", []),
                        confidence=pattern.get("confidence", 0.5),
                        agent="pattern_researcher",
                    )
                )

        elif category == "dependency" and "dependencies" in result:
            for dep in result["dependencies"]:
                dep_name = dep.get("name", "Unknown")
                all_dependencies.add(dep_name)
                findings.append(
                    ResearchFinding(
                        category="dependency",
                        title=f"{dep_name} - {dep.get('status', 'unknown')}",
                        description=dep.get("notes", ""),
                        confidence=0.9,
                        agent="dependency_researcher",
                    )
                )

        elif category == "investigation" and "similar_fixes" in result:
            for fix in result["similar_fixes"]:
                findings.append(
                    ResearchFinding(
                        category="precedent",
                        title=f"Similar fix: {fix.get('summary', 'Unknown')}",
                        description=f"Commit {fix.get('commit', 'unknown')}",
                        file_paths=fix.get("files", []),
                        confidence=0.7,
                        agent="investigator",
                    )
                )

        elif category == "precedent" and "precedents" in result:
            for prec in result["precedents"]:
                if prec.get("outcome") == "success":
                    similar_issues.append(
                        {
                            "reference": prec.get("reference", "unknown"),
                            "summary": prec.get("summary", ""),
                            "lessons": prec.get("lessons", ""),
                        }
                    )

        elif category == "architecture" and "constraints" in result:
            for constraint in result.get("constraints", []):
                findings.append(
                    ResearchFinding(
                        category="tradeoff",
                        title="Architectural constraint",
                        description=constraint,
                        confidence=0.8,
                        agent="architect",
                    )
                )

    # Generate recommended approach
    recommended_approach = _generate_recommendation(complexity, findings, similar_issues)

    return ResearchReport(
        issue_number=issue_data.get("number", 0),
        issue_title=issue_data.get("title", ""),
        complexity=complexity,
        findings=findings,
        similar_issues=similar_issues,
        identified_dependencies=sorted(all_dependencies),
        recommended_approach=recommended_approach,
        duration_seconds=duration_seconds,
        agents_used=len(research_results),
    )


def _generate_recommendation(
    complexity: ComplexityClassification, findings: list[ResearchFinding], similar_issues: list[dict[str, Any]]
) -> str:
    """Generate recommended approach based on research findings."""
    recommendations = []

    # High-confidence patterns
    pattern_findings = [f for f in findings if f.category == "pattern" and f.confidence >= 0.7]
    if pattern_findings:
        best_pattern = max(pattern_findings, key=lambda f: f.confidence)
        recommendations.append(f"Follow existing pattern: {best_pattern.title}")
        if best_pattern.file_paths:
            recommendations.append(f"  Reference: {best_pattern.file_paths[0]}")

    # Precedents
    if similar_issues:
        recommendations.append(f"Review {len(similar_issues)} similar resolved issue(s)")
        if len(similar_issues) > 0 and "lessons" in similar_issues[0]:
            recommendations.append(f"  Key lesson: {similar_issues[0]['lessons']}")

    # Dependencies
    dep_findings = [f for f in findings if f.category == "dependency"]
    if dep_findings:
        recommendations.append(f"Address {len(dep_findings)} dependencies first")

    # Complexity-based recommendations
    if complexity.requires_architecture_decision:
        recommendations.append("⚠️  Requires architecture decision before implementation")

    if complexity.has_ambiguities:
        recommendations.append(f"⚠️  Clarify ambiguities: {complexity.has_ambiguities[0]}")

    # Default fallback
    if not recommendations:
        if complexity.level.value == "complex":
            recommendations.append("Break into smaller sub-tasks for incremental implementation")
        else:
            recommendations.append("Proceed with standard implementation")

    return "\n".join(recommendations)


def save_research_report(report: ResearchReport, workspace_dir: Path) -> Path:
    """Save research report to file.

    Args:
        report: Research report to save
        workspace_dir: Workspace root directory

    Returns:
        Path to saved report file
    """
    research_dir = workspace_dir / ".workspace-os" / "research"
    research_dir.mkdir(parents=True, exist_ok=True)

    report_path = research_dir / f"research_issue_{report.issue_number}.md"

    # Convert to markdown
    markdown_content = f"""# Research Report: Issue #{report.issue_number}

**Title**: {report.issue_title}
**Complexity**: {report.complexity.level.value.upper()} (score: {report.complexity.score:.1f}/10)
**Duration**: {report.duration_seconds:.1f}s
**Agents Used**: {report.agents_used}

---

## Complexity Analysis

- **Requires Research**: {report.complexity.requires_research}
- **Requires Architecture Decision**: {report.complexity.requires_architecture_decision}
- **Estimated Agents**: {report.complexity.estimated_agents}
- **Estimated Duration**: {report.complexity.estimated_duration_minutes} minutes

### Reasoning

{report.complexity.reasoning}

### Detected Ambiguities

{chr(10).join(f"- {amb}" for amb in report.complexity.has_ambiguities) if report.complexity.has_ambiguities else "None"}

---

## Research Findings ({len(report.findings)})

"""

    # Group findings by category
    for category in ["pattern", "dependency", "precedent", "tradeoff"]:
        category_findings = [f for f in report.findings if f.category == category]
        if category_findings:
            markdown_content += f"\n### {category.title()}s\n\n"
            for finding in category_findings:
                markdown_content += f"**{finding.title}** (confidence: {finding.confidence:.0%})\n"
                markdown_content += f"{finding.description}\n"
                if finding.file_paths:
                    markdown_content += f"Files: {', '.join(finding.file_paths)}\n"
                markdown_content += "\n"

    # Similar issues
    if report.similar_issues:
        markdown_content += "\n## Similar Resolved Issues\n\n"
        for issue in report.similar_issues:
            markdown_content += f"- **{issue['reference']}**: {issue['summary']}\n"
            if issue.get("lessons"):
                markdown_content += f"  Lesson: {issue['lessons']}\n"

    # Dependencies
    if report.identified_dependencies:
        markdown_content += "\n## Identified Dependencies\n\n"
        for dep in report.identified_dependencies:
            markdown_content += f"- {dep}\n"

    # Recommendation
    markdown_content += f"\n---\n\n## Recommended Approach\n\n{report.recommended_approach}\n"

    # Write to file
    report_path.write_text(markdown_content, encoding="utf-8")

    # Also save JSON version for programmatic access
    json_path = research_dir / f"research_issue_{report.issue_number}.json"
    json_data = {
        "issue_number": report.issue_number,
        "issue_title": report.issue_title,
        "complexity_level": report.complexity.level.value,
        "complexity_score": report.complexity.score,
        "findings": [
            {
                "category": f.category,
                "title": f.title,
                "description": f.description,
                "file_paths": f.file_paths,
                "confidence": f.confidence,
                "agent": f.agent,
            }
            for f in report.findings
        ],
        "similar_issues": report.similar_issues,
        "dependencies": report.identified_dependencies,
        "recommended_approach": report.recommended_approach,
        "duration_seconds": report.duration_seconds,
        "agents_used": report.agents_used,
    }
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

    return report_path

# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Complex Issue Multi-Phase Workflow.

Coordinates complexity detection, research, architecture decisions,
and implementation planning for complex issues.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from workspace_os.architecture_decision import (
    ArchitectureDecision,
    ArchitectureOption,
    create_architecture_decision_record,
    evaluate_options,
    generate_architecture_prompt,
    generate_recommendation_reasoning,
    parse_architecture_options_from_json,
)
from workspace_os.issue_complexity import ComplexityClassification, ComplexityLevel, classify_issue
from workspace_os.research_phase import (
    ResearchReport,
    generate_research_prompts,
    save_research_report,
    synthesize_research_report,
)


@dataclass
class WorkflowPhaseResult:
    """Result from a workflow phase."""

    phase_name: str
    duration_seconds: float
    success: bool
    output_path: Path | None = None
    data: Any = None
    error: str | None = None


@dataclass
class ComplexIssueWorkflowResult:
    """Overall workflow result."""

    issue_number: int
    complexity: ComplexityClassification
    phases_completed: list[WorkflowPhaseResult]
    total_duration_seconds: float
    implementation_plan: str
    ready_for_implementation: bool
    user_approval_required: bool = False
    pending_decision: ArchitectureDecision | None = None


class ComplexIssueWorkflow:
    """Orchestrates multi-phase workflow for complex issues."""

    def __init__(
        self,
        workspace_dir: Path,
        agent_executor: Callable[[str, dict[str, Any] | None], dict[str, Any]],
        enable_user_approval: bool = True,
    ):
        """Initialize workflow coordinator.

        Args:
            workspace_dir: Workspace root directory
            agent_executor: Function to execute agent prompts (prompt, schema) -> result
            enable_user_approval: Whether to pause for user approval on architecture decisions
        """
        self.workspace_dir = workspace_dir
        self.agent_executor = agent_executor
        self.enable_user_approval = enable_user_approval

    def execute(self, issue_data: dict[str, Any]) -> ComplexIssueWorkflowResult:
        """Execute full multi-phase workflow.

        Args:
            issue_data: GitHub issue data

        Returns:
            Workflow result with completion status and artifacts
        """
        workflow_start = time.perf_counter()
        phases_completed = []
        issue_number = issue_data.get("number", 0)

        print(f"[workflow] Starting multi-phase workflow for issue #{issue_number}")

        # Phase 0: Complexity Detection (always)
        complexity_result = self._phase_complexity_detection(issue_data)
        phases_completed.append(complexity_result)

        if not complexity_result.success:
            return ComplexIssueWorkflowResult(
                issue_number=issue_number,
                complexity=complexity_result.data,
                phases_completed=phases_completed,
                total_duration_seconds=time.perf_counter() - workflow_start,
                implementation_plan="Failed during complexity detection",
                ready_for_implementation=False,
            )

        complexity: ComplexityClassification = complexity_result.data

        print(f"[workflow] Complexity: {complexity.level.value.upper()} (score: {complexity.score:.1f}/10)")
        print(f"[workflow] {complexity.reasoning}")

        # Phase 1: Research (if needed)
        research_report = None
        if complexity.requires_research:
            research_result = self._phase_research(issue_data, complexity)
            phases_completed.append(research_result)

            if research_result.success:
                research_report = research_result.data

        # Phase 2: Architecture Decision (if needed)
        architecture_decision = None
        if complexity.requires_architecture_decision:
            architecture_result = self._phase_architecture_decision(issue_data, complexity, research_report)
            phases_completed.append(architecture_result)

            if architecture_result.success:
                architecture_decision = architecture_result.data

                # Check if user approval is needed
                if self.enable_user_approval:
                    print(f"[workflow] ⏸️  Architecture decision requires user approval")
                    return ComplexIssueWorkflowResult(
                        issue_number=issue_number,
                        complexity=complexity,
                        phases_completed=phases_completed,
                        total_duration_seconds=time.perf_counter() - workflow_start,
                        implementation_plan="Pending architecture approval",
                        ready_for_implementation=False,
                        user_approval_required=True,
                        pending_decision=architecture_decision,
                    )

        # Phase 3: Implementation Planning
        plan_result = self._phase_implementation_planning(issue_data, complexity, research_report, architecture_decision)
        phases_completed.append(plan_result)

        total_duration = time.perf_counter() - workflow_start

        if not plan_result.success:
            return ComplexIssueWorkflowResult(
                issue_number=issue_number,
                complexity=complexity,
                phases_completed=phases_completed,
                total_duration_seconds=total_duration,
                implementation_plan="Failed during planning",
                ready_for_implementation=False,
            )

        print(f"[workflow] ✓ Workflow completed in {total_duration:.1f}s")

        return ComplexIssueWorkflowResult(
            issue_number=issue_number,
            complexity=complexity,
            phases_completed=phases_completed,
            total_duration_seconds=total_duration,
            implementation_plan=plan_result.data,
            ready_for_implementation=True,
        )

    def _phase_complexity_detection(self, issue_data: dict[str, Any]) -> WorkflowPhaseResult:
        """Phase 0: Detect issue complexity."""
        print(f"[workflow] Phase 0: Complexity Detection")
        start = time.perf_counter()

        try:
            complexity = classify_issue(issue_data)
            duration = time.perf_counter() - start

            return WorkflowPhaseResult(
                phase_name="complexity_detection", duration_seconds=duration, success=True, data=complexity
            )
        except Exception as e:
            return WorkflowPhaseResult(
                phase_name="complexity_detection",
                duration_seconds=time.perf_counter() - start,
                success=False,
                error=str(e),
            )

    def _phase_research(
        self, issue_data: dict[str, Any], complexity: ComplexityClassification
    ) -> WorkflowPhaseResult:
        """Phase 1: Research & Analysis."""
        print(f"[workflow] Phase 1: Research & Analysis ({complexity.estimated_agents} agents)")
        start = time.perf_counter()

        try:
            # Generate research prompts
            research_prompts = generate_research_prompts(complexity, issue_data)
            print(f"[workflow]   Generated {len(research_prompts)} research tasks")

            # Execute research agents in parallel (simulated - in reality would use agent pool)
            research_results = []
            for category, prompt in research_prompts:
                try:
                    # Schema for structured research output
                    schema = {"type": "object", "properties": {}, "required": []}

                    result = self.agent_executor(prompt, schema)
                    research_results.append((category, result))
                except Exception as e:
                    print(f"[workflow]   Research agent '{category}' failed: {e}")
                    research_results.append((category, None))

            # Synthesize research report
            duration = time.perf_counter() - start
            report = synthesize_research_report(issue_data, complexity, research_results, duration)

            # Save report
            report_path = save_research_report(report, self.workspace_dir)
            print(f"[workflow]   ✓ Research report saved: {report_path}")

            return WorkflowPhaseResult(
                phase_name="research",
                duration_seconds=duration,
                success=True,
                output_path=report_path,
                data=report,
            )

        except Exception as e:
            return WorkflowPhaseResult(
                phase_name="research", duration_seconds=time.perf_counter() - start, success=False, error=str(e)
            )

    def _phase_architecture_decision(
        self,
        issue_data: dict[str, Any],
        complexity: ComplexityClassification,
        research_report: ResearchReport | None,
    ) -> WorkflowPhaseResult:
        """Phase 2: Architecture Decision."""
        print(f"[workflow] Phase 2: Architecture Decision")
        start = time.perf_counter()

        try:
            # Generate architecture options prompt
            research_summary = ""
            if research_report:
                research_summary = research_report.recommended_approach

            prompt = generate_architecture_prompt(issue_data, research_summary)

            # Schema for architecture options
            schema = {
                "type": "object",
                "properties": {
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "pros": {"type": "array", "items": {"type": "string"}},
                                "cons": {"type": "array", "items": {"type": "string"}},
                                "estimated_effort_hours": {"type": "number"},
                                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                                "dependencies": {"type": "array", "items": {"type": "string"}},
                                "implementation_steps": {"type": "array", "items": {"type": "string"}},
                                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                            },
                            "required": ["name", "description", "pros", "cons", "estimated_effort_hours", "risk_level"],
                        },
                    }
                },
                "required": ["options"],
            }

            # Execute agent to generate options
            result = self.agent_executor(prompt, schema)
            options = parse_architecture_options_from_json(result)

            if not options:
                raise ValueError("No architecture options generated")

            print(f"[workflow]   Generated {len(options)} architecture options")

            # Evaluate and recommend
            recommended = evaluate_options(options, context={})
            reasoning = generate_recommendation_reasoning(recommended, options)

            print(f"[workflow]   Recommended: {recommended.name}")

            # Create decision record
            decision = ArchitectureDecision(
                issue_number=issue_data.get("number", 0),
                issue_title=issue_data.get("title", ""),
                options=options,
                recommended_option=recommended,
                recommendation_reasoning=reasoning,
                decision_date=datetime.now().isoformat(),
                decided_by="ai",
                research_summary=research_summary,
            )

            # Save ADR
            adr_path = create_architecture_decision_record(decision, self.workspace_dir)
            print(f"[workflow]   ✓ ADR saved: {adr_path}")

            duration = time.perf_counter() - start

            return WorkflowPhaseResult(
                phase_name="architecture_decision",
                duration_seconds=duration,
                success=True,
                output_path=adr_path,
                data=decision,
            )

        except Exception as e:
            return WorkflowPhaseResult(
                phase_name="architecture_decision",
                duration_seconds=time.perf_counter() - start,
                success=False,
                error=str(e),
            )

    def _phase_implementation_planning(
        self,
        issue_data: dict[str, Any],
        complexity: ComplexityClassification,
        research_report: ResearchReport | None,
        architecture_decision: ArchitectureDecision | None,
    ) -> WorkflowPhaseResult:
        """Phase 3: Create implementation plan."""
        print(f"[workflow] Phase 3: Implementation Planning")
        start = time.perf_counter()

        try:
            plan_sections = []

            # Issue summary
            plan_sections.append(f"# Implementation Plan: Issue #{issue_data.get('number', 0)}\n")
            plan_sections.append(f"**Title**: {issue_data.get('title', '')}\n")
            plan_sections.append(f"**Complexity**: {complexity.level.value.upper()}\n")

            # Research findings
            if research_report:
                plan_sections.append("\n## Research Findings\n")
                plan_sections.append(f"{research_report.recommended_approach}\n")

                if research_report.identified_dependencies:
                    plan_sections.append("\n### Dependencies to Address\n")
                    for dep in research_report.identified_dependencies:
                        plan_sections.append(f"- {dep}\n")

            # Architecture decision
            if architecture_decision:
                selected = architecture_decision.user_override or architecture_decision.recommended_option
                plan_sections.append("\n## Architecture\n")
                plan_sections.append(f"**Approach**: {selected.name}\n")
                plan_sections.append(f"{selected.description}\n")

                plan_sections.append("\n### Implementation Steps\n")
                for i, step in enumerate(selected.implementation_steps, 1):
                    plan_sections.append(f"{i}. {step}\n")

            # Estimated resources
            plan_sections.append("\n## Resources\n")
            plan_sections.append(f"**Estimated Agents**: {complexity.estimated_agents}\n")
            plan_sections.append(f"**Estimated Duration**: {complexity.estimated_duration_minutes} minutes\n")

            if architecture_decision:
                selected = architecture_decision.user_override or architecture_decision.recommended_option
                plan_sections.append(f"**Estimated Effort**: {selected.estimated_effort_hours:.1f} hours\n")
                plan_sections.append(f"**Risk Level**: {selected.risk_level.value.upper()}\n")

            # Tests needed
            plan_sections.append("\n## Testing\n")
            plan_sections.append("- Unit tests for new functionality\n")
            plan_sections.append("- Integration tests if dependencies involved\n")
            plan_sections.append("- Validate quality gates pass\n")

            plan = "".join(plan_sections)

            # Save plan
            plan_dir = self.workspace_dir / ".workspace-os" / "implementation-plans"
            plan_dir.mkdir(parents=True, exist_ok=True)
            plan_path = plan_dir / f"plan_issue_{issue_data.get('number', 0)}.md"
            plan_path.write_text(plan, encoding="utf-8")

            print(f"[workflow]   ✓ Implementation plan saved: {plan_path}")

            duration = time.perf_counter() - start

            return WorkflowPhaseResult(
                phase_name="implementation_planning",
                duration_seconds=duration,
                success=True,
                output_path=plan_path,
                data=plan,
            )

        except Exception as e:
            return WorkflowPhaseResult(
                phase_name="implementation_planning",
                duration_seconds=time.perf_counter() - start,
                success=False,
                error=str(e),
            )


def should_use_complex_workflow(issue_data: dict[str, Any]) -> tuple[bool, ComplexityClassification]:
    """Determine if an issue should use the complex workflow.

    Args:
        issue_data: GitHub issue data

    Returns:
        (should_use, complexity_classification)
    """
    complexity = classify_issue(issue_data)

    # Use complex workflow for MODERATE or COMPLEX issues
    should_use = complexity.level in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX)

    return should_use, complexity

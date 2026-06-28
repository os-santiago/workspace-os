# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Integration layer between complex issue workflow and cycle.py."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from workspace_os.architecture_decision import ArchitectureDecision
from workspace_os.complex_issue_workflow import ComplexIssueWorkflow, ComplexIssueWorkflowResult
from workspace_os.issue_complexity import ComplexityClassification, ComplexityLevel
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.model_provider import build_model_router
from workspace_os.workflow_agent_executor import create_workflow_agent_executor
from workspace_os.workflow_approval import prompt_user_for_architecture_approval


def should_use_complex_workflow(complexity: ComplexityClassification) -> bool:
    """Determine if issue should use complex workflow based on complexity.

    Args:
        complexity: Complexity classification

    Returns:
        True if should use multi-phase workflow (MODERATE or COMPLEX)
    """
    # Check environment variable override
    if os.environ.get("WOS_DISABLE_COMPLEX_WORKFLOW", "").lower() in ("true", "1", "yes"):
        return False

    return complexity.level in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX)


def execute_complex_workflow_for_issue(
    issue_data: dict[str, Any],
    complexity: ComplexityClassification,
    workspace_name: str,
    workspace_root: Path,
    memory_store: WorkspaceMemoryStore,
    config_path: Path | None = None,
    agent_type: str = "claude",
    agent_runner: Callable[..., object] | None = None,
    enable_user_approval: bool = True,
) -> ComplexIssueWorkflowResult:
    """Execute complex issue workflow for an issue.

    Args:
        issue_data: GitHub issue data
        complexity: Complexity classification
        workspace_name: Name of workspace
        workspace_root: Root directory
        memory_store: Memory store
        agent_type: Agent to use for workflow
        agent_runner: Optional custom agent runner
        enable_user_approval: Whether to prompt for architecture approval

    Returns:
        Workflow result with implementation plan and artifacts
    """
    print(f"[workflow] Issue #{issue_data['number']} classified as {complexity.level.value.upper()}")
    print(f"[workflow]   Score: {complexity.score:.1f}/10")
    print(f"[workflow]   Reasoning: {complexity.reasoning}")

    if complexity.has_ambiguities:
        print(f"[workflow]   ⚠️  Ambiguities detected:")
        for amb in complexity.has_ambiguities:
            print(f"[workflow]      - {amb}")

    if complexity.detected_dependencies:
        print(f"[workflow]   📦 Dependencies: {', '.join(complexity.detected_dependencies)}")

    model_router = build_model_router(config_path) if config_path is not None else None
    if model_router is not None:
        selected_provider = model_router.select_provider("planning")
        print(f"[workflow] model_provider={selected_provider.name}")

    # Create agent executor
    agent_executor = create_workflow_agent_executor(
        workspace_name=workspace_name,
        workspace_root=workspace_root,
        memory_store=memory_store,
        agent_type=agent_type,
        agent_runner=agent_runner,
        model_router=model_router,
    )

    # Execute workflow
    workflow = ComplexIssueWorkflow(
        workspace_dir=workspace_root, agent_executor=agent_executor, enable_user_approval=enable_user_approval
    )

    print(f"[workflow] Starting multi-phase workflow...")
    result = workflow.execute(issue_data)

    # Handle user approval if needed
    if result.user_approval_required and result.pending_decision:
        print(f"\n[workflow] ⏸️  Architecture decision requires user approval")

        # Check if auto-approve enabled
        auto_approve = os.environ.get("WOS_AUTO_APPROVE_ARCHITECTURE", "").lower() in ("true", "1", "yes")

        try:
            selected_option = prompt_user_for_architecture_approval(
                decision=result.pending_decision, workspace_dir=workspace_root, auto_approve=auto_approve
            )

            # Update decision with user selection
            if selected_option != result.pending_decision.recommended_option:
                result.pending_decision.user_override = selected_option

            # Continue workflow with approved option
            # (In full implementation, would re-execute planning phase with selected option)
            print(f"[workflow] ✓ Continuing with approved architecture: {selected_option.name}")
            result.ready_for_implementation = True

        except KeyboardInterrupt:
            # User cancelled - workflow remains paused
            print(f"\n[workflow] Workflow paused. Review ADR and resume manually.")
            raise

    # Display workflow summary
    print(f"\n[workflow] Workflow completed in {result.total_duration_seconds:.1f}s")
    for phase in result.phases_completed:
        status = "✓" if phase.success else "✗"
        print(f"[workflow]   {status} {phase.phase_name}: {phase.duration_seconds:.1f}s")
        if phase.output_path:
            print(f"[workflow]      → {phase.output_path}")

    return result


def build_enhanced_work_prompt_with_workflow(
    base_prompt: str, workflow_result: ComplexIssueWorkflowResult | None
) -> str:
    """Enhance work prompt with workflow findings.

    Args:
        base_prompt: Base work prompt
        workflow_result: Optional workflow result with research/architecture

    Returns:
        Enhanced prompt with workflow context
    """
    if not workflow_result or not workflow_result.ready_for_implementation:
        return base_prompt

    # Prepend workflow context to prompt
    enhanced_sections = [base_prompt, "\n---\n", "## Multi-Phase Workflow Results\n"]

    # Add implementation plan
    if workflow_result.implementation_plan:
        enhanced_sections.append(f"\n### Implementation Plan\n\n{workflow_result.implementation_plan}\n")

    # Add links to artifacts
    for phase in workflow_result.phases_completed:
        if phase.output_path:
            enhanced_sections.append(f"\n**{phase.phase_name}**: See `{phase.output_path}`\n")

    # Add guidance
    enhanced_sections.append(
        "\n**Instructions**: Follow the implementation plan above. "
        "Reference the research findings and architecture decision when implementing.\n"
    )

    return "".join(enhanced_sections)

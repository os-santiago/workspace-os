# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""User approval handling for complex issue workflow architecture decisions."""

from __future__ import annotations

from pathlib import Path

from workspace_os.architecture_decision import (
    ArchitectureDecision,
    ArchitectureOption,
    create_architecture_decision_record,
)


def prompt_user_for_architecture_approval(
    decision: ArchitectureDecision, workspace_dir: Path, auto_approve: bool = False
) -> ArchitectureOption:
    """Prompt user to approve or select an architecture option.

    Args:
        decision: Architecture decision with options
        workspace_dir: Workspace directory for ADR updates
        auto_approve: If True, automatically select recommended option

    Returns:
        Selected architecture option
    """
    if auto_approve:
        print(f"[workflow] Auto-approving recommended option: {decision.recommended_option.name}")
        return decision.recommended_option

    # Display decision to user
    print("\n" + "=" * 70)
    print("⚠️  ARCHITECTURE DECISION REQUIRED")
    print("=" * 70)
    print(f"\nIssue: #{decision.issue_number} - {decision.issue_title}\n")

    # Show all options
    for i, option in enumerate(decision.options, 1):
        is_recommended = option == decision.recommended_option
        marker = "✓ RECOMMENDED" if is_recommended else ""

        print(f"\n[{i}] {option.name} {marker}")
        print(f"    {option.description[:100]}...")
        print(f"    Effort: {option.estimated_effort_hours:.1f}h | Risk: {option.risk_level.value} | Confidence: {option.confidence:.0%}")

        if is_recommended:
            print(f"\n    Why recommended:")
            # Show top 2 pros
            for pro in option.pros[:2]:
                print(f"      • {pro}")

    # Show recommendation reasoning
    print(f"\n{decision.recommendation_reasoning}\n")
    print("=" * 70)

    # Prompt for selection
    while True:
        choice = input(f"\nSelect option (1-{len(decision.options)}, or 'q' to quit): ").strip()

        if choice.lower() == 'q':
            raise KeyboardInterrupt("User cancelled workflow - architecture decision required")

        if choice.isdigit() and 1 <= int(choice) <= len(decision.options):
            selected_idx = int(choice) - 1
            selected = decision.options[selected_idx]

            print(f"\n✓ Selected: {selected.name}")

            # Update ADR if user overrode recommendation
            if selected != decision.recommended_option:
                print(f"   (User override - original recommendation was {decision.recommended_option.name})")
                decision.user_override = selected
                decision.decided_by = "user"
                # Re-create ADR with user selection
                adr_path = create_architecture_decision_record(decision, workspace_dir)
                print(f"   Updated ADR: {adr_path}")

            return selected

        print(f"Invalid choice. Please enter a number between 1 and {len(decision.options)}, or 'q' to quit.")


def check_for_pending_approval(workspace_dir: Path) -> Path | None:
    """Check if there's a pending architecture decision requiring approval.

    Args:
        workspace_dir: Workspace directory

    Returns:
        Path to pending ADR file if exists, None otherwise
    """
    adr_dir = workspace_dir / ".workspace-os" / "architecture-decisions"
    if not adr_dir.exists():
        return None

    # Look for ADRs with "Status: Pending" (not implemented yet)
    # For now, return None - this would be enhanced to track pending decisions
    return None

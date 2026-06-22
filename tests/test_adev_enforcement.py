# Copyright 2026 Workspace OS Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Test ADEV workflow enforcement in WOS cycles.

Ensures Issue #86 fix: WOS ALWAYS enforces PR workflow regardless of
WOS_ENABLE_ISSUE_ASSIGNMENT setting.
"""

import os
from pathlib import Path
from workspace_os.cycle import _build_cycle_work_prompt
from workspace_os.memory import WorkspaceMemoryStore


def test_pr_workflow_always_enforced_with_assignment_disabled(tmp_path: Path) -> None:
    """
    Test that PR workflow instructions are present even when issue assignment is disabled.

    Regression test for Issue #86:
    Previously, when WOS_ENABLE_ISSUE_ASSIGNMENT=false, PR instructions were skipped.
    After fix, they MUST always be present (ADEV compliance).
    """
    # Setup
    memory_store = WorkspaceMemoryStore(tmp_path / "memory")
    memory_store.ensure_schema()
    sources = []

    # Simulate WOS_ENABLE_ISSUE_ASSIGNMENT=false (the bug condition)
    # In this mode, assigned_issue=None and gh_issues_hint=""
    # Previously this caused PR instructions to be skipped

    # Build prompt with NO issue assignment (simulates disabled mode)
    result = _build_cycle_work_prompt(
        sources=sources,
        memory_store=memory_store,
        workspace_name="test",
        objective="Implement feature X",
        note=None,
        iteration_number=1,
        assigned_issue=None,  # No issue assigned (bug condition)
        role="primary",
        recent_work=None,
    )

    prompt = result["primary:claude"]

    # CRITICAL ASSERTIONS: After Issue #86 fix, these MUST pass

    # 1. ADEV rules must be present
    assert "ADEV-COMPLIANT WORKFLOW" in prompt, "ADEV workflow header missing"
    assert "ADEV Rule #1" in prompt, "ADEV Rule #1 not enforced"
    assert "ADEV Rule #3" in prompt, "ADEV Rule #3 not enforced"
    assert "ADEV Rule #48" in prompt, "ADEV Rule #48 not enforced"

    # 2. PR workflow instructions must be present
    assert "gh pr create" in prompt, "PR creation instructions missing"
    assert "Pull Request" in prompt, "Pull Request mention missing"
    assert "Closes #" in prompt, "Issue linking instructions missing"

    # 3. Prohibitions must be stated
    assert "NEVER commit directly to main" in prompt, "Main commit prohibition missing"
    assert "ONE issue" in prompt or "1 issue" in prompt, "Atomic commit rule missing"
    assert "do NOT batch" in prompt or "PROHIBITED" in prompt, "Batch commit warning missing"

    # 4. Workflow steps must be present
    assert "git checkout -b" in prompt, "Branch creation missing"
    assert "git push" in prompt, "Push instructions missing"
    assert "atomic" in prompt.lower(), "Atomic commit principle missing"

    # 5. Conventional Commits must be mentioned
    assert "Conventional Commits" in prompt, "Conventional Commits requirement missing"


def test_pr_workflow_enforced_with_assignment_enabled(tmp_path: Path) -> None:
    """
    Test that PR workflow is still enforced when issue assignment IS enabled.

    Ensures we didn't break the original working mode.
    """
    memory_store = WorkspaceMemoryStore(tmp_path / "memory")
    memory_store.ensure_schema()
    sources = []

    # Build prompt WITH issue assignment (original working mode)
    result = _build_cycle_work_prompt(
        sources=sources,
        memory_store=memory_store,
        workspace_name="test",
        objective="Fix issue #123",
        note=None,
        iteration_number=1,
        assigned_issue={"number": 123, "title": "Test issue"},
        role="primary",
        recent_work=None,
    )

    prompt = result["primary:claude"]

    # Should have both ADEV enforcement AND issue-specific context
    assert "ADEV-COMPLIANT WORKFLOW" in prompt
    assert "gh pr create" in prompt
    assert "YOUR TASK: Work ONLY on issue #123" in prompt
    assert "fix/issue-123" in prompt

def test_adev_prohibitions_clearly_stated(tmp_path: Path) -> None:
    """
    Test that ADEV prohibitions are explicitly stated to prevent violations.
    """
    memory_store = WorkspaceMemoryStore(tmp_path / "memory")
    memory_store.ensure_schema()
    sources = []

    result = _build_cycle_work_prompt(
        sources=sources,
        memory_store=memory_store,
        workspace_name="test",
        objective="Test",
        note=None,
        iteration_number=1,
        assigned_issue=None,
        role="primary",
        recent_work=None,
    )

    prompt = result["primary:claude"]

    # Verify prohibitions are explicit
    prohibited_section = prompt[prompt.find("PROHIBITED"):] if "PROHIBITED" in prompt else ""

    assert "Batch commits" in prohibited_section or "batch" in prohibited_section
    assert "Direct commits to main" in prompt
    assert "Mixing unrelated changes" in prompt or "single responsibility" in prompt


def test_workflow_instructions_are_numbered_steps(tmp_path: Path) -> None:
    """
    Test that workflow is presented as numbered steps for clarity.
    """
    memory_store = WorkspaceMemoryStore(tmp_path / "memory")
    memory_store.ensure_schema()
    sources = []

    result = _build_cycle_work_prompt(
        sources=sources,
        memory_store=memory_store,
        workspace_name="test",
        objective="Test",
        note=None,
        iteration_number=1,
        assigned_issue=None,
        role="primary",
        recent_work=None,
    )

    prompt = result["primary:claude"]

    # Check for numbered workflow steps
    assert "1." in prompt and "NEVER commit directly to main" in prompt
    assert "2." in prompt and "ONE issue" in prompt
    assert "8." in prompt and "Pull Request" in prompt
    assert "11." in prompt  # Should have at least 11 steps


def test_regression_issue_86_batch_commit_prevented(tmp_path: Path) -> None:
    """
    Specific regression test for the exact bug found in homedir cycle.

    Homedir cycle created:
    - Commit 652bd272 with 4 issues (895, 887, 875, 886)
    - No PR created
    - This violates ADEV rules

    After fix, agents should be instructed NOT to do this.
    """
    memory_store = WorkspaceMemoryStore(tmp_path / "memory")
    memory_store.ensure_schema()
    sources = []

    # Simulate the exact configuration that caused the bug
    os.environ["WOS_ENABLE_ISSUE_ASSIGNMENT"] = "false"

    try:
        result = _build_cycle_work_prompt(
            sources=sources,
            memory_store=memory_store,
            workspace_name="homedir",
            objective="Resolve issues #895, #887, #875, #886",  # Multi-issue objective
            note=None,
            iteration_number=1,
            assigned_issue=None,  # No assignment (disabled mode)
            role="primary",
            recent_work=None,
        )

        prompt = result["primary:claude"]

        # After fix, prompt MUST warn against batching
        assert "do NOT batch" in prompt or "ONE issue" in prompt
        assert "gh pr create" in prompt  # Must still require PR
        assert "atomic" in prompt.lower()

        # Should not have specific issue assignment (since disabled mode gives no assigned_issue)
        # The prompt may still have guidance text like "NOTE: If working on..." or simply no assignment

    finally:
        # Cleanup
        if "WOS_ENABLE_ISSUE_ASSIGNMENT" in os.environ:
            del os.environ["WOS_ENABLE_ISSUE_ASSIGNMENT"]

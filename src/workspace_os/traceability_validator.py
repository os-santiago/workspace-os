"""
Traceability Compliance Validator for Workspace OS

This module provides automated validation of PR-to-issue traceability and quality gate
enforcement. It verifies that work items properly link to GitHub issues and PRs,
validates closing keywords, checks quality gate compliance, and generates compliance reports.

Usage:
    # Validate PR linking for a work item
    result = validate_pr_links_to_issue(
        workspace_root=Path("/path/to/repo"),
        issue_number=123,
        work_item_number=5,
        agent_type="claude"
    )

    # Run full traceability validation
    validator = TraceabilityValidator(workspace_root=Path("/path/to/repo"))
    report = validator.validate_cycle_traceability(cycle_id=2)

    # Check quality gate compliance
    gate_result = validator.validate_quality_gates(checkpoint_data)
"""

import json
import re
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Any
import sqlite3


class PRState(Enum):
    """PR state enumeration matching GitHub states."""
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"
    DRAFT = "draft"
    NOT_CREATED = "not_created"


class ValidationMode(Enum):
    """Enforcement mode for validation failures."""
    SOFT = "soft"  # Log warnings, don't block
    HARD = "hard"  # Block completion on failures
    BATCH = "batch"  # Defer validation to checkpoint


class CheckStatus(Enum):
    """Combined status for required checks."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


@dataclass
class PRValidationResult:
    """Result of PR-to-issue link validation."""
    valid: bool
    reason: str
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    branch_name: Optional[str] = None
    head_commit_sha: Optional[str] = None
    pr_state: Optional[str] = None
    closing_keywords_verified: bool = False
    timeline_cross_ref_confirmed: bool = False
    linked_issues: list[dict[str, Any]] = field(default_factory=list)
    validation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class QualityGateResult:
    """Result of quality gate validation."""
    gate_name: str
    passed: bool
    details: str
    blocking: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TraceabilityReport:
    """Comprehensive traceability compliance report."""
    cycle_id: int
    validation_timestamp: str
    total_work_items: int
    prs_created: int
    prs_with_valid_links: int
    prs_missing_keywords: int
    prs_not_created: int
    issues_closed: int
    quality_gates_passed: int
    quality_gates_failed: int
    avg_work_to_pr_seconds: Optional[float] = None
    avg_pr_to_merge_seconds: Optional[float] = None
    validation_failures: list[dict[str, Any]] = field(default_factory=list)
    gate_failures: list[dict[str, Any]] = field(default_factory=list)
    compliance_rate: float = 0.0

    def __post_init__(self):
        """Calculate compliance rate."""
        if self.total_work_items > 0:
            self.compliance_rate = (self.prs_with_valid_links / self.total_work_items) * 100


class TraceabilityValidator:
    """
    Main validator class for traceability compliance.

    Validates:
    - PR creation and issue linking
    - Closing keyword presence in PR bodies
    - GitHub timeline cross-references
    - Quality gate compliance
    - Checkpoint pass rates
    """

    # GitHub closing keywords
    CLOSING_KEYWORDS = [
        "close", "closes", "closed",
        "fix", "fixes", "fixed",
        "resolve", "resolves", "resolved"
    ]

    # Timeout for GitHub API calls
    DEFAULT_TIMEOUT = 10.0

    def __init__(
        self,
        workspace_root: Path,
        validation_mode: ValidationMode = ValidationMode.SOFT,
        timeout_seconds: float = DEFAULT_TIMEOUT
    ):
        """
        Initialize validator.

        Args:
            workspace_root: Root directory of the workspace repository
            validation_mode: Enforcement mode (soft/hard/batch)
            timeout_seconds: Timeout for subprocess calls
        """
        self.workspace_root = workspace_root
        self.validation_mode = validation_mode
        self.timeout_seconds = timeout_seconds

    def validate_pr_links_to_issue(
        self,
        issue_number: int,
        work_item_number: int,
        agent_type: str,
        role: str = "primary"
    ) -> PRValidationResult:
        """
        Verify that a PR was created linking to the assigned issue.

        Args:
            issue_number: GitHub issue number assigned to work item
            work_item_number: Work item sequence number
            agent_type: Agent that performed the work (opencode/claude)
            role: Agent role (primary/cross-check/observer)

        Returns:
            PRValidationResult with validation status and metadata
        """
        # Skip validation for non-primary roles
        if role in ("cross-check", "observer"):
            return PRValidationResult(
                valid=True,
                reason=f"{role}_role_skip",
                pr_number=None,
                pr_url=None
            )

        try:
            # Query recent PRs that reference this issue
            prs = self._query_recent_prs_for_issue(issue_number)

            if not prs:
                return PRValidationResult(
                    valid=False,
                    reason=f"No recent PR found linking to issue #{issue_number}",
                    pr_number=None,
                    pr_url=None
                )

            # Filter to most recent PR (within last 10 minutes)
            recent_pr = self._filter_recent_pr(prs)

            if not recent_pr:
                return PRValidationResult(
                    valid=False,
                    reason=f"No PR created in last 10 minutes for issue #{issue_number}",
                    pr_number=None,
                    pr_url=None
                )

            # Validate closing keywords in PR body
            keywords_valid, keyword_used = self._validate_closing_keywords(
                recent_pr.get("body", ""),
                issue_number
            )

            # Check timeline cross-reference
            cross_ref_valid = self._validate_timeline_cross_reference(
                issue_number,
                recent_pr["number"]
            )

            # Extract linked issues from PR body
            linked_issues = self._extract_linked_issues(recent_pr.get("body", ""))

            return PRValidationResult(
                valid=keywords_valid,
                reason="PR correctly links to issue with closing keyword" if keywords_valid
                       else f"PR #{recent_pr['number']} references issue but missing closing keyword",
                pr_number=recent_pr["number"],
                pr_url=recent_pr.get("url"),
                branch_name=recent_pr.get("headRefName"),
                head_commit_sha=recent_pr.get("headRefOid"),
                pr_state=recent_pr.get("state", "open").lower(),
                closing_keywords_verified=keywords_valid,
                timeline_cross_ref_confirmed=cross_ref_valid,
                linked_issues=linked_issues
            )

        except subprocess.TimeoutExpired:
            return PRValidationResult(
                valid=False,
                reason=f"PR verification timed out after {self.timeout_seconds}s",
                pr_number=None,
                pr_url=None
            )
        except Exception as e:
            return PRValidationResult(
                valid=False,
                reason=f"PR verification error: {str(e)[:200]}",
                pr_number=None,
                pr_url=None
            )

    def _query_recent_prs_for_issue(self, issue_number: int) -> list[dict[str, Any]]:
        """
        Query GitHub for recent PRs referencing the issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            List of PR objects from gh CLI
        """
        result = subprocess.run(
            [
                "gh", "pr", "list",
                "--search", f"#{issue_number} in:body",
                "--limit", "5",
                "--json", "number,title,body,createdAt,url,headRefName,headRefOid,state",
                "--state", "all"
            ],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False
        )

        if result.returncode != 0:
            # Check for rate limiting
            if "rate limit" in result.stderr.lower():
                raise RuntimeError("GitHub API rate limit exceeded")
            raise RuntimeError(f"gh pr list failed: {result.stderr[:200]}")

        return json.loads(result.stdout)

    def _filter_recent_pr(self, prs: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """
        Filter PRs to find most recently created (within 10 minutes).

        Args:
            prs: List of PR objects

        Returns:
            Most recent PR or None
        """
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(minutes=10)

        recent_prs = []
        for pr in prs:
            created_at_str = pr["createdAt"].replace("Z", "+00:00")
            created_at = datetime.fromisoformat(created_at_str)
            if created_at >= recent_cutoff:
                recent_prs.append((created_at, pr))

        if not recent_prs:
            return None

        # Return most recent
        recent_prs.sort(key=lambda x: x[0], reverse=True)
        return recent_prs[0][1]

    def _validate_closing_keywords(
        self,
        pr_body: str,
        issue_number: int
    ) -> tuple[bool, Optional[str]]:
        """
        Validate PR body contains closing keyword for issue.

        Args:
            pr_body: PR description text
            issue_number: Issue number to check for

        Returns:
            (valid, keyword_used) tuple
        """
        if not pr_body:
            return False, None

        body_lower = pr_body.lower()

        # Check each closing keyword
        for keyword in self.CLOSING_KEYWORDS:
            # Match "Closes #123", "Closes: #123", "Closes #123.", etc.
            patterns = [
                f"{keyword} #{issue_number}",
                f"{keyword}: #{issue_number}",
                f"{keyword} #{issue_number}.",
                f"{keyword} #{issue_number},",
            ]
            for pattern in patterns:
                if pattern in body_lower:
                    return True, keyword

        return False, None

    def _validate_timeline_cross_reference(
        self,
        issue_number: int,
        pr_number: int
    ) -> bool:
        """
        Check GitHub timeline for cross-reference event.

        Args:
            issue_number: Issue number
            pr_number: PR number

        Returns:
            True if cross-reference exists
        """
        try:
            # Get repository info
            repo_info = self._get_repo_info()
            if not repo_info:
                return False

            result = subprocess.run(
                [
                    "gh", "api",
                    f"repos/{repo_info['owner']}/{repo_info['name']}/issues/{issue_number}/timeline",
                    "--jq", f'.[] | select(.event=="cross-referenced" and .source.issue.number=={pr_number})'
                ],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False
            )

            return bool(result.stdout.strip())

        except Exception:
            # Non-critical check, return False on error
            return False

    def _get_repo_info(self) -> Optional[dict[str, str]]:
        """Get repository owner and name from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False
            )

            if result.returncode != 0:
                return None

            # Parse owner/repo from URL
            # Handles: git@github.com:owner/repo.git or https://github.com/owner/repo.git
            url = result.stdout.strip()
            match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', url)
            if match:
                return {"owner": match.group(1), "name": match.group(2)}

            return None

        except Exception:
            return None

    def _extract_linked_issues(self, pr_body: str) -> list[dict[str, Any]]:
        """
        Extract all issue references from PR body.

        Args:
            pr_body: PR description text

        Returns:
            List of {number: int, keyword: str} dicts
        """
        if not pr_body:
            return []

        linked = []

        # Pattern: (keyword) #(number)
        pattern = r'\b(' + '|'.join(self.CLOSING_KEYWORDS) + r')\s*:?\s*#(\d+)'
        matches = re.finditer(pattern, pr_body, re.IGNORECASE)

        for match in matches:
            keyword = match.group(1).lower()
            number = int(match.group(2))
            linked.append({"number": number, "keyword": keyword})

        return linked

    def validate_quality_gates(
        self,
        checkpoint_data: dict[str, Any]
    ) -> list[QualityGateResult]:
        """
        Validate quality gate compliance from checkpoint data.

        Args:
            checkpoint_data: Checkpoint evaluation results

        Returns:
            List of QualityGateResult objects
        """
        results = []

        # Health gate
        results.append(QualityGateResult(
            gate_name="Health Gate",
            passed=checkpoint_data.get("health_ok", False),
            details=checkpoint_data.get("health_details", "No details"),
            blocking=True
        ))

        # Stability gate
        results.append(QualityGateResult(
            gate_name="Stability Gate",
            passed=checkpoint_data.get("stability_ok", False),
            details=checkpoint_data.get("stability_details", "No details"),
            blocking=True
        ))

        # Security gate
        results.append(QualityGateResult(
            gate_name="Security Gate",
            passed=checkpoint_data.get("security_ok", False),
            details=checkpoint_data.get("security_details", "No details"),
            blocking=True
        ))

        # Quality gate
        results.append(QualityGateResult(
            gate_name="Quality Gate",
            passed=checkpoint_data.get("quality_ok", False),
            details=checkpoint_data.get("quality_details", "No details"),
            blocking=True
        ))

        return results

    def validate_cycle_traceability(
        self,
        memory_db_path: Path,
        cycle_id: int
    ) -> TraceabilityReport:
        """
        Validate traceability for entire cycle.

        Args:
            memory_db_path: Path to memory.db SQLite database
            cycle_id: Cycle ID to validate

        Returns:
            TraceabilityReport with compliance metrics
        """
        conn = sqlite3.connect(memory_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Query work items from agent_queue (if table exists)
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='agent_queue'
            """)

            if not cursor.fetchone():
                # Fallback: empty report
                return TraceabilityReport(
                    cycle_id=cycle_id,
                    validation_timestamp=datetime.now(timezone.utc).isoformat(),
                    total_work_items=0,
                    prs_created=0,
                    prs_with_valid_links=0,
                    prs_missing_keywords=0,
                    prs_not_created=0,
                    issues_closed=0,
                    quality_gates_passed=0,
                    quality_gates_failed=0
                )

            # Get completed work items for this cycle
            cursor.execute("""
                SELECT
                    task_id,
                    metadata,
                    started_at,
                    completed_at
                FROM agent_queue
                WHERE status = 'completed'
                AND task_id LIKE ?
                ORDER BY started_at
            """, (f"%cycle-{cycle_id}-%",))

            work_items = cursor.fetchall()

            # Initialize counters
            total_work_items = len(work_items)
            prs_created = 0
            prs_with_valid_links = 0
            prs_missing_keywords = 0
            prs_not_created = 0
            validation_failures = []

            work_to_pr_times = []

            # Validate each work item
            for item in work_items:
                metadata = json.loads(item["metadata"]) if item["metadata"] else {}
                issue_number = metadata.get("issue_number")

                if not issue_number:
                    # Work item without issue assignment (legacy mode)
                    continue

                # Validate PR creation
                result = self.validate_pr_links_to_issue(
                    issue_number=issue_number,
                    work_item_number=metadata.get("work_item_number", 0),
                    agent_type=metadata.get("agent_type", "unknown"),
                    role=metadata.get("role", "primary")
                )

                if result.pr_number:
                    prs_created += 1

                    if result.valid:
                        prs_with_valid_links += 1

                        # Calculate work-to-PR latency
                        if item["started_at"] and result.validation_timestamp:
                            started = datetime.fromisoformat(item["started_at"])
                            created = datetime.fromisoformat(result.validation_timestamp)
                            work_to_pr_times.append((created - started).total_seconds())
                    else:
                        prs_missing_keywords += 1
                        validation_failures.append({
                            "task_id": item["task_id"],
                            "issue_number": issue_number,
                            "pr_number": result.pr_number,
                            "reason": result.reason
                        })
                else:
                    prs_not_created += 1
                    validation_failures.append({
                        "task_id": item["task_id"],
                        "issue_number": issue_number,
                        "reason": result.reason
                    })

            # Get checkpoint quality gate results
            cursor.execute("""
                SELECT
                    health_ok,
                    stability_ok,
                    security_ok,
                    quality_ok
                FROM cycle_checkpoints
                WHERE cycle_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (cycle_id,))

            checkpoint = cursor.fetchone()

            quality_gates_passed = 0
            quality_gates_failed = 0

            if checkpoint:
                gates = [
                    checkpoint["health_ok"],
                    checkpoint["stability_ok"],
                    checkpoint["security_ok"],
                    checkpoint["quality_ok"]
                ]
                quality_gates_passed = sum(1 for g in gates if g)
                quality_gates_failed = sum(1 for g in gates if not g)

            # Build report
            return TraceabilityReport(
                cycle_id=cycle_id,
                validation_timestamp=datetime.now(timezone.utc).isoformat(),
                total_work_items=total_work_items,
                prs_created=prs_created,
                prs_with_valid_links=prs_with_valid_links,
                prs_missing_keywords=prs_missing_keywords,
                prs_not_created=prs_not_created,
                issues_closed=0,  # Would need GitHub API to verify
                quality_gates_passed=quality_gates_passed,
                quality_gates_failed=quality_gates_failed,
                avg_work_to_pr_seconds=sum(work_to_pr_times) / len(work_to_pr_times) if work_to_pr_times else None,
                validation_failures=validation_failures
            )

        finally:
            conn.close()

    def auto_fix_pr_body(
        self,
        pr_number: int,
        issue_number: int
    ) -> bool:
        """
        Attempt to auto-fix PR body by adding closing keyword.

        Args:
            pr_number: PR number to fix
            issue_number: Issue number to reference

        Returns:
            True if fix succeeded
        """
        try:
            # Get current PR body
            result = subprocess.run(
                [
                    "gh", "pr", "view", str(pr_number),
                    "--json", "body",
                    "--jq", ".body"
                ],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False
            )

            if result.returncode != 0:
                return False

            current_body = result.stdout.strip()

            # Append closing keyword
            fixed_body = f"{current_body}\n\nCloses #{issue_number}"

            # Update PR
            fix_result = subprocess.run(
                ["gh", "pr", "edit", str(pr_number), "--body", fixed_body],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False
            )

            return fix_result.returncode == 0

        except Exception:
            return False

    def generate_compliance_report(
        self,
        report: TraceabilityReport,
        output_format: str = "json"
    ) -> str:
        """
        Generate formatted compliance report.

        Args:
            report: TraceabilityReport to format
            output_format: "json" or "markdown"

        Returns:
            Formatted report string
        """
        if output_format == "json":
            return json.dumps(asdict(report), indent=2)

        elif output_format == "markdown":
            md = f"""# Traceability Compliance Report

**Cycle ID:** {report.cycle_id}
**Validation Date:** {report.validation_timestamp}
**Compliance Rate:** {report.compliance_rate:.1f}%

## Summary

| Metric | Count |
|--------|-------|
| Total Work Items | {report.total_work_items} |
| PRs Created | {report.prs_created} |
| PRs with Valid Links | {report.prs_with_valid_links} |
| PRs Missing Keywords | {report.prs_missing_keywords} |
| PRs Not Created | {report.prs_not_created} |
| Issues Closed | {report.issues_closed} |

## Quality Gates

| Metric | Count |
|--------|-------|
| Gates Passed | {report.quality_gates_passed} |
| Gates Failed | {report.quality_gates_failed} |

## Performance Metrics

- **Avg Work-to-PR Time:** {f'{report.avg_work_to_pr_seconds:.1f}s' if report.avg_work_to_pr_seconds else 'N/A'}
- **Avg PR-to-Merge Time:** {f'{report.avg_pr_to_merge_seconds:.1f}s' if report.avg_pr_to_merge_seconds else 'N/A'}

## Validation Failures

"""
            if report.validation_failures:
                for failure in report.validation_failures:
                    md += f"- **Task:** {failure.get('task_id', 'unknown')}\n"
                    md += f"  - Issue: #{failure.get('issue_number', 'N/A')}\n"
                    md += f"  - PR: #{failure.get('pr_number', 'N/A')}\n"
                    md += f"  - Reason: {failure.get('reason', 'Unknown')}\n\n"
            else:
                md += "*No validation failures*\n"

            return md

        else:
            raise ValueError(f"Unsupported format: {output_format}")


def validate_pr_links_to_issue(
    workspace_root: Path,
    issue_number: int,
    work_item_number: int,
    agent_type: str,
    role: str = "primary",
    timeout_seconds: float = 10.0
) -> dict[str, Any]:
    """
    Standalone function to validate PR-to-issue linking.

    This is the main entry point for cycle.py integration.

    Args:
        workspace_root: Root directory of workspace repository
        issue_number: GitHub issue number assigned to work
        work_item_number: Work item sequence number
        agent_type: Agent that performed work
        role: Agent role (primary/cross-check/observer)
        timeout_seconds: Timeout for API calls

    Returns:
        Dictionary with validation result (compatible with cycle.py)
    """
    validator = TraceabilityValidator(
        workspace_root=workspace_root,
        timeout_seconds=timeout_seconds
    )

    result = validator.validate_pr_links_to_issue(
        issue_number=issue_number,
        work_item_number=work_item_number,
        agent_type=agent_type,
        role=role
    )

    return result.to_dict()


if __name__ == "__main__":
    import sys

    # CLI for manual validation
    if len(sys.argv) < 3:
        print("Usage: python traceability_validator.py <command> <args>")
        print("Commands:")
        print("  validate-pr <issue_number> <work_item_number> <agent_type>")
        print("  validate-cycle <memory_db_path> <cycle_id>")
        print("  auto-fix <pr_number> <issue_number>")
        sys.exit(1)

    command = sys.argv[1]
    workspace_root = Path.cwd()

    if command == "validate-pr":
        issue_num = int(sys.argv[2])
        work_item = int(sys.argv[3])
        agent = sys.argv[4]

        result = validate_pr_links_to_issue(
            workspace_root=workspace_root,
            issue_number=issue_num,
            work_item_number=work_item,
            agent_type=agent
        )

        print(json.dumps(result, indent=2))
        sys.exit(0 if result["valid"] else 1)

    elif command == "validate-cycle":
        db_path = Path(sys.argv[2])
        cycle_id = int(sys.argv[3])

        validator = TraceabilityValidator(workspace_root=workspace_root)
        report = validator.validate_cycle_traceability(db_path, cycle_id)

        print(validator.generate_compliance_report(report, "markdown"))
        sys.exit(0)

    elif command == "auto-fix":
        pr_num = int(sys.argv[2])
        issue_num = int(sys.argv[3])

        validator = TraceabilityValidator(workspace_root=workspace_root)
        success = validator.auto_fix_pr_body(pr_num, issue_num)

        if success:
            print(f"Successfully fixed PR #{pr_num} to close issue #{issue_num}")
            sys.exit(0)
        else:
            print(f"Failed to fix PR #{pr_num}")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

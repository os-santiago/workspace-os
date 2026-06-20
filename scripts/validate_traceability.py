#!/usr/bin/env python3
"""
Production-ready Traceability Validation Script for Workspace OS

This script provides comprehensive CLI commands for validating PR-to-issue traceability,
quality gates, and cycle compliance. It supports multiple validation modes (SOFT/HARD/BATCH)
and output formats (JSON/CSV/Markdown).

Usage:
    # Trace issue to PRs
    python validate_traceability.py trace issue --issue-number 123

    # Trace PR to linked issues
    python validate_traceability.py trace pr --pr-number 456

    # Trace work item
    python validate_traceability.py trace work-item --cycle-id 2 --work-item 5

    # Validate full cycle
    python validate_traceability.py validate cycle --cycle-id 2 --output json

    # Auto-fix missing closing keywords
    python validate_traceability.py fix pr --pr-number 456 --issue-number 123

    # Batch validation with CSV output
    python validate_traceability.py validate cycle --cycle-id 2 --mode batch --output csv

Author: Workspace OS Team
License: MIT
"""

import argparse
import csv
import json
import logging
import re
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# Enumerations
# ============================================================================

class ValidationMode(Enum):
    """Enforcement mode for validation failures."""
    SOFT = "soft"    # Log warnings, don't block
    HARD = "hard"    # Block completion on failures
    BATCH = "batch"  # Defer validation to checkpoint


class PRState(Enum):
    """PR state enumeration matching GitHub states."""
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"
    DRAFT = "draft"
    NOT_CREATED = "not_created"


class OutputFormat(Enum):
    """Output format for reports."""
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    TEXT = "text"


# ============================================================================
# Data Classes
# ============================================================================

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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class IssueTraceResult:
    """Result of tracing an issue to its PRs."""
    issue_number: int
    issue_title: str
    issue_state: str
    linked_prs: list[dict[str, Any]] = field(default_factory=list)
    total_prs: int = 0
    prs_with_keywords: int = 0
    is_closed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class PRTraceResult:
    """Result of tracing a PR to its linked issues."""
    pr_number: int
    pr_title: str
    pr_state: str
    pr_url: str
    linked_issues: list[dict[str, Any]] = field(default_factory=list)
    total_issues: int = 0
    issues_with_keywords: int = 0
    is_merged: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# ============================================================================
# Main Validator Class
# ============================================================================

class TraceabilityValidator:
    """
    Production-ready validator class for traceability compliance.

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

    # Default timeout for subprocess calls
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

        Raises:
            ValueError: If workspace_root doesn't exist
        """
        if not workspace_root.exists():
            raise ValueError(f"Workspace root does not exist: {workspace_root}")

        self.workspace_root = workspace_root
        self.validation_mode = validation_mode
        self.timeout_seconds = timeout_seconds
        logger.info(f"Initialized validator for {workspace_root} in {validation_mode.value} mode")

    def trace_issue(self, issue_number: int) -> IssueTraceResult:
        """
        Trace an issue to all linked PRs.

        Args:
            issue_number: GitHub issue number

        Returns:
            IssueTraceResult with linked PR information

        Raises:
            RuntimeError: If GitHub API call fails
        """
        logger.info(f"Tracing issue #{issue_number}")

        try:
            # Get issue details
            issue_result = subprocess.run(
                [
                    "gh", "issue", "view", str(issue_number),
                    "--json", "number,title,state,closed"
                ],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=True
            )

            issue_data = json.loads(issue_result.stdout)

            # Find all PRs that reference this issue
            prs = self._query_recent_prs_for_issue(issue_number)

            linked_prs = []
            prs_with_keywords = 0

            for pr in prs:
                # Check for closing keywords
                has_keyword, keyword = self._validate_closing_keywords(
                    pr.get("body", ""),
                    issue_number
                )

                if has_keyword:
                    prs_with_keywords += 1

                linked_prs.append({
                    "number": pr["number"],
                    "title": pr.get("title", ""),
                    "state": pr.get("state", ""),
                    "url": pr.get("url", ""),
                    "has_closing_keyword": has_keyword,
                    "keyword_used": keyword,
                    "created_at": pr.get("createdAt", "")
                })

            return IssueTraceResult(
                issue_number=issue_number,
                issue_title=issue_data.get("title", ""),
                issue_state=issue_data.get("state", ""),
                linked_prs=linked_prs,
                total_prs=len(linked_prs),
                prs_with_keywords=prs_with_keywords,
                is_closed=issue_data.get("closed", False)
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to trace issue #{issue_number}: {e.stderr}")
            raise RuntimeError(f"GitHub API call failed: {e.stderr}")
        except Exception as e:
            logger.error(f"Error tracing issue #{issue_number}: {str(e)}")
            raise

    def trace_pr(self, pr_number: int) -> PRTraceResult:
        """
        Trace a PR to all linked issues.

        Args:
            pr_number: GitHub PR number

        Returns:
            PRTraceResult with linked issue information

        Raises:
            RuntimeError: If GitHub API call fails
        """
        logger.info(f"Tracing PR #{pr_number}")

        try:
            # Get PR details
            pr_result = subprocess.run(
                [
                    "gh", "pr", "view", str(pr_number),
                    "--json", "number,title,state,url,body,merged"
                ],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=True
            )

            pr_data = json.loads(pr_result.stdout)

            # Extract linked issues from PR body
            linked_issues = self._extract_linked_issues(pr_data.get("body", ""))

            issues_with_keywords = 0

            # Enrich with issue details
            enriched_issues = []
            for issue in linked_issues:
                try:
                    issue_result = subprocess.run(
                        [
                            "gh", "issue", "view", str(issue["number"]),
                            "--json", "number,title,state,closed"
                        ],
                        cwd=self.workspace_root,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout_seconds,
                        check=True
                    )

                    issue_data = json.loads(issue_result.stdout)

                    enriched_issues.append({
                        "number": issue["number"],
                        "title": issue_data.get("title", ""),
                        "state": issue_data.get("state", ""),
                        "keyword": issue["keyword"],
                        "is_closed": issue_data.get("closed", False)
                    })

                    issues_with_keywords += 1

                except subprocess.CalledProcessError:
                    logger.warning(f"Failed to fetch details for issue #{issue['number']}")
                    enriched_issues.append({
                        "number": issue["number"],
                        "title": "Unknown",
                        "state": "unknown",
                        "keyword": issue["keyword"],
                        "is_closed": False
                    })

            return PRTraceResult(
                pr_number=pr_number,
                pr_title=pr_data.get("title", ""),
                pr_state=pr_data.get("state", ""),
                pr_url=pr_data.get("url", ""),
                linked_issues=enriched_issues,
                total_issues=len(enriched_issues),
                issues_with_keywords=issues_with_keywords,
                is_merged=pr_data.get("merged", False)
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to trace PR #{pr_number}: {e.stderr}")
            raise RuntimeError(f"GitHub API call failed: {e.stderr}")
        except Exception as e:
            logger.error(f"Error tracing PR #{pr_number}: {str(e)}")
            raise

    def trace_work_item(
        self,
        memory_db_path: Path,
        cycle_id: int,
        work_item_number: int
    ) -> dict[str, Any]:
        """
        Trace a work item through issue → PR → merge.

        Args:
            memory_db_path: Path to memory.db SQLite database
            cycle_id: Cycle ID
            work_item_number: Work item number

        Returns:
            Dictionary with work item trace information

        Raises:
            ValueError: If work item not found
            RuntimeError: If database access fails
        """
        logger.info(f"Tracing work item cycle-{cycle_id}-{work_item_number}")

        try:
            conn = sqlite3.connect(memory_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Find work item
            task_id_pattern = f"%cycle-{cycle_id}-{work_item_number}%"

            cursor.execute("""
                SELECT
                    task_id,
                    metadata,
                    status,
                    started_at,
                    completed_at
                FROM agent_queue
                WHERE task_id LIKE ?
                LIMIT 1
            """, (task_id_pattern,))

            work_item = cursor.fetchone()

            if not work_item:
                raise ValueError(
                    f"Work item not found: cycle-{cycle_id}-{work_item_number}"
                )

            metadata = json.loads(work_item["metadata"]) if work_item["metadata"] else {}
            issue_number = metadata.get("issue_number")

            if not issue_number:
                return {
                    "task_id": work_item["task_id"],
                    "status": work_item["status"],
                    "issue_number": None,
                    "pr_info": None,
                    "trace_status": "no_issue_assigned"
                }

            # Validate PR creation
            result = self.validate_pr_links_to_issue(
                issue_number=issue_number,
                work_item_number=work_item_number,
                agent_type=metadata.get("agent_type", "unknown"),
                role=metadata.get("role", "primary")
            )

            # Trace issue to get full context
            issue_trace = self.trace_issue(issue_number)

            return {
                "task_id": work_item["task_id"],
                "status": work_item["status"],
                "started_at": work_item["started_at"],
                "completed_at": work_item["completed_at"],
                "issue_number": issue_number,
                "issue_trace": issue_trace.to_dict(),
                "pr_validation": result.to_dict(),
                "trace_status": "complete" if result.valid else "incomplete"
            }

        except sqlite3.Error as e:
            logger.error(f"Database error: {str(e)}")
            raise RuntimeError(f"Failed to access database: {str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()

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
        logger.debug(
            f"Validating PR link: issue #{issue_number}, "
            f"work_item {work_item_number}, agent {agent_type}, role {role}"
        )

        # Skip validation for non-primary roles
        if role in ("cross-check", "observer"):
            logger.info(f"Skipping validation for {role} role")
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
                logger.warning(f"No PRs found linking to issue #{issue_number}")
                return PRValidationResult(
                    valid=False,
                    reason=f"No recent PR found linking to issue #{issue_number}",
                    pr_number=None,
                    pr_url=None
                )

            # Filter to most recent PR (within last 10 minutes)
            recent_pr = self._filter_recent_pr(prs)

            if not recent_pr:
                logger.warning(
                    f"No PR created in last 10 minutes for issue #{issue_number}"
                )
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

            if keywords_valid:
                logger.info(
                    f"✓ PR #{recent_pr['number']} correctly links to issue "
                    f"#{issue_number} with '{keyword_used}'"
                )
            else:
                logger.warning(
                    f"✗ PR #{recent_pr['number']} references issue "
                    f"#{issue_number} but missing closing keyword"
                )

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
            logger.error(f"PR verification timed out after {self.timeout_seconds}s")
            return PRValidationResult(
                valid=False,
                reason=f"PR verification timed out after {self.timeout_seconds}s",
                pr_number=None,
                pr_url=None
            )
        except Exception as e:
            logger.error(f"PR verification error: {str(e)}")
            return PRValidationResult(
                valid=False,
                reason=f"PR verification error: {str(e)[:200]}",
                pr_number=None,
                pr_url=None
            )

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
        logger.info("Validating quality gates")

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

        passed = sum(1 for r in results if r.passed)
        total = len(results)
        logger.info(f"Quality gates: {passed}/{total} passed")

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

        Raises:
            RuntimeError: If database access fails
        """
        logger.info(f"Validating cycle {cycle_id} traceability")

        try:
            conn = sqlite3.connect(memory_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if agent_queue table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='agent_queue'
            """)

            if not cursor.fetchone():
                logger.warning("agent_queue table not found, returning empty report")
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

            logger.info(f"Found {total_work_items} work items for cycle {cycle_id}")

            # Validate each work item
            for item in work_items:
                metadata = json.loads(item["metadata"]) if item["metadata"] else {}
                issue_number = metadata.get("issue_number")

                if not issue_number:
                    # Work item without issue assignment (legacy mode)
                    logger.debug(f"Skipping {item['task_id']} - no issue assigned")
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
            report = TraceabilityReport(
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

            logger.info(
                f"Cycle {cycle_id} compliance: {report.compliance_rate:.1f}% "
                f"({prs_with_valid_links}/{total_work_items} valid)"
            )

            return report

        except sqlite3.Error as e:
            logger.error(f"Database error: {str(e)}")
            raise RuntimeError(f"Failed to access database: {str(e)}")
        finally:
            if 'conn' in locals():
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
        logger.info(f"Auto-fixing PR #{pr_number} to close issue #{issue_number}")

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
                logger.error(f"Failed to fetch PR body: {result.stderr}")
                return False

            current_body = result.stdout.strip()

            # Check if already has closing keyword
            has_keyword, _ = self._validate_closing_keywords(current_body, issue_number)
            if has_keyword:
                logger.info(f"PR #{pr_number} already has closing keyword")
                return True

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

            if fix_result.returncode == 0:
                logger.info(f"✓ Successfully fixed PR #{pr_number}")
                return True
            else:
                logger.error(f"Failed to update PR: {fix_result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error auto-fixing PR: {str(e)}")
            return False

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _query_recent_prs_for_issue(self, issue_number: int) -> list[dict[str, Any]]:
        """
        Query GitHub for recent PRs referencing the issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            List of PR objects from gh CLI

        Raises:
            RuntimeError: If gh CLI call fails
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
        """
        Get repository owner and name from git remote.

        Returns:
            Dictionary with 'owner' and 'name' keys, or None if not found
        """
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


# ============================================================================
# Output Formatters
# ============================================================================

class OutputFormatter:
    """Format validation results for various output formats."""

    @staticmethod
    def format_report(
        report: TraceabilityReport,
        output_format: OutputFormat
    ) -> str:
        """
        Generate formatted compliance report.

        Args:
            report: TraceabilityReport to format
            output_format: Output format

        Returns:
            Formatted report string
        """
        if output_format == OutputFormat.JSON:
            return json.dumps(report.to_dict(), indent=2)

        elif output_format == OutputFormat.CSV:
            return OutputFormatter._format_csv(report)

        elif output_format == OutputFormat.MARKDOWN:
            return OutputFormatter._format_markdown(report)

        elif output_format == OutputFormat.TEXT:
            return OutputFormatter._format_text(report)

        else:
            raise ValueError(f"Unsupported format: {output_format}")

    @staticmethod
    def _format_csv(report: TraceabilityReport) -> str:
        """Format report as CSV."""
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Summary section
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Cycle ID", report.cycle_id])
        writer.writerow(["Validation Timestamp", report.validation_timestamp])
        writer.writerow(["Compliance Rate (%)", f"{report.compliance_rate:.1f}"])
        writer.writerow(["Total Work Items", report.total_work_items])
        writer.writerow(["PRs Created", report.prs_created])
        writer.writerow(["PRs with Valid Links", report.prs_with_valid_links])
        writer.writerow(["PRs Missing Keywords", report.prs_missing_keywords])
        writer.writerow(["PRs Not Created", report.prs_not_created])
        writer.writerow(["Issues Closed", report.issues_closed])
        writer.writerow(["Quality Gates Passed", report.quality_gates_passed])
        writer.writerow(["Quality Gates Failed", report.quality_gates_failed])

        if report.avg_work_to_pr_seconds:
            writer.writerow(["Avg Work-to-PR (seconds)", f"{report.avg_work_to_pr_seconds:.1f}"])

        # Failures section
        if report.validation_failures:
            writer.writerow([])
            writer.writerow(["Validation Failures"])
            writer.writerow(["Task ID", "Issue Number", "PR Number", "Reason"])
            for failure in report.validation_failures:
                writer.writerow([
                    failure.get("task_id", ""),
                    failure.get("issue_number", ""),
                    failure.get("pr_number", ""),
                    failure.get("reason", "")
                ])

        return output.getvalue()

    @staticmethod
    def _format_markdown(report: TraceabilityReport) -> str:
        """Format report as Markdown."""
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

    @staticmethod
    def _format_text(report: TraceabilityReport) -> str:
        """Format report as plain text."""
        text = f"""Traceability Compliance Report
{'=' * 60}

Cycle ID: {report.cycle_id}
Validation Date: {report.validation_timestamp}
Compliance Rate: {report.compliance_rate:.1f}%

Summary
{'-' * 60}
Total Work Items:        {report.total_work_items}
PRs Created:             {report.prs_created}
PRs with Valid Links:    {report.prs_with_valid_links}
PRs Missing Keywords:    {report.prs_missing_keywords}
PRs Not Created:         {report.prs_not_created}
Issues Closed:           {report.issues_closed}

Quality Gates
{'-' * 60}
Gates Passed:            {report.quality_gates_passed}
Gates Failed:            {report.quality_gates_failed}

Performance Metrics
{'-' * 60}
Avg Work-to-PR Time:     {f'{report.avg_work_to_pr_seconds:.1f}s' if report.avg_work_to_pr_seconds else 'N/A'}
Avg PR-to-Merge Time:    {f'{report.avg_pr_to_merge_seconds:.1f}s' if report.avg_pr_to_merge_seconds else 'N/A'}

"""
        if report.validation_failures:
            text += f"\nValidation Failures\n{'-' * 60}\n"
            for failure in report.validation_failures:
                text += f"\nTask: {failure.get('task_id', 'unknown')}\n"
                text += f"  Issue: #{failure.get('issue_number', 'N/A')}\n"
                text += f"  PR: #{failure.get('pr_number', 'N/A')}\n"
                text += f"  Reason: {failure.get('reason', 'Unknown')}\n"
        else:
            text += f"\nValidation Failures\n{'-' * 60}\nNone\n"

        return text

    @staticmethod
    def format_issue_trace(
        result: IssueTraceResult,
        output_format: OutputFormat
    ) -> str:
        """Format issue trace result."""
        if output_format == OutputFormat.JSON:
            return json.dumps(result.to_dict(), indent=2)

        elif output_format == OutputFormat.MARKDOWN:
            md = f"""# Issue Trace: #{result.issue_number}

**Title:** {result.issue_title}
**State:** {result.issue_state}
**Is Closed:** {result.is_closed}

## Linked PRs ({result.total_prs})

PRs with closing keywords: {result.prs_with_keywords}/{result.total_prs}

"""
            if result.linked_prs:
                md += "| PR # | Title | State | Has Keyword | Keyword |\n"
                md += "|------|-------|-------|-------------|----------|\n"
                for pr in result.linked_prs:
                    keyword = pr.get('keyword_used', 'N/A') if pr.get('has_closing_keyword') else '-'
                    md += f"| #{pr['number']} | {pr['title'][:50]} | {pr['state']} | {'✓' if pr['has_closing_keyword'] else '✗'} | {keyword} |\n"
            else:
                md += "*No linked PRs found*\n"

            return md

        else:
            # TEXT format
            text = f"""Issue Trace: #{result.issue_number}
{'=' * 60}

Title: {result.issue_title}
State: {result.issue_state}
Is Closed: {result.is_closed}

Linked PRs: {result.total_prs}
PRs with closing keywords: {result.prs_with_keywords}/{result.total_prs}

"""
            if result.linked_prs:
                for pr in result.linked_prs:
                    text += f"\nPR #{pr['number']}: {pr['title']}\n"
                    text += f"  State: {pr['state']}\n"
                    text += f"  Has Keyword: {'Yes' if pr['has_closing_keyword'] else 'No'}\n"
                    if pr.get('keyword_used'):
                        text += f"  Keyword: {pr['keyword_used']}\n"
            else:
                text += "No linked PRs found\n"

            return text

    @staticmethod
    def format_pr_trace(
        result: PRTraceResult,
        output_format: OutputFormat
    ) -> str:
        """Format PR trace result."""
        if output_format == OutputFormat.JSON:
            return json.dumps(result.to_dict(), indent=2)

        elif output_format == OutputFormat.MARKDOWN:
            md = f"""# PR Trace: #{result.pr_number}

**Title:** {result.pr_title}
**State:** {result.pr_state}
**Is Merged:** {result.is_merged}
**URL:** {result.pr_url}

## Linked Issues ({result.total_issues})

Issues with closing keywords: {result.issues_with_keywords}/{result.total_issues}

"""
            if result.linked_issues:
                md += "| Issue # | Title | State | Keyword | Is Closed |\n"
                md += "|---------|-------|-------|---------|----------|\n"
                for issue in result.linked_issues:
                    md += f"| #{issue['number']} | {issue['title'][:50]} | {issue['state']} | {issue['keyword']} | {'✓' if issue['is_closed'] else '✗'} |\n"
            else:
                md += "*No linked issues found*\n"

            return md

        else:
            # TEXT format
            text = f"""PR Trace: #{result.pr_number}
{'=' * 60}

Title: {result.pr_title}
State: {result.pr_state}
Is Merged: {result.is_merged}
URL: {result.pr_url}

Linked Issues: {result.total_issues}
Issues with closing keywords: {result.issues_with_keywords}/{result.total_issues}

"""
            if result.linked_issues:
                for issue in result.linked_issues:
                    text += f"\nIssue #{issue['number']}: {issue['title']}\n"
                    text += f"  State: {issue['state']}\n"
                    text += f"  Keyword: {issue['keyword']}\n"
                    text += f"  Is Closed: {'Yes' if issue['is_closed'] else 'No'}\n"
            else:
                text += "No linked issues found\n"

            return text


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_trace_issue(args: argparse.Namespace) -> int:
    """Handle 'trace issue' command."""
    try:
        validator = TraceabilityValidator(
            workspace_root=args.workspace_root,
            timeout_seconds=args.timeout
        )

        result = validator.trace_issue(args.issue_number)

        output_format = OutputFormat(args.output)
        formatted = OutputFormatter.format_issue_trace(result, output_format)

        print(formatted)

        return 0

    except Exception as e:
        logger.error(f"Failed to trace issue: {str(e)}")
        return 1


def cmd_trace_pr(args: argparse.Namespace) -> int:
    """Handle 'trace pr' command."""
    try:
        validator = TraceabilityValidator(
            workspace_root=args.workspace_root,
            timeout_seconds=args.timeout
        )

        result = validator.trace_pr(args.pr_number)

        output_format = OutputFormat(args.output)
        formatted = OutputFormatter.format_pr_trace(result, output_format)

        print(formatted)

        return 0

    except Exception as e:
        logger.error(f"Failed to trace PR: {str(e)}")
        return 1


def cmd_trace_work_item(args: argparse.Namespace) -> int:
    """Handle 'trace work-item' command."""
    try:
        validator = TraceabilityValidator(
            workspace_root=args.workspace_root,
            timeout_seconds=args.timeout
        )

        result = validator.trace_work_item(
            memory_db_path=args.memory_db,
            cycle_id=args.cycle_id,
            work_item_number=args.work_item
        )

        output_format = OutputFormat(args.output)

        if output_format == OutputFormat.JSON:
            print(json.dumps(result, indent=2))
        else:
            # Simplified text output for work item trace
            print(f"Work Item Trace: {result['task_id']}")
            print(f"Status: {result['status']}")
            print(f"Trace Status: {result['trace_status']}")

            if result.get('issue_number'):
                print(f"\nIssue: #{result['issue_number']}")

                if result.get('pr_validation'):
                    pr_val = result['pr_validation']
                    print(f"PR: #{pr_val.get('pr_number', 'N/A')}")
                    print(f"Valid: {pr_val.get('valid', False)}")
                    print(f"Reason: {pr_val.get('reason', 'N/A')}")

        return 0

    except Exception as e:
        logger.error(f"Failed to trace work item: {str(e)}")
        return 1


def cmd_validate_cycle(args: argparse.Namespace) -> int:
    """Handle 'validate cycle' command."""
    try:
        validator = TraceabilityValidator(
            workspace_root=args.workspace_root,
            validation_mode=ValidationMode(args.mode),
            timeout_seconds=args.timeout
        )

        report = validator.validate_cycle_traceability(
            memory_db_path=args.memory_db,
            cycle_id=args.cycle_id
        )

        output_format = OutputFormat(args.output)
        formatted = OutputFormatter.format_report(report, output_format)

        print(formatted)

        # Exit with non-zero if validation failed in HARD mode
        if args.mode == "hard" and report.compliance_rate < 100.0:
            logger.warning(f"Validation failed: {report.compliance_rate:.1f}% compliance")
            return 1

        return 0

    except Exception as e:
        logger.error(f"Failed to validate cycle: {str(e)}")
        return 1


def cmd_fix_pr(args: argparse.Namespace) -> int:
    """Handle 'fix pr' command."""
    try:
        validator = TraceabilityValidator(
            workspace_root=args.workspace_root,
            timeout_seconds=args.timeout
        )

        success = validator.auto_fix_pr_body(
            pr_number=args.pr_number,
            issue_number=args.issue_number
        )

        if success:
            print(f"✓ Successfully fixed PR #{args.pr_number} to close issue #{args.issue_number}")
            return 0
        else:
            print(f"✗ Failed to fix PR #{args.pr_number}")
            return 1

    except Exception as e:
        logger.error(f"Failed to fix PR: {str(e)}")
        return 1


# ============================================================================
# Main CLI Entry Point
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all commands."""
    parser = argparse.ArgumentParser(
        description="Traceability Validation Tool for Workspace OS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Trace issue to PRs
  %(prog)s trace issue --issue-number 123

  # Trace PR to linked issues
  %(prog)s trace pr --pr-number 456

  # Validate full cycle
  %(prog)s validate cycle --cycle-id 2 --output json

  # Auto-fix missing closing keywords
  %(prog)s fix pr --pr-number 456 --issue-number 123
        """
    )

    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path.cwd(),
        help="Root directory of workspace repository (default: current directory)"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout for subprocess calls in seconds (default: 10.0)"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # ========================================================================
    # Trace commands
    # ========================================================================
    trace_parser = subparsers.add_parser("trace", help="Trace traceability links")
    trace_subparsers = trace_parser.add_subparsers(dest="trace_type", help="Type of trace")

    # trace issue
    trace_issue_parser = trace_subparsers.add_parser("issue", help="Trace issue to PRs")
    trace_issue_parser.add_argument(
        "--issue-number",
        type=int,
        required=True,
        help="GitHub issue number"
    )
    trace_issue_parser.add_argument(
        "--output",
        choices=["json", "markdown", "text"],
        default="text",
        help="Output format (default: text)"
    )

    # trace pr
    trace_pr_parser = trace_subparsers.add_parser("pr", help="Trace PR to linked issues")
    trace_pr_parser.add_argument(
        "--pr-number",
        type=int,
        required=True,
        help="GitHub PR number"
    )
    trace_pr_parser.add_argument(
        "--output",
        choices=["json", "markdown", "text"],
        default="text",
        help="Output format (default: text)"
    )

    # trace work-item
    trace_work_item_parser = trace_subparsers.add_parser("work-item", help="Trace work item through cycle")
    trace_work_item_parser.add_argument(
        "--cycle-id",
        type=int,
        required=True,
        help="Cycle ID"
    )
    trace_work_item_parser.add_argument(
        "--work-item",
        type=int,
        required=True,
        help="Work item number"
    )
    trace_work_item_parser.add_argument(
        "--memory-db",
        type=Path,
        default=Path.cwd() / ".claude" / "memory.db",
        help="Path to memory.db (default: .claude/memory.db)"
    )
    trace_work_item_parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)"
    )

    # ========================================================================
    # Validate commands
    # ========================================================================
    validate_parser = subparsers.add_parser("validate", help="Validate traceability compliance")
    validate_subparsers = validate_parser.add_subparsers(dest="validate_type", help="Type of validation")

    # validate cycle
    validate_cycle_parser = validate_subparsers.add_parser("cycle", help="Validate full cycle traceability")
    validate_cycle_parser.add_argument(
        "--cycle-id",
        type=int,
        required=True,
        help="Cycle ID to validate"
    )
    validate_cycle_parser.add_argument(
        "--memory-db",
        type=Path,
        default=Path.cwd() / ".claude" / "memory.db",
        help="Path to memory.db (default: .claude/memory.db)"
    )
    validate_cycle_parser.add_argument(
        "--mode",
        choices=["soft", "hard", "batch"],
        default="soft",
        help="Validation mode (default: soft)"
    )
    validate_cycle_parser.add_argument(
        "--output",
        choices=["json", "csv", "markdown", "text"],
        default="markdown",
        help="Output format (default: markdown)"
    )

    # ========================================================================
    # Fix commands
    # ========================================================================
    fix_parser = subparsers.add_parser("fix", help="Auto-fix traceability issues")
    fix_subparsers = fix_parser.add_subparsers(dest="fix_type", help="Type of fix")

    # fix pr
    fix_pr_parser = fix_subparsers.add_parser("pr", help="Auto-fix PR closing keywords")
    fix_pr_parser.add_argument(
        "--pr-number",
        type=int,
        required=True,
        help="PR number to fix"
    )
    fix_pr_parser.add_argument(
        "--issue-number",
        type=int,
        required=True,
        help="Issue number to link"
    )

    return parser


def main() -> int:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Dispatch to command handlers
    if args.command == "trace":
        if args.trace_type == "issue":
            return cmd_trace_issue(args)
        elif args.trace_type == "pr":
            return cmd_trace_pr(args)
        elif args.trace_type == "work-item":
            return cmd_trace_work_item(args)
        else:
            parser.print_help()
            return 1

    elif args.command == "validate":
        if args.validate_type == "cycle":
            return cmd_validate_cycle(args)
        else:
            parser.print_help()
            return 1

    elif args.command == "fix":
        if args.fix_type == "pr":
            return cmd_fix_pr(args)
        else:
            parser.print_help()
            return 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

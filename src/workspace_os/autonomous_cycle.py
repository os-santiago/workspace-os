from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
import json
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from workspace_os.conscience import ALLOW, ALLOW_WITH_LIMITS, ASK_CLARIFICATION, ESCALATE_TO_HUMAN, REFUSE, evaluate_request, render_decision_for_prompt
from workspace_os.delegation import build_hardened_delegate_prompt
from workspace_os.issue_complexity import ComplexityClassification, ComplexityLevel, classify_issue
from workspace_os.memory import WorkspaceMemoryStore


class AutonomousCycleStage(str, Enum):
    ISSUE_SELECTION = "issue_selection"
    OCE_GATE = "oce_gate"
    BRANCH_CREATION = "branch_creation"
    IMPLEMENTATION = "implementation"
    VALIDATION = "validation"
    PR_CREATION = "pr_creation"
    REVIEW = "review"
    MERGE = "merge"
    RECORDING = "recording"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class AutonomousCycleDisposition(str, Enum):
    SAFE_AUTONOMOUS = "safe_autonomous"
    VALIDATION_ONLY = "validation_only"
    HUMAN_REVIEW = "human_review"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AutonomousCyclePolicy:
    disposition: AutonomousCycleDisposition
    reason: str
    risk_level: str
    requires_validation: bool
    requires_human_review: bool
    can_merge: bool
    confidence: float = 0.0
    validation_hint: str | None = None
    gate_factors: tuple[str, ...] = ()

    def render(self) -> str:
        lines = [
            "Autonomous cycle policy",
            f"disposition={self.disposition.value}",
            f"risk_level={self.risk_level}",
            f"requires_validation={self.requires_validation}",
            f"requires_human_review={self.requires_human_review}",
            f"can_merge={self.can_merge}",
            f"confidence={self.confidence:.2f}",
            f"reason={self.reason}",
        ]
        if self.validation_hint:
            lines.append(f"validation_hint={self.validation_hint}")
        if self.gate_factors:
            lines.append("gate_factors:")
            lines.extend(f"- {factor}" for factor in self.gate_factors)
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class AutonomousCycleRecord:
    id: int
    issue_number: int
    issue_title: str
    issue_url: str | None
    branch_name: str
    stage: str
    status: str
    policy_disposition: str
    policy_reason: str
    risk_level: str
    validation_commands: tuple[str, ...] = ()
    validation_results: tuple[dict[str, Any], ...] = ()
    pr_number: int | None = None
    pr_url: str | None = None
    merge_status: str | None = None
    blockers: tuple[str, ...] = ()
    learning_signals: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None

    def compact_summary(self) -> str:
        lines = [
            f"cycle_id={self.id}",
            f"issue=#{self.issue_number}: {self.issue_title}",
            f"stage={self.stage}",
            f"status={self.status}",
            f"branch={self.branch_name}",
            f"policy={self.policy_disposition}",
            f"risk_level={self.risk_level}",
            f"pr_number={self.pr_number or 'n/a'}",
            f"merge_status={self.merge_status or 'n/a'}",
        ]
        if self.blockers:
            lines.append(f"blockers={'; '.join(self.blockers)}")
        if self.learning_signals:
            lines.append(f"learning_signals={'; '.join(self.learning_signals)}")
        return "\n".join(lines)

    def render(self) -> str:
        lines = [
            "Autonomous cycle record",
            f"id={self.id}",
            f"issue=#{self.issue_number}: {self.issue_title}",
            f"branch={self.branch_name}",
            f"stage={self.stage}",
            f"status={self.status}",
            f"policy={self.policy_disposition}",
            f"risk_level={self.risk_level}",
            f"pr_number={self.pr_number or 'n/a'}",
            f"merge_status={self.merge_status or 'n/a'}",
            f"created_at={self.created_at}",
            f"updated_at={self.updated_at}",
            f"completed_at={self.completed_at or 'n/a'}",
        ]
        if self.policy_reason:
            lines.append(f"policy_reason={self.policy_reason}")
        if self.validation_commands:
            lines.append("validation_commands:")
            lines.extend(f"- {command}" for command in self.validation_commands)
        if self.validation_results:
            lines.append("validation_results:")
            for result in self.validation_results:
                lines.append(
                    "- "
                    f"{result.get('command', 'n/a')} "
                    f"returncode={result.get('returncode', 'n/a')} "
                    f"passed={result.get('passed', False)}"
                )
        if self.blockers:
            lines.append("blockers:")
            lines.extend(f"- {blocker}" for blocker in self.blockers)
        if self.learning_signals:
            lines.append("learning_signals:")
            lines.extend(f"- {signal}" for signal in self.learning_signals)
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class AutonomousCyclePlan:
    issue_number: int
    issue_title: str
    branch_name: str
    policy: AutonomousCyclePolicy
    prompt: str
    validation_commands: tuple[str, ...]
    should_merge: bool
    notes: tuple[str, ...] = ()


class AutonomousCycleStore:
    def __init__(self, path: Path):
        self.path = path

    def ensure_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS autonomous_cycle_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_number INTEGER NOT NULL,
                    issue_title TEXT NOT NULL,
                    issue_url TEXT,
                    branch_name TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    policy_disposition TEXT NOT NULL,
                    policy_reason TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    validation_commands_json TEXT NOT NULL,
                    validation_results_json TEXT NOT NULL,
                    pr_number INTEGER,
                    pr_url TEXT,
                    merge_status TEXT,
                    blockers_json TEXT NOT NULL,
                    learning_signals_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS autonomous_cycle_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (cycle_id) REFERENCES autonomous_cycle_runs(id)
                );
                """
            )
            conn.commit()

    def start_cycle(
        self,
        issue_number: int,
        issue_title: str,
        issue_url: str | None,
        branch_name: str,
        policy: AutonomousCyclePolicy,
        validation_commands: Sequence[str] = (),
        prompt: str = "",
    ) -> int:
        now = _utc_now()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO autonomous_cycle_runs (
                    issue_number, issue_title, issue_url, branch_name,
                    stage, status, policy_disposition, policy_reason, risk_level,
                    validation_commands_json, validation_results_json,
                    pr_number, pr_url, merge_status, blockers_json, learning_signals_json,
                    created_at, updated_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, NULL)
                """,
                (
                    issue_number,
                    issue_title.strip(),
                    issue_url,
                    branch_name.strip(),
                    AutonomousCycleStage.ISSUE_SELECTION.value,
                    "running",
                    policy.disposition.value,
                    policy.reason.strip(),
                    policy.risk_level.strip(),
                    json.dumps(list(validation_commands), ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            cycle_id = int(cursor.lastrowid)
            conn.commit()
        self.append_event(
            cycle_id,
            AutonomousCycleStage.ISSUE_SELECTION,
            "selected",
            f"Selected issue #{issue_number}: {issue_title}",
            payload={"issue_number": issue_number, "branch_name": branch_name, "policy": policy.render(), "prompt": prompt},
            created_at=now,
        )
        return cycle_id

    def update_cycle(
        self,
        cycle_id: int,
        stage: AutonomousCycleStage,
        status: str,
        detail: str,
        *,
        pr_number: int | None = None,
        pr_url: str | None = None,
        merge_status: str | None = None,
        blockers: Sequence[str] = (),
        learning_signals: Sequence[str] = (),
        validation_results: Sequence[dict[str, Any]] = (),
        validation_commands: Sequence[str] | None = None,
        completed: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> None:
        now = _utc_now()
        with self._connection() as conn:
            current = conn.execute(
                "SELECT validation_commands_json, validation_results_json, blockers_json, learning_signals_json FROM autonomous_cycle_runs WHERE id = ?",
                (cycle_id,),
            ).fetchone()
            if current is None:
                raise ValueError(f"Autonomous cycle {cycle_id} not found.")

            current_validation_commands = json.loads(current["validation_commands_json"] or "[]")
            current_validation_results = json.loads(current["validation_results_json"] or "[]")
            current_blockers = json.loads(current["blockers_json"] or "[]")
            current_learning_signals = json.loads(current["learning_signals_json"] or "[]")

            if validation_commands is not None:
                current_validation_commands = list(validation_commands)
            if validation_results:
                current_validation_results = list(validation_results)
            if blockers:
                current_blockers = _dedupe([*current_blockers, *blockers])
            if learning_signals:
                current_learning_signals = _dedupe([*current_learning_signals, *learning_signals])

            conn.execute(
                """
                UPDATE autonomous_cycle_runs
                SET stage = ?, status = ?, pr_number = COALESCE(?, pr_number), pr_url = COALESCE(?, pr_url),
                    merge_status = COALESCE(?, merge_status), validation_commands_json = ?,
                    validation_results_json = ?, blockers_json = ?, learning_signals_json = ?,
                    updated_at = ?, completed_at = CASE WHEN ? THEN ? ELSE completed_at END
                WHERE id = ?
                """,
                (
                    stage.value,
                    status,
                    pr_number,
                    pr_url,
                    merge_status,
                    json.dumps(current_validation_commands, ensure_ascii=False),
                    json.dumps(current_validation_results, ensure_ascii=False),
                    json.dumps(current_blockers, ensure_ascii=False),
                    json.dumps(current_learning_signals, ensure_ascii=False),
                    now,
                    1 if completed else 0,
                    now if completed else None,
                    cycle_id,
                ),
            )
            conn.commit()

        self.append_event(
            cycle_id,
            stage,
            status,
            detail,
            payload=payload or {
                "pr_number": pr_number,
                "pr_url": pr_url,
                "merge_status": merge_status,
                "blockers": list(blockers),
                "learning_signals": list(learning_signals),
                "validation_results": list(validation_results),
            },
            created_at=now,
        )

    def append_event(
        self,
        cycle_id: int,
        stage: AutonomousCycleStage,
        status: str,
        detail: str,
        *,
        payload: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO autonomous_cycle_events (cycle_id, stage, status, detail, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cycle_id,
                    stage.value,
                    status,
                    detail.strip(),
                    json.dumps(payload or {}, ensure_ascii=False),
                    created_at or _utc_now(),
                ),
            )
            conn.commit()

    def get_cycle(self, cycle_id: int) -> AutonomousCycleRecord | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM autonomous_cycle_runs
                WHERE id = ?
                """,
                (cycle_id,),
            ).fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def list_cycles(self, limit: int = 20) -> list[AutonomousCycleRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM autonomous_cycle_runs
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def latest_cycle_for_issue(self, issue_number: int) -> AutonomousCycleRecord | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM autonomous_cycle_runs
                WHERE issue_number = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (issue_number,),
            ).fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def latest_learning_signals(self, limit: int = 20) -> list[str]:
        signals: list[str] = []
        for record in self.list_cycles(limit=limit):
            for signal in record.learning_signals:
                if signal not in signals:
                    signals.append(signal)
        return signals

    @contextmanager
    def _connection(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class AutonomousCycleOrchestrator:
    def __init__(
        self,
        workspace_root: Path,
        memory_store: WorkspaceMemoryStore,
        store: AutonomousCycleStore | None = None,
        command_runner: Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]] | None = None,
        agent_executor: Callable[[str, dict[str, Any] | None], dict[str, Any]] | None = None,
    ) -> None:
        self.workspace_root = workspace_root
        self.memory_store = memory_store
        self.store = store or AutonomousCycleStore(memory_store.path.parent / "autonomous-cycles.sqlite3")
        self.command_runner = command_runner or _run_command
        self.agent_executor = agent_executor
        self.store.ensure_schema()
        self.memory_store.ensure_schema()

    def plan_cycle(
        self,
        issue_data: dict[str, Any],
        validation_commands: Sequence[str] | None = None,
    ) -> AutonomousCyclePlan:
        issue_number = int(issue_data.get("number", 0))
        issue_title = str(issue_data.get("title", f"issue-{issue_number}"))
        branch_name = _branch_name(issue_number, issue_title)
        complexity = classify_issue(issue_data)
        commands = tuple(validation_commands or self._default_validation_commands())
        policy = self.evaluate_policy(issue_data, complexity, validation_commands=commands)
        prior_cycle = self.store.latest_cycle_for_issue(issue_number)
        recent_signals = self.store.latest_learning_signals(limit=8)
        prompt = build_hardened_delegate_prompt(
            agent="claude",
            workspace_name=self.workspace_root.name,
            workspace_root=self.workspace_root,
            task=f"Implement issue #{issue_number}: {issue_title}",
            brief=self._build_brief(
                issue_data,
                complexity,
                policy,
                prior_cycle=prior_cycle,
                recent_signals=recent_signals,
            ),
            tone="focused, concise, and repository-safe",
            detail_level="high",
        )
        notes = [
            f"complexity={complexity.level.value}",
            f"score={complexity.score:.1f}",
            f"requires_human_review={policy.requires_human_review}",
        ]
        if prior_cycle is not None:
            notes.append(f"resumes_cycle_id={prior_cycle.id}")
        notes.extend(f"recent_signal={signal}" for signal in recent_signals[:3])
        return AutonomousCyclePlan(
            issue_number=issue_number,
            issue_title=issue_title,
            branch_name=branch_name,
            policy=policy,
            prompt=prompt,
            validation_commands=commands,
            should_merge=policy.can_merge,
            notes=tuple(notes),
        )

    def evaluate_policy(
        self,
        issue_data: dict[str, Any],
        complexity: ComplexityClassification | None = None,
        validation_commands: Sequence[str] | None = None,
    ) -> AutonomousCyclePolicy:
        issue_number = int(issue_data.get("number", 0))
        title = str(issue_data.get("title", f"issue-{issue_number}"))
        body = str(issue_data.get("body", ""))
        labels = [str(label.get("name", "")) for label in issue_data.get("labels", []) if isinstance(label, dict)]
        brief = " ".join([title, body, " ".join(labels)])
        decision = evaluate_request(title, brief=brief, destination="software")
        complexity = complexity or classify_issue(issue_data)
        validation_commands = tuple(validation_commands or self._default_validation_commands())
        gate = _assess_autonomy_gate(issue_data, complexity, validation_commands, self.workspace_root)

        if decision.decision == REFUSE:
            return AutonomousCyclePolicy(
                disposition=AutonomousCycleDisposition.BLOCKED,
                reason=f"{decision.rationale} {gate.reason}".strip(),
                risk_level=decision.risk_level,
                requires_validation=False,
                requires_human_review=True,
                can_merge=False,
                confidence=0.0,
                validation_hint="Blocked by OCE policy.",
                gate_factors=gate.factors,
            )

        if decision.decision in {ASK_CLARIFICATION, ESCALATE_TO_HUMAN}:
            return AutonomousCyclePolicy(
                disposition=AutonomousCycleDisposition.HUMAN_REVIEW,
                reason=f"{decision.rationale} {gate.reason}".strip(),
                risk_level=decision.risk_level,
                requires_validation=gate.requires_validation,
                requires_human_review=True,
                can_merge=False,
                confidence=0.35,
                validation_hint=gate.validation_hint,
                gate_factors=gate.factors,
            )

        if gate.disposition == AutonomousCycleDisposition.HUMAN_REVIEW:
            return AutonomousCyclePolicy(
                disposition=AutonomousCycleDisposition.HUMAN_REVIEW,
                reason=gate.reason,
                risk_level=decision.risk_level,
                requires_validation=False,
                requires_human_review=True,
                can_merge=False,
                confidence=gate.confidence,
                validation_hint=gate.validation_hint,
                gate_factors=gate.factors,
            )

        if gate.disposition == AutonomousCycleDisposition.VALIDATION_ONLY:
            return AutonomousCyclePolicy(
                disposition=AutonomousCycleDisposition.VALIDATION_ONLY,
                reason=gate.reason,
                risk_level=decision.risk_level,
                requires_validation=gate.requires_validation,
                requires_human_review=True,
                can_merge=False,
                confidence=gate.confidence,
                validation_hint=gate.validation_hint,
                gate_factors=gate.factors,
            )

        return AutonomousCyclePolicy(
            disposition=AutonomousCycleDisposition.SAFE_AUTONOMOUS,
            reason=gate.reason,
            risk_level=decision.risk_level,
            requires_validation=gate.requires_validation,
            requires_human_review=gate.requires_human_review,
            can_merge=gate.can_merge,
            confidence=gate.confidence,
            validation_hint=gate.validation_hint,
            gate_factors=gate.factors,
        )

    def create_cycle_record(
        self,
        issue_data: dict[str, Any],
        validation_commands: Sequence[str] | None = None,
        dry_run: bool = True,
    ) -> AutonomousCycleRecord:
        plan = self.plan_cycle(issue_data, validation_commands=validation_commands)
        issue_number = plan.issue_number
        issue_title = plan.issue_title
        issue_url = issue_data.get("url")

        cycle_id = self.store.start_cycle(
            issue_number=issue_number,
            issue_title=issue_title,
            issue_url=issue_url,
            branch_name=plan.branch_name,
            policy=plan.policy,
            validation_commands=plan.validation_commands,
            prompt=plan.prompt,
        )

        if plan.policy.disposition == AutonomousCycleDisposition.BLOCKED:
            self.store.update_cycle(
                cycle_id,
                AutonomousCycleStage.BLOCKED,
                "blocked",
                plan.policy.reason,
                blockers=(plan.policy.reason,),
                learning_signals=(f"blocked:{plan.policy.risk_level}",),
                completed=True,
            )
            record = self.store.get_cycle(cycle_id)
            if record is None:
                raise RuntimeError("Cycle record could not be loaded after blocking.")
            return record

        if plan.policy.disposition == AutonomousCycleDisposition.HUMAN_REVIEW:
            self.store.update_cycle(
                cycle_id,
                AutonomousCycleStage.OCE_GATE,
                "human_review_required",
                plan.policy.reason,
                blockers=("human_review_required",),
                learning_signals=(f"human_review:{plan.policy.risk_level}",),
                completed=True,
            )
            record = self.store.get_cycle(cycle_id)
            if record is None:
                raise RuntimeError("Cycle record could not be loaded after human review gate.")
            return record

        if not dry_run:
            self.command_runner(["git", "checkout", "-b", plan.branch_name], self.workspace_root)

        self.store.update_cycle(
            cycle_id,
            AutonomousCycleStage.BRANCH_CREATION,
            "running",
            f"Prepared feature branch {plan.branch_name}",
            learning_signals=("branch_created",),
        )

        if self.agent_executor is not None:
            implementation_summary = self.agent_executor(plan.prompt, None)
            summary_text = implementation_summary.get("output") if isinstance(implementation_summary, dict) else str(implementation_summary)
            self.store.update_cycle(
                cycle_id,
                AutonomousCycleStage.IMPLEMENTATION,
                "running",
                "Delegated implementation plan to agent executor.",
                learning_signals=("implementation_delegated", _truncate(summary_text or "n/a", 160)),
                payload={"agent_output": summary_text},
            )
        else:
            self.store.update_cycle(
                cycle_id,
                AutonomousCycleStage.IMPLEMENTATION,
                "running",
                "Implementation step is pending an external agent.",
                learning_signals=("implementation_pending",),
            )

        validation_results = self._run_validation(plan.validation_commands, dry_run=dry_run)
        validation_passed = all(result.get("passed", False) for result in validation_results)
        self.store.update_cycle(
            cycle_id,
            AutonomousCycleStage.VALIDATION,
            "passed" if validation_passed else "failed",
            "Validation completed." if validation_passed else "Validation failed.",
            validation_results=validation_results,
            learning_signals=(
                "validation_passed" if validation_passed else "validation_failed",
                *(result.get("command", "") for result in validation_results if not result.get("passed", False)),
            ),
        )

        pr_number = None
        pr_url = None
        if validation_passed and plan.policy.disposition == AutonomousCycleDisposition.SAFE_AUTONOMOUS:
            if not dry_run:
                pr_result = self.command_runner(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--title",
                        f"fix: {issue_title}",
                        "--body",
                        f"Closes #{issue_number}\n\n{issue_title}",
                    ],
                    self.workspace_root,
                )
                pr_output = (pr_result.stdout or "").strip()
                pr_number = _extract_pr_number(pr_output)
                pr_url = _extract_pr_url(pr_output)
            self.store.update_cycle(
                cycle_id,
                AutonomousCycleStage.PR_CREATION,
                "created",
                "Pull request created or prepared.",
                pr_number=pr_number,
                pr_url=pr_url,
                learning_signals=("pr_prepared",),
            )
            if plan.should_merge:
                if not dry_run:
                    self.command_runner(
                        ["gh", "pr", "merge", str(pr_number or ""), "--squash", "--delete-branch"],
                        self.workspace_root,
                    )
                self.store.update_cycle(
                    cycle_id,
                    AutonomousCycleStage.MERGE,
                    "merged",
                    "Merge completed or prepared.",
                    merge_status="merged" if not dry_run else "pending",
                    learning_signals=("merged",),
                    completed=True,
                )
            else:
                self.store.update_cycle(
                    cycle_id,
                    AutonomousCycleStage.REVIEW,
                    "review_required",
                    "Merge gated behind human review.",
                    blockers=("human_review_required",),
                    learning_signals=("review_required",),
                )
        else:
            blocker = "validation_failed" if not validation_passed else "policy_requires_review"
            self.store.update_cycle(
                cycle_id,
                AutonomousCycleStage.REVIEW,
                "review_required",
                "Validation failed or policy does not allow autonomous merge.",
                blockers=(blocker,),
                learning_signals=("review_required",),
            )

        record = self.store.get_cycle(cycle_id)
        if record is None:
            raise RuntimeError("Cycle record could not be loaded.")
        return record

    def _run_validation(self, validation_commands: Sequence[str], dry_run: bool = True) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for command in validation_commands:
            if dry_run:
                results.append({"command": command, "returncode": 0, "passed": True, "stdout": "", "stderr": ""})
                continue
            completed = self.command_runner(_shell_command(command), self.workspace_root)
            results.append(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "passed": completed.returncode == 0,
                    "stdout": getattr(completed, "stdout", "") or "",
                    "stderr": getattr(completed, "stderr", "") or "",
                }
            )
        return results

    def _build_brief(
        self,
        issue_data: dict[str, Any],
        complexity: ComplexityClassification,
        policy: AutonomousCyclePolicy,
        *,
        prior_cycle: AutonomousCycleRecord | None = None,
        recent_signals: Sequence[str] = (),
    ) -> str:
        issue_number = issue_data.get("number", "n/a")
        title = issue_data.get("title", "Untitled")
        body = issue_data.get("body", "")
        labels = [label.get("name", "") for label in issue_data.get("labels", []) if isinstance(label, dict)]
        brief_lines = [
            f"Issue #{issue_number}: {title}",
            f"Complexity={complexity.level.value} score={complexity.score:.1f}",
            f"Policy={policy.disposition.value}",
            f"Reason={policy.reason}",
        ]
        if labels:
            brief_lines.append(f"Labels={', '.join(labels)}")
        if body:
            brief_lines.append(f"Body preview={_truncate(body, 500)}")
        if prior_cycle is not None:
            brief_lines.append("Previous autonomous cycle:")
            brief_lines.append(f"- {prior_cycle.compact_summary()}")
            if prior_cycle.validation_commands:
                brief_lines.append(f"- validation_commands={'; '.join(prior_cycle.validation_commands)}")
            if prior_cycle.validation_results:
                validation_bits = []
                for result in prior_cycle.validation_results[:3]:
                    validation_bits.append(
                        f"{result.get('command', 'n/a')}:{'pass' if result.get('passed', False) else 'fail'}"
                    )
                if validation_bits:
                    brief_lines.append(f"- validation_results={'; '.join(validation_bits)}")
        if recent_signals:
            brief_lines.append("Recent learning signals:")
            brief_lines.extend(f"- {signal}" for signal in recent_signals[:5])
        return "\n".join(brief_lines)

    def _default_validation_commands(self) -> list[str]:
        return [
            "python -m pytest tests/test_autonomous_cycle.py -q",
        ]


def evaluate_autonomy(issue_data: dict[str, Any]) -> AutonomousCyclePolicy:
    workspace_root = Path(issue_data.get("_workspace_root", "."))
    store = WorkspaceMemoryStore(workspace_root / ".workspace-os" / "workspace-memory.sqlite3")
    store.ensure_schema()
    orchestrator = AutonomousCycleOrchestrator(workspace_root=workspace_root, memory_store=store)
    return orchestrator.evaluate_policy(issue_data)


@dataclass(frozen=True)
class AutonomyGateAssessment:
    disposition: AutonomousCycleDisposition
    reason: str
    requires_validation: bool
    requires_human_review: bool
    can_merge: bool
    confidence: float
    validation_hint: str | None
    factors: tuple[str, ...]


def _assess_autonomy_gate(
    issue_data: dict[str, Any],
    complexity: ComplexityClassification,
    validation_commands: Sequence[str],
    workspace_root: Path,
) -> AutonomyGateAssessment:
    title = str(issue_data.get("title", ""))
    body = str(issue_data.get("body", ""))
    labels = [str(label.get("name", "")) for label in issue_data.get("labels", []) if isinstance(label, dict)]
    full_text = " ".join([title, body, " ".join(labels)]).casefold()

    scope_score = complexity.score
    has_tests = _workspace_has_tests(workspace_root)
    coverage_available = has_tests and any("pytest" in command.lower() for command in validation_commands)
    architecture_change = complexity.requires_architecture_decision or _contains_any(
        full_text,
        (
            "architecture",
            "refactor",
            "rewrite",
            "migration",
            "orchestrator",
            "policy",
            "routing",
            "workflow",
            "state",
            "storage",
        ),
    )
    cross_cutting = architecture_change or _contains_any(
        full_text,
        (
            "multiple modules",
            "cross-cutting",
            "integration",
            "shared",
            "core",
            "end to end",
        ),
    )
    merge_risk = "high" if architecture_change or scope_score >= 7.0 else "medium" if scope_score >= 4.0 else "low"
    ambiguity = "high" if complexity.has_ambiguities else "medium" if complexity.level == ComplexityLevel.MODERATE else "low"

    factors = [
        f"scope_size={_scope_label(scope_score)}",
        f"change_surface={'cross-cutting' if cross_cutting else 'local'}",
        f"test_coverage_available={'yes' if coverage_available else 'no'}",
        f"merge_risk={merge_risk}",
        f"ambiguity={ambiguity}",
    ]
    if architecture_change:
        factors.append("architecture_change=yes")
    if complexity.has_ambiguities:
        factors.extend(f"ambiguity_detail={item}" for item in complexity.has_ambiguities[:3])

    if not coverage_available and (complexity.level != ComplexityLevel.SIMPLE or architecture_change or complexity.has_ambiguities):
        return AutonomyGateAssessment(
            disposition=AutonomousCycleDisposition.HUMAN_REVIEW,
            reason="Coverage is not available for a moderate or larger change, so the cycle should stop for human review.",
            requires_validation=True,
            requires_human_review=True,
            can_merge=False,
            confidence=0.45,
            validation_hint="Add or confirm tests before mutation and merge.",
            factors=tuple(factors),
        )

    if complexity.level == ComplexityLevel.COMPLEX or architecture_change or ambiguity == "high" and cross_cutting:
        return AutonomyGateAssessment(
            disposition=AutonomousCycleDisposition.VALIDATION_ONLY,
            reason="The issue crosses architectural or shared-surface boundaries, so WOS may prepare and validate but must stop before autonomous merge.",
            requires_validation=True,
            requires_human_review=True,
            can_merge=False,
            confidence=0.65,
            validation_hint="Run targeted validation and request review before merge.",
            factors=tuple(factors),
        )

    if complexity.level == ComplexityLevel.MODERATE:
        return AutonomyGateAssessment(
            disposition=AutonomousCycleDisposition.VALIDATION_ONLY,
            reason="The change is moderate in scope, so WOS can validate it but should keep the merge behind a review gate.",
            requires_validation=True,
            requires_human_review=True,
            can_merge=False,
            confidence=0.8,
            validation_hint="Validation required before merge.",
            factors=tuple(factors),
        )

    return AutonomyGateAssessment(
        disposition=AutonomousCycleDisposition.SAFE_AUTONOMOUS,
        reason="The issue is small, low-risk, and has enough local coverage for autonomous execution.",
        requires_validation=True,
        requires_human_review=False,
        can_merge=True,
        confidence=0.92,
        validation_hint="Run the narrowest meaningful validation and merge only if it passes.",
        factors=tuple(factors),
    )


def _record_from_row(row: sqlite3.Row) -> AutonomousCycleRecord:
    return AutonomousCycleRecord(
        id=int(row["id"]),
        issue_number=int(row["issue_number"]),
        issue_title=str(row["issue_title"]),
        issue_url=row["issue_url"],
        branch_name=str(row["branch_name"]),
        stage=str(row["stage"]),
        status=str(row["status"]),
        policy_disposition=str(row["policy_disposition"]),
        policy_reason=str(row["policy_reason"]),
        risk_level=str(row["risk_level"]),
        validation_commands=tuple(json.loads(row["validation_commands_json"] or "[]")),
        validation_results=tuple(json.loads(row["validation_results_json"] or "[]")),
        pr_number=int(row["pr_number"]) if row["pr_number"] is not None else None,
        pr_url=row["pr_url"],
        merge_status=row["merge_status"],
        blockers=tuple(json.loads(row["blockers_json"] or "[]")),
        learning_signals=tuple(json.loads(row["learning_signals_json"] or "[]")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        completed_at=row["completed_at"],
    )


def _branch_name(issue_number: int, issue_title: str) -> str:
    slug = _slugify(issue_title)
    if not slug:
        slug = "issue"
    return f"feat/issue-{issue_number}-{slug[:40]}".rstrip("-")


def _slugify(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _dedupe(values: Sequence[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def _shell_command(command: str) -> list[str]:
    return ["powershell", "-NoLogo", "-NoProfile", "-Command", command]


def _run_command(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _extract_pr_number(output: str) -> int | None:
    match = re.search(r"#?(\d+)", output)
    if match:
        return int(match.group(1))
    return None


def _extract_pr_url(output: str) -> str | None:
    match = re.search(r"https://github\.com/\S+", output)
    return match.group(0) if match else None


def _truncate(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."


def _workspace_has_tests(workspace_root: Path) -> bool:
    tests_dir = workspace_root / "tests"
    if not tests_dir.exists() or not tests_dir.is_dir():
        return False
    return any(tests_dir.glob("test_*.py")) or any(tests_dir.rglob("test_*.py"))


def _scope_label(score: float) -> str:
    if score >= 7.0:
        return "large"
    if score >= 4.0:
        return "medium"
    return "small"


def _contains_any(value: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in value for pattern in patterns)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

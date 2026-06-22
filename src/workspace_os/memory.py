from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = 13


@dataclass(frozen=True)
class MemoryHit:
    kind: str
    title: str
    body: str
    created_at: str

    def render(self) -> str:
        return f"- [{self.kind}] {self.title}: {self.body} ({self.created_at})"


class WorkspaceMemoryStore:
    _active_path: Path | None = None

    def __init__(self, path: Path):
        self.path = path
        WorkspaceMemoryStore._active_path = path

    def ensure_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS operator_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS operator_profile (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    context_hash TEXT NOT NULL,
                    outcome TEXT NOT NULL CHECK(outcome IN ('success', 'failure', 'partial')),
                    evidence_ref TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_type, context_hash)
                );

                CREATE TABLE IF NOT EXISTS reusable_lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                    applied_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS decision_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_hash TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    missing_context TEXT NOT NULL,
                    primary_agent TEXT,
                    secondary_agent TEXT,
                    routing_reason TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feedback_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_text TEXT NOT NULL,
                    result_text TEXT NOT NULL,
                    feedback_text TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('positive', 'questionable', 'over_expectation')),
                    error_type TEXT NOT NULL DEFAULT 'neutral',
                    reason TEXT NOT NULL,
                    has_objection INTEGER NOT NULL DEFAULT 0,
                    has_praise INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    batch_id INTEGER,
                    process_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS agent_launches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent TEXT NOT NULL,
                    task TEXT NOT NULL,
                    workspace TEXT,
                    launched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS batch_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );

                CREATE TABLE IF NOT EXISTS process_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );

                CREATE TABLE IF NOT EXISTS process_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process_id INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (process_id) REFERENCES process_runs(id)
                );

                CREATE TABLE IF NOT EXISTS context_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    batch_id INTEGER,
                    process_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS cycle_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );

                CREATE TABLE IF NOT EXISTS cycle_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    iteration_number INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    note TEXT,
                    health_ok INTEGER NOT NULL,
                    stability_ok INTEGER NOT NULL,
                    security_ok INTEGER NOT NULL,
                    quality_ok INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (cycle_id) REFERENCES cycle_runs(id)
                );

                CREATE TABLE IF NOT EXISTS question_answer_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_text TEXT NOT NULL,
                    answer_text TEXT NOT NULL,
                    task_context TEXT NOT NULL,
                    work_item_id TEXT,
                    agent_name TEXT,
                    similarity_hash TEXT,
                    created_at TEXT NOT NULL,
                    batch_id INTEGER,
                    process_id INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_qa_task_context ON question_answer_pairs(task_context);
                CREATE INDEX IF NOT EXISTS idx_qa_similarity_hash ON question_answer_pairs(similarity_hash);
                CREATE INDEX IF NOT EXISTS idx_qa_created_at ON question_answer_pairs(created_at);
                """
            )
            for table in ("task_outcomes", "decision_log", "conversation_turns", "agent_launches", "feedback_events"):
                self._ensure_batch_column(conn, table)
            self._ensure_decision_columns(conn)
            self._ensure_agent_launches_schema(conn)
            self._ensure_feedback_columns(conn)
            self._ensure_cycle_columns(conn)
            conn.execute("DELETE FROM schema_version")
            conn.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
            conn.commit()

    def record_preference(self, key: str, value: str) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO operator_preferences (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key.strip(), value.strip(), _utc_now()),
            )
            conn.commit()

    def get_preference(self, key: str) -> str | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM operator_preferences WHERE key = ?",
                (key.strip(),),
            ).fetchone()
            return str(row["value"]) if row else None

    def set_profile_key(self, key: str, value: str) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO operator_profile (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key.strip(), value.strip(), _utc_now()),
            )
            conn.commit()

    def get_profile_key(self, key: str) -> str | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM operator_profile WHERE key = ?",
                (key.strip(),),
            ).fetchone()
            return str(row["value"]) if row else None

    def record_task_outcome(
        self,
        task_type: str,
        context_hash: str,
        outcome: str,
        evidence_ref: str | None = None,
        created_at: str | None = None,
        batch_id: int | None = None,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO task_outcomes (task_type, context_hash, outcome, evidence_ref, created_at, batch_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_type, context_hash) DO UPDATE SET
                    outcome = excluded.outcome,
                    evidence_ref = excluded.evidence_ref,
                    created_at = excluded.created_at,
                    batch_id = excluded.batch_id
                """,
                (
                    task_type.strip(),
                    context_hash.strip(),
                    outcome.strip(),
                    evidence_ref,
                    created_at or _utc_now(),
                    batch_id if batch_id is not None else self.active_batch_id(conn),
                ),
            )
            conn.commit()

    def record_lesson(
        self,
        category: str,
        rule_text: str,
        evidence_refs: Iterable[str],
        confidence: float,
    ) -> None:
        refs = [ref.strip() for ref in evidence_refs if ref and ref.strip()]
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO reusable_lessons (category, rule_text, evidence_refs, confidence, applied_count, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (category.strip(), rule_text.strip(), json.dumps(refs), confidence, _utc_now()),
            )
            conn.commit()

    def record_decision(
        self,
        request_hash: str,
        risk_level: str,
        decision: str,
        missing_context: Iterable[str],
        primary_agent: str | None = None,
        secondary_agent: str | None = None,
        routing_reason: str | None = None,
        created_at: str | None = None,
        batch_id: int | None = None,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO decision_log (
                    request_hash, risk_level, decision, missing_context,
                    primary_agent, secondary_agent, routing_reason,
                    created_at, batch_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_hash.strip(),
                    risk_level.strip(),
                    decision.strip(),
                    json.dumps([item.strip() for item in missing_context if item and item.strip()]),
                    primary_agent.strip() if primary_agent and primary_agent.strip() else None,
                    secondary_agent.strip() if secondary_agent and secondary_agent.strip() else None,
                    routing_reason.strip() if routing_reason and routing_reason.strip() else None,
                    created_at or _utc_now(),
                    batch_id if batch_id is not None else self.active_batch_id(conn),
                ),
            )
            conn.commit()

    def record_turn(
        self,
        session_id: str,
        role: str,
        message: str,
        created_at: str | None = None,
        batch_id: int | None = None,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO conversation_turns (session_id, role, message, created_at, batch_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id.strip(),
                    role.strip(),
                    message.strip(),
                    created_at or _utc_now(),
                    batch_id if batch_id is not None else self.active_batch_id(conn),
                ),
            )
            conn.commit()

    def record_feedback_event(
        self,
        request_text: str,
        result_text: str,
        feedback_text: str,
        status: str,
        reason: str,
        error_type: str = "neutral",
        has_objection: bool = False,
        has_praise: bool = False,
        created_at: str | None = None,
        batch_id: int | None = None,
        process_id: int | None = None,
    ) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO feedback_events (
                    request_text, result_text, feedback_text, status, error_type, reason,
                    has_objection, has_praise, created_at, batch_id, process_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_text.strip(),
                    result_text.strip(),
                    feedback_text.strip(),
                    status.strip(),
                    error_type.strip() if error_type and error_type.strip() else "neutral",
                    reason.strip(),
                    1 if has_objection else 0,
                    1 if has_praise else 0,
                    created_at or _utc_now(),
                    batch_id if batch_id is not None else self.active_batch_id(conn),
                    process_id if process_id is not None else self.active_process_id(conn),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def record_agent_launch(
        self,
        agent: str,
        task: str,
        workspace: str | None,
        launched_at: str | None = None,
        batch_id: int | None = None,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_launches (agent, task, workspace, launched_at, batch_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    agent.strip(),
                    task.strip(),
                    workspace.strip() if workspace else None,
                    launched_at or _utc_now(),
                    batch_id if batch_id is not None else self.active_batch_id(conn),
                ),
            )
            conn.commit()

    def start_batch(self, label: str, objective: str, started_at: str | None = None) -> int:
        active = self.active_batch()
        if active is not None:
            raise ValueError("A batch is already active.")
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO batch_runs (label, objective, started_at, ended_at)
                VALUES (?, ?, ?, NULL)
                """,
                (label.strip(), objective.strip(), started_at or _utc_now()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def active_batch(self) -> dict[str, str | None] | None:
        with self._connection() as conn:
            return self._active_batch_row(conn)

    def active_batch_id(self, conn: sqlite3.Connection | None = None) -> int | None:
        if conn is not None:
            row = self._active_batch_row(conn)
            return int(row["id"]) if row else None
        with self._connection() as fresh_conn:
            row = self._active_batch_row(fresh_conn)
            return int(row["id"]) if row else None

    def _active_batch_row(self, conn: sqlite3.Connection) -> dict[str, str | None] | None:
        row = conn.execute(
            """
            SELECT id, label, objective, started_at, ended_at
            FROM batch_runs
            WHERE ended_at IS NULL
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "label": str(row["label"]),
            "objective": str(row["objective"]),
            "started_at": str(row["started_at"]),
            "ended_at": row["ended_at"],
        }

    def finish_active_batch(self, ended_at: str | None = None) -> dict[str, str | None] | None:
        batch = self.active_batch()
        if batch is None:
            return None
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE batch_runs
                SET ended_at = ?
                WHERE id = ?
                """,
                (ended_at or _utc_now(), batch["id"]),
            )
            conn.commit()
        return self.get_batch(int(batch["id"]))

    def get_batch(self, batch_id: int) -> dict[str, str | None] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, label, objective, started_at, ended_at
                FROM batch_runs
                WHERE id = ?
                """,
                (batch_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "id": str(row["id"]),
                "label": str(row["label"]),
                "objective": str(row["objective"]),
                "started_at": str(row["started_at"]),
                "ended_at": row["ended_at"],
            }

    def batch_metrics(self, batch_id: int | None = None, now: str | None = None) -> dict[str, object] | None:
        batch = self.get_batch(batch_id) if batch_id is not None else self.active_batch()
        if batch is None:
            return None
        window_end = batch["ended_at"] or (now or _utc_now())
        started_at = str(batch["started_at"])
        batch_id_value = int(batch["id"])
        with self._connection() as conn:
            launch_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM agent_launches
                WHERE (batch_id = ? OR (batch_id IS NULL AND launched_at >= ? AND launched_at <= ?))
                """,
                (batch_id_value, started_at, window_end),
            ).fetchone()
            outcome_rows = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN outcome = 'failure' THEN 1 ELSE 0 END) AS failure_count,
                    SUM(CASE WHEN outcome = 'partial' THEN 1 ELSE 0 END) AS partial_count
                FROM task_outcomes
                WHERE (batch_id = ? OR (batch_id IS NULL AND created_at >= ? AND created_at <= ?))
                """,
                (batch_id_value, started_at, window_end),
            ).fetchone()
            turn_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM conversation_turns
                WHERE (batch_id = ? OR (batch_id IS NULL AND created_at >= ? AND created_at <= ?))
                """,
                (batch_id_value, started_at, window_end),
            ).fetchone()
        total = int(outcome_rows["total"] or 0)
        success_count = int(outcome_rows["success_count"] or 0)
        failure_count = int(outcome_rows["failure_count"] or 0)
        partial_count = int(outcome_rows["partial_count"] or 0)
        return {
            "batch": batch,
            "batch_id": batch_id_value,
            "window_end": window_end,
            "duration_seconds": _duration_seconds(started_at, window_end),
            "delegations": int(launch_count["count"] or 0),
            "defect_iterations": failure_count + partial_count,
            "task_outcome_total": total,
            "task_success_count": success_count,
            "task_failure_count": failure_count,
            "task_partial_count": partial_count,
            "conversation_turns": int(turn_count["count"] or 0),
        }

    def batch_history(self, limit: int = 10) -> list[dict[str, str | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, label, objective, started_at, ended_at
                FROM batch_runs
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {
                    "id": str(row["id"]),
                    "label": str(row["label"]),
                    "objective": str(row["objective"]),
                    "started_at": str(row["started_at"]),
                    "ended_at": row["ended_at"],
                }
                for row in rows
            ]

    def start_process(self, label: str, objective: str, started_at: str | None = None) -> int:
        active = self.active_process()
        if active is not None:
            raise ValueError("A process is already active.")
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO process_runs (label, objective, started_at, ended_at)
                VALUES (?, ?, ?, NULL)
                """,
                (label.strip(), objective.strip(), started_at or _utc_now()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def active_process(self) -> dict[str, str | None] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, label, objective, started_at, ended_at
                FROM process_runs
                WHERE ended_at IS NULL
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            return {
                "id": str(row["id"]),
                "label": str(row["label"]),
                "objective": str(row["objective"]),
                "started_at": str(row["started_at"]),
                "ended_at": row["ended_at"],
            }

    def finish_active_process(self, ended_at: str | None = None) -> dict[str, str | None] | None:
        process = self.active_process()
        if process is None:
            return None
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE process_runs
                SET ended_at = ?
                WHERE id = ?
                """,
                (ended_at or _utc_now(), process["id"]),
            )
            conn.commit()
        return self.get_process(int(process["id"]))

    def get_process(self, process_id: int) -> dict[str, str | None] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, label, objective, started_at, ended_at
                FROM process_runs
                WHERE id = ?
                """,
                (process_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "id": str(row["id"]),
                "label": str(row["label"]),
                "objective": str(row["objective"]),
                "started_at": str(row["started_at"]),
                "ended_at": row["ended_at"],
            }

    def active_process_id(self, conn: sqlite3.Connection | None = None) -> int | None:
        if conn is not None:
            row = self._active_process_row(conn)
            return int(row["id"]) if row else None
        with self._connection() as fresh_conn:
            row = self._active_process_row(fresh_conn)
            return int(row["id"]) if row else None

    def _active_process_row(self, conn: sqlite3.Connection) -> dict[str, str | None] | None:
        row = conn.execute(
            """
            SELECT id, label, objective, started_at, ended_at
            FROM process_runs
            WHERE ended_at IS NULL
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "label": str(row["label"]),
            "objective": str(row["objective"]),
            "started_at": str(row["started_at"]),
            "ended_at": row["ended_at"],
        }

    def process_history(self, limit: int = 10) -> list[dict[str, str | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, label, objective, started_at, ended_at
                FROM process_runs
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {
                    "id": str(row["id"]),
                    "label": str(row["label"]),
                    "objective": str(row["objective"]),
                    "started_at": str(row["started_at"]),
                    "ended_at": row["ended_at"],
                }
                for row in rows
            ]

    def start_cycle(self, label: str, objective: str, started_at: str | None = None) -> int:
        active = self.active_cycle()
        if active is not None:
            raise ValueError("A cycle is already active.")
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO cycle_runs (label, objective, started_at, ended_at)
                VALUES (?, ?, ?, NULL)
                """,
                (label.strip(), objective.strip(), started_at or _utc_now()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def active_cycle(self) -> dict[str, str | None] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, label, objective, started_at, ended_at
                FROM cycle_runs
                WHERE ended_at IS NULL
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            return {
                "id": str(row["id"]),
                "label": str(row["label"]),
                "objective": str(row["objective"]),
                "started_at": str(row["started_at"]),
                "ended_at": row["ended_at"],
            }

    def active_cycle_id(self, conn: sqlite3.Connection | None = None) -> int | None:
        if conn is not None:
            row = self._active_cycle_row(conn)
            return int(row["id"]) if row else None
        with self._connection() as fresh_conn:
            row = self._active_cycle_row(fresh_conn)
            return int(row["id"]) if row else None

    def _active_cycle_row(self, conn: sqlite3.Connection) -> dict[str, str | None] | None:
        row = conn.execute(
            """
            SELECT id, label, objective, started_at, ended_at
            FROM cycle_runs
            WHERE ended_at IS NULL
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "label": str(row["label"]),
            "objective": str(row["objective"]),
            "started_at": str(row["started_at"]),
            "ended_at": row["ended_at"],
        }

    def finish_active_cycle(self, ended_at: str | None = None) -> dict[str, str | None] | None:
        cycle = self.active_cycle()
        if cycle is None:
            return None
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE cycle_runs
                SET ended_at = ?
                WHERE id = ?
                """,
                (ended_at or _utc_now(), cycle["id"]),
            )
            conn.commit()
        return self.get_cycle(int(cycle["id"]))

    def get_cycle(self, cycle_id: int) -> dict[str, str | None] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, label, objective, started_at, ended_at
                FROM cycle_runs
                WHERE id = ?
                """,
                (cycle_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "id": str(row["id"]),
                "label": str(row["label"]),
                "objective": str(row["objective"]),
                "started_at": str(row["started_at"]),
                "ended_at": row["ended_at"],
            }

    def cycle_history(self, limit: int = 10) -> list[dict[str, str | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, label, objective, started_at, ended_at
                FROM cycle_runs
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {
                    "id": str(row["id"]),
                    "label": str(row["label"]),
                    "objective": str(row["objective"]),
                    "started_at": str(row["started_at"]),
                    "ended_at": row["ended_at"],
                }
                for row in rows
            ]

    def record_cycle_checkpoint(
        self,
        label: str,
        iteration_number: int,
        report: dict[str, object],
        note: str | None = None,
        cycle_id: int | None = None,
        created_at: str | None = None,
    ) -> int:
        active_cycle_id = cycle_id
        if active_cycle_id is None:
            with self._connection() as conn:
                active_cycle_id = self.active_cycle_id(conn)
        if active_cycle_id is None:
            raise ValueError("No active cycle found.")
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO cycle_checkpoints (
                    cycle_id, iteration_number, label, note,
                    health_ok, stability_ok, security_ok, quality_ok,
                    report_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    active_cycle_id,
                    iteration_number,
                    label.strip(),
                    note.strip() if note else None,
                    1 if bool(report.get("health_ok")) else 0,
                    1 if bool(report.get("stability_ok")) else 0,
                    1 if bool(report.get("security_ok")) else 0,
                    1 if bool(report.get("quality_ok")) else 0,
                    json.dumps(report, ensure_ascii=False),
                    created_at or _utc_now(),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def cycle_checkpoints(self, cycle_id: int, limit: int = 20) -> list[dict[str, str | int | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, cycle_id, iteration_number, label, note, health_ok, stability_ok, security_ok, quality_ok, report_json, created_at
                FROM cycle_checkpoints
                WHERE cycle_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (cycle_id, limit),
            )
            return [
                {
                    "id": int(row["id"]),
                    "cycle_id": int(row["cycle_id"]),
                    "iteration_number": int(row["iteration_number"]),
                    "label": str(row["label"]),
                    "note": row["note"],
                    "health_ok": int(row["health_ok"] or 0),
                    "stability_ok": int(row["stability_ok"] or 0),
                    "security_ok": int(row["security_ok"] or 0),
                    "quality_ok": int(row["quality_ok"] or 0),
                    "report_json": str(row["report_json"]),
                    "created_at": str(row["created_at"]),
                }
                for row in rows
            ]

    def latest_cycle_checkpoint(self, cycle_id: int) -> dict[str, str | int | None] | None:
        checkpoints = self.cycle_checkpoints(cycle_id, limit=1)
        return checkpoints[0] if checkpoints else None

    def cycle_report(self, cycle_id: int | None = None) -> dict[str, object] | None:
        cycle = self.get_cycle(cycle_id) if cycle_id is not None else self.active_cycle()
        if cycle is None:
            return None
        checkpoints = self.cycle_checkpoints(int(cycle["id"]), limit=100)
        health_passed = sum(1 for checkpoint in checkpoints if checkpoint["health_ok"])
        stability_passed = sum(1 for checkpoint in checkpoints if checkpoint["stability_ok"])
        security_passed = sum(1 for checkpoint in checkpoints if checkpoint["security_ok"])
        quality_passed = sum(1 for checkpoint in checkpoints if checkpoint["quality_ok"])
        total = len(checkpoints)
        return {
            "cycle": cycle,
            "cycle_id": int(cycle["id"]),
            "checkpoint_count": total,
            "health_pass_rate": (health_passed / total) if total else 0.0,
            "stability_pass_rate": (stability_passed / total) if total else 0.0,
            "security_pass_rate": (security_passed / total) if total else 0.0,
            "quality_pass_rate": (quality_passed / total) if total else 0.0,
            "latest_checkpoint": checkpoints[0] if checkpoints else None,
        }

    def record_process_checkpoint(
        self,
        label: str,
        note: str | None = None,
        process_id: int | None = None,
        created_at: str | None = None,
    ) -> int:
        active_process_id = process_id
        if active_process_id is None:
            with self._connection() as conn:
                active_process_id = self.active_process_id(conn)
        if active_process_id is None:
            raise ValueError("No active process found.")
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO process_checkpoints (process_id, label, note, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    active_process_id,
                    label.strip(),
                    note.strip() if note else None,
                    created_at or _utc_now(),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def process_checkpoints(self, process_id: int, limit: int = 20) -> list[dict[str, str | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, process_id, label, note, created_at
                FROM process_checkpoints
                WHERE process_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (process_id, limit),
            )
            return [
                {
                    "id": str(row["id"]),
                    "process_id": str(row["process_id"]),
                    "label": str(row["label"]),
                    "note": row["note"],
                    "created_at": str(row["created_at"]),
                }
                for row in rows
            ]

    def process_checkpoint_count(self, process_id: int) -> int:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM process_checkpoints
                WHERE process_id = ?
                """,
                (process_id,),
            ).fetchone()
            return int(row["count"] or 0) if row else 0

    def latest_process_checkpoint(self, process_id: int) -> dict[str, str | None] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, process_id, label, note, created_at
                FROM process_checkpoints
                WHERE process_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (process_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "id": str(row["id"]),
                "process_id": str(row["process_id"]),
                "label": str(row["label"]),
                "note": row["note"],
                "created_at": str(row["created_at"]),
            }

    def record_context_snapshot(
        self,
        scope: str,
        reason: str,
        summary: str,
        markdown: str,
        created_at: str | None = None,
        batch_id: int | None = None,
        process_id: int | None = None,
    ) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO context_snapshots (scope, reason, summary, markdown, created_at, batch_id, process_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.strip(),
                    reason.strip(),
                    summary.strip(),
                    markdown.strip(),
                    created_at or _utc_now(),
                    batch_id if batch_id is not None else self.active_batch_id(conn),
                    process_id if process_id is not None else self.active_process_id(conn),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def latest_context_snapshot(self, scope: str | None = None) -> dict[str, str | None] | None:
        query = """
            SELECT id, scope, reason, summary, markdown, created_at, batch_id, process_id
            FROM context_snapshots
        """
        params: tuple[object, ...] = ()
        if scope is not None:
            query += " WHERE scope = ?"
            params = (scope.strip(),)
        query += " ORDER BY created_at DESC, id DESC LIMIT 1"
        with self._connection() as conn:
            row = conn.execute(query, params).fetchone()
            if row is None:
                return None
            return {
                "id": str(row["id"]),
                "scope": str(row["scope"]),
                "reason": str(row["reason"]),
                "summary": str(row["summary"]),
                "markdown": str(row["markdown"]),
                "created_at": str(row["created_at"]),
                "batch_id": str(row["batch_id"]) if row["batch_id"] is not None else None,
                "process_id": str(row["process_id"]) if row["process_id"] is not None else None,
            }

    def context_snapshot_count(self) -> int:
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM context_snapshots").fetchone()
            return int(row["count"] or 0) if row else 0

    def context_snapshot_history(self, limit: int = 10) -> list[dict[str, str | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, scope, reason, summary, markdown, created_at, batch_id, process_id
                FROM context_snapshots
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {
                    "id": str(row["id"]),
                    "scope": str(row["scope"]),
                    "reason": str(row["reason"]),
                    "summary": str(row["summary"]),
                    "markdown": str(row["markdown"]),
                    "created_at": str(row["created_at"]),
                    "batch_id": str(row["batch_id"]) if row["batch_id"] is not None else None,
                    "process_id": str(row["process_id"]) if row["process_id"] is not None else None,
                }
                for row in rows
            ]

    def process_metrics(self, process_id: int | None = None, now: str | None = None) -> dict[str, object] | None:
        process = self.get_process(process_id) if process_id is not None else self.active_process()
        if process is None:
            return None
        window_end = process["ended_at"] or (now or _utc_now())
        started_at = str(process["started_at"])
        process_id_value = int(process["id"])
        batches = [
            batch
            for batch in self.batch_history(limit=1000)
            if str(batch["started_at"]) >= started_at and str(batch["started_at"]) <= window_end
        ]
        batch_count = len(batches)
        delegations = 0
        defects = 0
        for batch in batches:
            report = self.batch_metrics(batch_id=int(batch["id"]))
            if report is None:
                continue
            delegations += report["delegations"]
            defects += report["defect_iterations"]
        return {
            "process": process,
            "process_id": process_id_value,
            "window_end": window_end,
            "duration_seconds": _duration_seconds(started_at, window_end),
            "batch_count": batch_count,
            "delegations": delegations,
            "defect_iterations": defects,
            "checkpoint_count": self.process_checkpoint_count(process_id_value),
            "latest_checkpoint": self.latest_process_checkpoint(process_id_value),
        }

    def _ensure_batch_column(self, conn: sqlite3.Connection, table: str) -> None:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN batch_id INTEGER")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).casefold():
                raise

    def _ensure_decision_columns(self, conn: sqlite3.Connection) -> None:
        for column in ("primary_agent", "secondary_agent", "routing_reason"):
            try:
                conn.execute(f"ALTER TABLE decision_log ADD COLUMN {column} TEXT")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).casefold():
                    raise

    def _ensure_agent_launches_schema(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'agent_launches'
            """
        ).fetchone()
        if row is None:
            return
        sql = str(row["sql"] or "")
        if "CHECK(agent IN ('codex', 'claude'))" not in sql:
            return

        conn.execute("ALTER TABLE agent_launches RENAME TO agent_launches_legacy")
        conn.execute(
            """
            CREATE TABLE agent_launches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT NOT NULL,
                task TEXT NOT NULL,
                workspace TEXT,
                launched_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO agent_launches (id, agent, task, workspace, launched_at)
            SELECT id, agent, task, workspace, launched_at
            FROM agent_launches_legacy
            """
        )
        conn.execute("DROP TABLE agent_launches_legacy")

    def _ensure_feedback_columns(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("PRAGMA table_info(feedback_events)").fetchall()
        columns = {str(item["name"]) for item in row}
        if "error_type" not in columns:
            conn.execute("ALTER TABLE feedback_events ADD COLUMN error_type TEXT NOT NULL DEFAULT 'neutral'")

    def _ensure_cycle_columns(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("PRAGMA table_info(cycle_checkpoints)").fetchall()
        columns = {str(item["name"]) for item in row}
        if row and "report_json" not in columns:
            conn.execute("ALTER TABLE cycle_checkpoints ADD COLUMN report_json TEXT NOT NULL DEFAULT '{}'")

    def recent_launches(self, limit: int = 10) -> list[dict[str, str | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT agent, task, workspace, launched_at
                FROM agent_launches
                ORDER BY launched_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {
                    "agent": str(row["agent"]),
                    "task": str(row["task"]),
                    "workspace": row["workspace"],
                    "launched_at": str(row["launched_at"]),
                }
                for row in rows
            ]

    def task_outcome_metrics(self, limit: int | None = None) -> list[dict[str, int | str]]:
        query = """
                SELECT
                    task_type,
                    COUNT(*) AS total,
                    SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN outcome = 'failure' THEN 1 ELSE 0 END) AS failure_count,
                    SUM(CASE WHEN outcome = 'partial' THEN 1 ELSE 0 END) AS partial_count
                FROM task_outcomes
                GROUP BY task_type
                ORDER BY total DESC, task_type ASC
                """
        params: tuple[object, ...] = ()
        if limit is not None:
            query += "\n                LIMIT ?"
            params = (limit,)
        with self._connection() as conn:
            rows = conn.execute(query, params)
            return [
                {
                    "task_type": str(row["task_type"]),
                    "total": int(row["total"]),
                    "success_count": int(row["success_count"] or 0),
                    "failure_count": int(row["failure_count"] or 0),
                    "partial_count": int(row["partial_count"] or 0),
                }
                for row in rows
            ]

    def decision_metrics(self) -> list[dict[str, str | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT risk_level, missing_context, decision, primary_agent, secondary_agent, routing_reason
                FROM decision_log
                ORDER BY created_at DESC, id DESC
                """
            )
            return [
                {
                    "risk_level": str(row["risk_level"]),
                    "missing_context": str(row["missing_context"]),
                    "decision": str(row["decision"]),
                    "primary_agent": row["primary_agent"],
                    "secondary_agent": row["secondary_agent"],
                    "routing_reason": row["routing_reason"],
                }
                for row in rows
            ]

    def decision_metrics_summary(self, limit: int | None = None) -> dict[str, object]:
        decisions = self.decision_metrics()
        if limit is not None:
            decisions = decisions[:limit]

        decision_counts: dict[str, int] = {}
        risk_counts: dict[str, int] = {}
        primary_agent_counts: dict[str, int] = {}
        routing_reason_counts: dict[str, int] = {}
        missing_context_counts: dict[str, int] = {}
        redirect_count = 0
        allow_count = 0
        limit_count = 0
        refuse_count = 0

        for row in decisions:
            decision = row["decision"]
            risk_level = row["risk_level"]
            primary_agent = row["primary_agent"] or "n/a"
            routing_reason = row["routing_reason"] or "n/a"
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
            risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1
            primary_agent_counts[primary_agent] = primary_agent_counts.get(primary_agent, 0) + 1
            routing_reason_counts[routing_reason] = routing_reason_counts.get(routing_reason, 0) + 1
            try:
                missing_items = json.loads(row["missing_context"] or "[]")
            except json.JSONDecodeError:
                missing_items = []
            for item in missing_items:
                missing_context_counts[item] = missing_context_counts.get(item, 0) + 1
            if decision == "SAFE_REDIRECT":
                redirect_count += 1
            elif decision == "ALLOW":
                allow_count += 1
            elif decision == "ALLOW_WITH_LIMITS":
                limit_count += 1
            elif decision == "REFUSE":
                refuse_count += 1

        total = len(decisions)
        return {
            "total": total,
            "decision_counts": decision_counts,
            "risk_counts": risk_counts,
            "primary_agent_counts": primary_agent_counts,
            "routing_reason_counts": routing_reason_counts,
            "missing_context_counts": dict(sorted(missing_context_counts.items(), key=lambda item: (-item[1], item[0]))),
            "top_missing_context": _top_missing_context(missing_context_counts),
            "recommended_next_action": _recommended_next_action(missing_context_counts, routing_reason_counts, primary_agent_counts),
            "redirect_rate": (redirect_count / total) if total else 0.0,
            "allow_rate": (allow_count / total) if total else 0.0,
            "limit_rate": (limit_count / total) if total else 0.0,
            "refusal_rate": (refuse_count / total) if total else 0.0,
        }

    def recent_conversation_turns(self, limit: int = 30, session_id: str | None = None) -> list[dict[str, str]]:
        with self._connection() as conn:
            query = """
                SELECT session_id, role, message, created_at
                FROM conversation_turns
            """
            params: tuple[object, ...]
            if session_id is not None:
                query += " WHERE session_id = ?"
                params = (session_id.strip(), limit)
                query += " ORDER BY created_at DESC, id DESC LIMIT ?"
            else:
                params = (limit,)
                query += " ORDER BY created_at DESC, id DESC LIMIT ?"
            rows = conn.execute(query, params)
            return [
                {
                    "session_id": str(row["session_id"]),
                    "role": str(row["role"]),
                    "message": str(row["message"]),
                    "created_at": str(row["created_at"]),
                }
                for row in rows
            ]

    def feedback_history(self, limit: int = 20) -> list[dict[str, str | int | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, request_text, result_text, feedback_text, status, error_type, reason, has_objection, has_praise, created_at, batch_id, process_id
                FROM feedback_events
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {
                    "id": int(row["id"]),
                    "request_text": str(row["request_text"]),
                    "result_text": str(row["result_text"]),
                    "feedback_text": str(row["feedback_text"]),
                    "status": str(row["status"]),
                    "error_type": str(row["error_type"] or "neutral"),
                    "reason": str(row["reason"]),
                    "has_objection": int(row["has_objection"] or 0),
                    "has_praise": int(row["has_praise"] or 0),
                    "created_at": str(row["created_at"]),
                    "batch_id": int(row["batch_id"]) if row["batch_id"] is not None else None,
                    "process_id": int(row["process_id"]) if row["process_id"] is not None else None,
                }
                for row in rows
            ]

    def feedback_metrics(self) -> dict[str, int]:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'positive' THEN 1 ELSE 0 END) AS positive_count,
                    SUM(CASE WHEN status = 'questionable' THEN 1 ELSE 0 END) AS questionable_count,
                    SUM(CASE WHEN status = 'over_expectation' THEN 1 ELSE 0 END) AS over_expectation_count,
                    SUM(CASE WHEN error_type = 'too_verbose' THEN 1 ELSE 0 END) AS too_verbose_count,
                    SUM(CASE WHEN error_type = 'wrong_agent' THEN 1 ELSE 0 END) AS wrong_agent_count,
                    SUM(CASE WHEN error_type = 'missing_repo_resolution' THEN 1 ELSE 0 END) AS missing_repo_resolution_count,
                    SUM(CASE WHEN error_type = 'missing_clarification' THEN 1 ELSE 0 END) AS missing_clarification_count,
                    SUM(CASE WHEN error_type = 'ignored_preference' THEN 1 ELSE 0 END) AS ignored_preference_count,
                    SUM(CASE WHEN error_type = 'generic_fallback' THEN 1 ELSE 0 END) AS generic_fallback_count,
                    SUM(has_objection) AS objection_count,
                    SUM(has_praise) AS praise_count
                FROM feedback_events
                """
            ).fetchone()
            return {
                "total": int(row["total"] or 0) if row else 0,
                "positive_count": int(row["positive_count"] or 0) if row else 0,
                "questionable_count": int(row["questionable_count"] or 0) if row else 0,
                "over_expectation_count": int(row["over_expectation_count"] or 0) if row else 0,
                "too_verbose_count": int(row["too_verbose_count"] or 0) if row else 0,
                "wrong_agent_count": int(row["wrong_agent_count"] or 0) if row else 0,
                "missing_repo_resolution_count": int(row["missing_repo_resolution_count"] or 0) if row else 0,
                "missing_clarification_count": int(row["missing_clarification_count"] or 0) if row else 0,
                "ignored_preference_count": int(row["ignored_preference_count"] or 0) if row else 0,
                "generic_fallback_count": int(row["generic_fallback_count"] or 0) if row else 0,
                "objection_count": int(row["objection_count"] or 0) if row else 0,
                "praise_count": int(row["praise_count"] or 0) if row else 0,
            }

    def search(self, query: str, limit: int = 8) -> list[MemoryHit]:
        needle = f"%{query.strip()}%"
        if not query.strip():
            return self.recent(limit=limit)

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT kind, title, body, created_at FROM (
                    SELECT 'preference' AS kind, key AS title, value AS body, updated_at AS created_at
                    FROM operator_preferences
                    WHERE key LIKE :needle OR value LIKE :needle
                    UNION ALL
                    SELECT 'lesson' AS kind, category AS title, rule_text AS body, created_at
                    FROM reusable_lessons
                    WHERE category LIKE :needle OR rule_text LIKE :needle OR evidence_refs LIKE :needle
                    UNION ALL
                    SELECT 'outcome' AS kind, task_type AS title, outcome || COALESCE(' [' || evidence_ref || ']', '') AS body, created_at
                    FROM task_outcomes
                    WHERE task_type LIKE :needle OR context_hash LIKE :needle OR outcome LIKE :needle OR COALESCE(evidence_ref, '') LIKE :needle
                    UNION ALL
                    SELECT 'decision' AS kind, decision AS title, risk_level || ' ' || missing_context AS body, created_at
                    FROM decision_log
                    WHERE request_hash LIKE :needle OR risk_level LIKE :needle OR decision LIKE :needle OR missing_context LIKE :needle
                    UNION ALL
                    SELECT 'conversation' AS kind, role AS title, message AS body, created_at
                    FROM conversation_turns
                    WHERE session_id LIKE :needle OR role LIKE :needle OR message LIKE :needle
                    UNION ALL
                    SELECT 'feedback' AS kind, status AS title, feedback_text || ' [' || error_type || ']' AS body, created_at
                    FROM feedback_events
                    WHERE request_text LIKE :needle OR result_text LIKE :needle OR feedback_text LIKE :needle OR status LIKE :needle OR reason LIKE :needle OR error_type LIKE :needle
                    UNION ALL
                    SELECT 'snapshot' AS kind, scope || ' ' || reason AS title, summary AS body, created_at
                    FROM context_snapshots
                    WHERE scope LIKE :needle OR reason LIKE :needle OR summary LIKE :needle OR markdown LIKE :needle
                )
                ORDER BY created_at DESC
                LIMIT :limit
                """,
                {"needle": needle, "limit": limit},
            )
            return [MemoryHit(row["kind"], row["title"], row["body"], row["created_at"]) for row in rows]

    def recent(self, limit: int = 8) -> list[MemoryHit]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT kind, title, body, created_at FROM (
                    SELECT 'preference' AS kind, key AS title, value AS body, updated_at AS created_at
                    FROM operator_preferences
                    UNION ALL
                    SELECT 'lesson' AS kind, category AS title, rule_text AS body, created_at
                    FROM reusable_lessons
                    UNION ALL
                    SELECT 'outcome' AS kind, task_type AS title, outcome AS body, created_at
                    FROM task_outcomes
                    UNION ALL
                    SELECT 'decision' AS kind, decision AS title, risk_level || ' ' || missing_context AS body, created_at
                    FROM decision_log
                    UNION ALL
                    SELECT 'conversation' AS kind, role AS title, message AS body, created_at
                    FROM conversation_turns
                    UNION ALL
                    SELECT 'feedback' AS kind, status AS title, feedback_text || ' [' || error_type || ']' AS body, created_at
                    FROM feedback_events
                    UNION ALL
                    SELECT 'snapshot' AS kind, scope || ' ' || reason AS title, summary AS body, created_at
                    FROM context_snapshots
                )
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [MemoryHit(row["kind"], row["title"], row["body"], row["created_at"]) for row in rows]

    def stats(self) -> dict[str, int]:
        with self._connection() as conn:
            counts = {}
            for table in (
                "operator_preferences",
                "operator_profile",
                "task_outcomes",
                "reusable_lessons",
                "decision_log",
                "conversation_turns",
                "feedback_events",
                "agent_launches",
                "context_snapshots",
                "cycle_runs",
                "cycle_checkpoints",
                "question_answer_pairs",
            ):
                row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
                counts[table] = int(row["count"]) if row else 0
            return counts

    def record_qa(
        self,
        question: str,
        answer: str,
        task_context: str,
        work_item_id: str | None = None,
        agent_name: str | None = None,
    ) -> None:
        """Record a question-answer pair for learning and future suggestions."""
        import hashlib

        similarity_hash = hashlib.md5(question.lower().strip().encode()).hexdigest()[:16]

        with self._connection() as conn:
            batch_id = self.active_batch_id(conn)
            process_id = self.active_process_id(conn)

            conn.execute(
                """
                INSERT INTO question_answer_pairs
                (question_text, answer_text, task_context, work_item_id, agent_name,
                 similarity_hash, created_at, batch_id, process_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question.strip(),
                    answer.strip(),
                    task_context.strip(),
                    work_item_id,
                    agent_name,
                    similarity_hash,
                    _utc_now(),
                    batch_id,
                    process_id,
                ),
            )
            conn.commit()

    def get_similar_questions(
        self,
        task_context: str,
        limit: int = 5,
    ) -> list[dict[str, str]]:
        """Find questions from similar task contexts."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT question_text, answer_text, task_context, agent_name, created_at, similarity_hash
                FROM question_answer_pairs
                WHERE task_context LIKE ?
                   OR similarity_hash IN (
                       SELECT similarity_hash
                       FROM question_answer_pairs
                       WHERE task_context LIKE ?
                   )
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (f"%{task_context}%", f"%{task_context}%", limit * 3),
            )
            return [
                {
                    "question": str(row["question_text"]),
                    "answer": str(row["answer_text"]),
                    "context": str(row["task_context"]),
                    "agent": str(row["agent_name"]) if row["agent_name"] else "unknown",
                    "created_at": str(row["created_at"]),
                }
                for row in rows
            ]

    def get_qa_for_work_item(self, work_item_id: str) -> list[dict[str, str]]:
        """Get all Q&A pairs for a specific work item."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT question_text, answer_text, task_context, agent_name, created_at
                FROM question_answer_pairs
                WHERE work_item_id = ?
                ORDER BY created_at ASC
                """,
                (work_item_id,),
            )
            return [
                {
                    "question": str(row["question_text"]),
                    "answer": str(row["answer_text"]),
                    "context": str(row["task_context"]),
                    "agent": str(row["agent_name"]) if row["agent_name"] else "unknown",
                    "created_at": str(row["created_at"]),
                }
                for row in rows
            ]

    def qa_metrics(self) -> dict[str, int]:
        """Get Q&A metrics."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT task_context) as unique_contexts,
                    COUNT(DISTINCT similarity_hash) as unique_questions
                FROM question_answer_pairs
                """
            ).fetchone()

            return {
                "total": int(row["total"]) if row else 0,
                "unique_contexts": int(row["unique_contexts"]) if row else 0,
                "unique_questions": int(row["unique_questions"]) if row else 0,
            }

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _duration_seconds(started_at: str, ended_at: str) -> float:
    start = datetime.fromisoformat(started_at)
    end = datetime.fromisoformat(ended_at)
    return max(0.0, (end - start).total_seconds())


def _top_missing_context(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _recommended_next_action(
    missing_context_counts: dict[str, int],
    routing_reason_counts: dict[str, int],
    primary_agent_counts: dict[str, int],
) -> str:
    top_missing = _top_missing_context(missing_context_counts)
    top_routing = _top_context_key(routing_reason_counts)
    top_agent = _top_context_key(primary_agent_counts)

    if top_missing in {"authorization", "role", "permission", "owner", "ownership"}:
        return "ask_clarification_before_delegating"
    if top_missing in {"workspace", "inventory", "repo", "branch", "status", "missing_workspace"}:
        return "route_to_opencode_for_inventory"
    if top_missing in {"safety", "privacy", "legal", "policy"}:
        return "route_to_claude_for_cross_check"
    if top_routing and "clarify" in top_routing:
        return "prefer_minimal_clarification_then_delegate"
    if top_agent == "opencode":
        return "keep_opencode_as_primary_for_workspace_execution"
    if top_agent == "claude":
        return "keep_claude_as_primary_for_sensitive_reviews"
    if top_agent == "codex":
        return "keep_opencode_as_primary_for_workspace_execution"
    return "keep_ambiguous_requests_explicit_and_actionable"


def _top_context_key(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = 4


@dataclass(frozen=True)
class MemoryHit:
    kind: str
    title: str
    body: str
    created_at: str

    def render(self) -> str:
        return f"- [{self.kind}] {self.title}: {self.body} ({self.created_at})"


class WorkspaceMemoryStore:
    def __init__(self, path: Path):
        self.path = path

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
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_launches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent TEXT NOT NULL CHECK(agent IN ('codex', 'claude')),
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
                """
            )
            for table in ("task_outcomes", "decision_log", "conversation_turns", "agent_launches"):
                self._ensure_batch_column(conn, table)
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
        created_at: str | None = None,
        batch_id: int | None = None,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO decision_log (request_hash, risk_level, decision, missing_context, created_at, batch_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request_hash.strip(),
                    risk_level.strip(),
                    decision.strip(),
                    json.dumps([item.strip() for item in missing_context if item and item.strip()]),
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

    def _ensure_batch_column(self, conn: sqlite3.Connection, table: str) -> None:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN batch_id INTEGER")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).casefold():
                raise

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

    def decision_metrics(self) -> list[dict[str, str]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT risk_level, missing_context
                FROM decision_log
                ORDER BY created_at DESC, id DESC
                """
            )
            return [
                {
                    "risk_level": str(row["risk_level"]),
                    "missing_context": str(row["missing_context"]),
                }
                for row in rows
            ]

    def recent_conversation_turns(self, limit: int = 30) -> list[dict[str, str]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT session_id, role, message, created_at
                FROM conversation_turns
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {
                    "session_id": str(row["session_id"]),
                    "role": str(row["role"]),
                    "message": str(row["message"]),
                    "created_at": str(row["created_at"]),
                }
                for row in rows
            ]

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
                "agent_launches",
            ):
                row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
                counts[table] = int(row["count"]) if row else 0
            return counts

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
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _duration_seconds(started_at: str, ended_at: str) -> int:
    start = datetime.fromisoformat(started_at)
    end = datetime.fromisoformat(ended_at)
    return max(0, int((end - start).total_seconds()))

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = 2


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
                """
            )
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
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO task_outcomes (task_type, context_hash, outcome, evidence_ref, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(task_type, context_hash) DO UPDATE SET
                    outcome = excluded.outcome,
                    evidence_ref = excluded.evidence_ref,
                    created_at = excluded.created_at
                """,
                (task_type.strip(), context_hash.strip(), outcome.strip(), evidence_ref, _utc_now()),
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
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO decision_log (request_hash, risk_level, decision, missing_context, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    request_hash.strip(),
                    risk_level.strip(),
                    decision.strip(),
                    json.dumps([item.strip() for item in missing_context if item and item.strip()]),
                    _utc_now(),
                ),
            )
            conn.commit()

    def record_turn(self, session_id: str, role: str, message: str) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO conversation_turns (session_id, role, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id.strip(), role.strip(), message.strip(), _utc_now()),
            )
            conn.commit()

    def record_agent_launch(self, agent: str, task: str, workspace: str | None) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_launches (agent, task, workspace, launched_at)
                VALUES (?, ?, ?, ?)
                """,
                (agent.strip(), task.strip(), workspace.strip() if workspace else None, _utc_now()),
            )
            conn.commit()

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

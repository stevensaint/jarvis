"""SQLite persistence for registry snapshots, routing evidence, and outcomes."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .contracts import OutcomeRecord, RoutingDecision, WorkerDescriptor

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class WorkerRoutingStore:
    """Small synchronous store used only for bounded routing metadata writes."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path, timeout=5.0, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
            columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(julia_workers)")
            }
            if "node_id" not in columns:
                conn.execute("ALTER TABLE julia_workers ADD COLUMN node_id TEXT")
            self._conn = conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("WorkerRoutingStore: call open() before use")
        return self._conn

    def upsert_worker(self, worker: WorkerDescriptor) -> None:
        payload = worker.model_dump_json()
        updated_at = time.time_ns() // 1_000_000
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO julia_workers (
                    worker_id, provider, model, worker_class,
                    node_id,
                    authorization_state, availability_state, privacy_class,
                    descriptor_json, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    provider=excluded.provider,
                    model=excluded.model,
                    worker_class=excluded.worker_class,
                    node_id=excluded.node_id,
                    authorization_state=excluded.authorization_state,
                    availability_state=excluded.availability_state,
                    privacy_class=excluded.privacy_class,
                    descriptor_json=excluded.descriptor_json,
                    updated_at_ms=excluded.updated_at_ms
                """,
                (
                    worker.worker_id,
                    worker.provider,
                    worker.model,
                    worker.worker_class,
                    worker.node_id,
                    worker.authorization_state.value,
                    worker.availability.state.value,
                    worker.privacy_class.value,
                    payload,
                    updated_at,
                ),
            )

    def list_workers(self) -> tuple[WorkerDescriptor, ...]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT descriptor_json FROM julia_workers ORDER BY worker_id"
            ).fetchall()
        return tuple(WorkerDescriptor.model_validate_json(str(row[0])) for row in rows)

    def save_decision(self, decision: RoutingDecision) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO julia_routing_decisions (
                    decision_id, objective_id, task_id, task_category,
                    selected_worker_id, decision_json, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.objective_id,
                    decision.task_id,
                    decision.task_category,
                    decision.selected_worker_id,
                    decision.model_dump_json(),
                    decision.created_at_ms,
                ),
            )

    def decisions_for_task(self, task_id: str) -> tuple[RoutingDecision, ...]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT decision_json FROM julia_routing_decisions
                WHERE task_id = ? ORDER BY created_at_ms, rowid
                """,
                (task_id,),
            ).fetchall()
        return tuple(RoutingDecision.model_validate_json(str(row[0])) for row in rows)

    def decisions_for_objective(self, objective_id: str) -> tuple[RoutingDecision, ...]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT decision_json FROM julia_routing_decisions
                WHERE objective_id = ? ORDER BY created_at_ms, rowid
                """,
                (objective_id,),
            ).fetchall()
        return tuple(RoutingDecision.model_validate_json(str(row[0])) for row in rows)

    def record_outcome(self, outcome: OutcomeRecord) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO julia_worker_outcomes (
                    objective_id, task_id, task_category, worker_id, provider,
                    model, failure_type, final_status, outcome_json, recorded_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.objective_id,
                    outcome.task_id,
                    outcome.task_category,
                    outcome.worker_id,
                    outcome.provider,
                    outcome.model,
                    outcome.failure_type.value if outcome.failure_type else None,
                    outcome.final_status,
                    outcome.model_dump_json(),
                    outcome.recorded_at_ms,
                ),
            )

    def aggregate_metrics(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT worker_id, task_category,
                       COUNT(*) AS attempts,
                       SUM(CASE WHEN final_status = 'success' THEN 1 ELSE 0 END) AS successes,
                       AVG(CAST(json_extract(outcome_json, '$.attempts') AS REAL)) AS average_attempts,
                       AVG(CAST(json_extract(outcome_json, '$.actual_cost_usd') AS REAL)) AS average_cost_usd,
                       AVG(CAST(json_extract(outcome_json, '$.duration_ms') AS REAL)) AS average_latency_ms,
                       AVG(CASE WHEN json_extract(outcome_json, '$.critic_result') = 'approve' THEN 1.0 ELSE 0.0 END) AS critic_acceptance_rate,
                       AVG(CASE WHEN json_extract(outcome_json, '$.human_correction') = 1 THEN 1.0 ELSE 0.0 END) AS human_correction_rate
                FROM julia_worker_outcomes
                GROUP BY worker_id, task_category
                ORDER BY worker_id, task_category
                """
            ).fetchall()
        return [
            {
                "worker_id": str(row[0]),
                "task_category": str(row[1]),
                "attempts": int(row[2]),
                "success_rate": float(row[3]) / int(row[2]) if row[2] else 0.0,
                "critic_acceptance_rate": float(row[7] or 0.0),
                "average_attempts": float(row[4] or 0.0),
                "average_cost_usd": float(row[5] or 0.0),
                "average_latency_ms": float(row[6] or 0.0),
                "human_correction_rate": float(row[8] or 0.0),
            }
            for row in rows
        ]

"""SQLite ledger for Julia lifecycle, nodes, execution, and recovery."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .contracts import (
    ExecutionAttempt,
    ExecutionState,
    NodeDescriptor,
    RecoveryRecord,
    RuntimeSnapshot,
    RuntimeState,
    SideEffectState,
    now_ms,
)

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class JuliaRuntimeStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
            self._conn = conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("JuliaRuntimeStore: call open() before use")
        return self._conn

    def save_runtime(self, snapshot: RuntimeSnapshot, *, event: bool = True) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO julia_runtime_state(singleton, snapshot_json, updated_at_ms)
                VALUES (1, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    snapshot_json=excluded.snapshot_json,
                    updated_at_ms=excluded.updated_at_ms
                """,
                (snapshot.model_dump_json(), snapshot.updated_at_ms),
            )
            if event:
                self.conn.execute(
                    """
                    INSERT INTO julia_runtime_events(
                        event_type, state, node_id, detail, created_at_ms
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "RuntimeStateChanged",
                        snapshot.state.value,
                        snapshot.primary_node_id,
                        snapshot.detail,
                        snapshot.updated_at_ms,
                    ),
                )

    def runtime_snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            row = self.conn.execute(
                "SELECT snapshot_json FROM julia_runtime_state WHERE singleton = 1"
            ).fetchone()
        if row is None:
            return RuntimeSnapshot(
                state=RuntimeState.STOPPED,
                desired_state=RuntimeState.STOPPED,
                detail="runtime has not started",
            )
        return RuntimeSnapshot.model_validate_json(str(row[0]))

    def set_desired_state(self, state: RuntimeState, *, detail: str) -> RuntimeSnapshot:
        current = self.runtime_snapshot()
        updated = current.model_copy(
            update={"desired_state": state, "updated_at_ms": now_ms(), "detail": detail}
        )
        self.save_runtime(updated)
        return updated

    def lifecycle_events(self, *, limit: int = 100) -> list[dict[str, object]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT seq, event_type, state, node_id, detail, created_at_ms
                FROM julia_runtime_events ORDER BY seq DESC LIMIT ?
                """,
                (max(1, min(limit, 1000)),),
            ).fetchall()
        return [
            {
                "seq": int(row[0]),
                "event_type": str(row[1]),
                "state": str(row[2]),
                "node_id": str(row[3]) if row[3] is not None else None,
                "detail": str(row[4]),
                "created_at_ms": int(row[5]),
            }
            for row in rows
        ]

    def upsert_node(self, node: NodeDescriptor) -> None:
        with self._lock, self.conn:
            if node.is_primary:
                rows = self.conn.execute(
                    """
                    SELECT node_id, descriptor_json FROM julia_nodes
                    WHERE node_id <> ? AND is_primary = 1
                    """,
                    (node.node_id,),
                ).fetchall()
                for prior_id, descriptor_json in rows:
                    prior = NodeDescriptor.model_validate_json(str(descriptor_json))
                    demoted = prior.model_copy(
                        update={"is_primary": False, "last_seen_ms": now_ms()}
                    )
                    self.conn.execute(
                        """
                        UPDATE julia_nodes
                        SET is_primary = 0, descriptor_json = ?, updated_at_ms = ?
                        WHERE node_id = ?
                        """,
                        (demoted.model_dump_json(), demoted.last_seen_ms, str(prior_id)),
                    )
            self.conn.execute(
                """
                INSERT INTO julia_nodes(
                    node_id, availability_state, is_primary,
                    descriptor_json, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    availability_state=excluded.availability_state,
                    is_primary=excluded.is_primary,
                    descriptor_json=excluded.descriptor_json,
                    updated_at_ms=excluded.updated_at_ms
                """,
                (
                    node.node_id,
                    node.availability_state.value,
                    int(node.is_primary),
                    node.model_dump_json(),
                    node.last_seen_ms,
                ),
            )

    def nodes(self) -> tuple[NodeDescriptor, ...]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT descriptor_json FROM julia_nodes ORDER BY node_id"
            ).fetchall()
        return tuple(NodeDescriptor.model_validate_json(str(row[0])) for row in rows)

    def node(self, node_id: str) -> NodeDescriptor | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT descriptor_json FROM julia_nodes WHERE node_id = ?",
                (node_id,),
            ).fetchone()
        return NodeDescriptor.model_validate_json(str(row[0])) if row else None

    def save_attempt(self, attempt: ExecutionAttempt) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO julia_execution_attempts(
                    attempt_id, idempotency_key, objective_id, task_id,
                    node_id, worker_id, state, side_effect_state,
                    attempt_json, created_at_ms, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET
                    state=excluded.state,
                    side_effect_state=excluded.side_effect_state,
                    attempt_json=excluded.attempt_json,
                    updated_at_ms=excluded.updated_at_ms
                """,
                (
                    attempt.attempt_id,
                    attempt.idempotency_key,
                    attempt.objective_id,
                    attempt.task_id,
                    attempt.node_id,
                    attempt.worker_id,
                    attempt.state.value,
                    attempt.side_effect_state.value,
                    attempt.model_dump_json(),
                    attempt.created_at_ms,
                    attempt.updated_at_ms,
                ),
            )

    def attempt_for_key(self, idempotency_key: str) -> ExecutionAttempt | None:
        with self._lock:
            row = self.conn.execute(
                """
                SELECT attempt_json FROM julia_execution_attempts
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
        return ExecutionAttempt.model_validate_json(str(row[0])) if row else None

    def attempt(self, attempt_id: str) -> ExecutionAttempt | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT attempt_json FROM julia_execution_attempts WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
        return ExecutionAttempt.model_validate_json(str(row[0])) if row else None

    def interrupted_attempts(self) -> tuple[ExecutionAttempt, ...]:
        terminal = (
            ExecutionState.SUCCEEDED.value,
            ExecutionState.FAILED.value,
            ExecutionState.CANCELLED.value,
            ExecutionState.INTERRUPTED.value,
        )
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT attempt_json FROM julia_execution_attempts
                WHERE state NOT IN (?, ?, ?, ?) ORDER BY created_at_ms
                """,
                terminal,
            ).fetchall()
        return tuple(ExecutionAttempt.model_validate_json(str(row[0])) for row in rows)

    def update_attempt(
        self,
        attempt_id: str,
        *,
        state: ExecutionState,
        side_effect_state: SideEffectState | None = None,
        detail: str = "",
    ) -> ExecutionAttempt:
        current = self.attempt(attempt_id)
        if current is None:
            raise KeyError(attempt_id)
        updated = current.model_copy(
            update={
                "state": state,
                "side_effect_state": side_effect_state or current.side_effect_state,
                "updated_at_ms": now_ms(),
                "detail": detail or current.detail,
            }
        )
        self.save_attempt(updated)
        return updated

    def save_recovery(self, record: RecoveryRecord) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO julia_recovery_records(
                    recovery_id, attempt_id, objective_id, task_id,
                    disposition, recovery_json, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.recovery_id,
                    record.attempt_id,
                    record.objective_id,
                    record.task_id,
                    record.disposition.value,
                    record.model_dump_json(),
                    record.created_at_ms,
                ),
            )

    def recovery_records(self, *, limit: int = 100) -> tuple[RecoveryRecord, ...]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT recovery_json FROM julia_recovery_records
                ORDER BY created_at_ms DESC LIMIT ?
                """,
                (max(1, min(limit, 1000)),),
            ).fetchall()
        return tuple(RecoveryRecord.model_validate_json(str(row[0])) for row in rows)

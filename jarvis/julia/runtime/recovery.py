"""Idempotent execution tracking and authority-preserving recovery."""

from __future__ import annotations

from uuid import uuid4

from .contracts import (
    ExecutionAttempt,
    ExecutionState,
    RecoveryDisposition,
    RecoveryRecord,
    SideEffectState,
    now_ms,
)
from .store import JuliaRuntimeStore


class DuplicateExecutionError(RuntimeError):
    def __init__(self, attempt: ExecutionAttempt) -> None:
        super().__init__(
            f"execution key {attempt.idempotency_key!r} already exists in {attempt.state.value}"
        )
        self.attempt = attempt


class ExecutionRecoveryManager:
    def __init__(self, store: JuliaRuntimeStore) -> None:
        self.store = store

    def begin(
        self,
        *,
        idempotency_key: str,
        objective_id: str,
        task_id: str,
        iteration: int,
        authorization: dict[str, object],
        node_id: str | None,
        worker_id: str | None,
        resumable: bool,
        retry_safe: bool,
    ) -> ExecutionAttempt:
        existing = self.store.attempt_for_key(idempotency_key)
        if existing is not None:
            raise DuplicateExecutionError(existing)
        attempt = ExecutionAttempt(
            attempt_id=str(uuid4()),
            idempotency_key=idempotency_key,
            objective_id=objective_id,
            task_id=task_id,
            iteration=iteration,
            node_id=node_id,
            worker_id=worker_id,
            state=ExecutionState.RUNNING,
            side_effect_state=SideEffectState.NONE,
            authorization=authorization,
            resumable=resumable,
            retry_safe=retry_safe,
        )
        self.store.save_attempt(attempt)
        return attempt

    def checkpoint(
        self,
        attempt_id: str,
        *,
        state: ExecutionState,
        side_effect_state: SideEffectState,
        detail: str = "",
    ) -> ExecutionAttempt:
        return self.store.update_attempt(
            attempt_id,
            state=state,
            side_effect_state=side_effect_state,
            detail=detail,
        )

    @staticmethod
    def classify(attempt: ExecutionAttempt) -> tuple[RecoveryDisposition, str]:
        if attempt.state is ExecutionState.AWAITING_APPROVAL:
            return RecoveryDisposition.AWAIT_APPROVAL, "approval was not granted before restart"
        if attempt.state is ExecutionState.AWAITING_VERIFICATION:
            return RecoveryDisposition.VERIFY, "worker result exists but verification is incomplete"
        if attempt.side_effect_state is SideEffectState.UNKNOWN:
            return (
                RecoveryDisposition.MANUAL_RECONCILIATION,
                "external side effects may have occurred; blind retry is prohibited",
            )
        if attempt.side_effect_state is SideEffectState.COMMITTED:
            return RecoveryDisposition.VERIFY, "committed side effect must be verified"
        if attempt.resumable:
            return RecoveryDisposition.RESUME, "attempt declared resumable under original authority"
        if attempt.retry_safe and attempt.side_effect_state in {
            SideEffectState.NONE,
            SideEffectState.IDEMPOTENT,
        }:
            return RecoveryDisposition.RETRY, "attempt is explicitly retry-safe"
        if attempt.node_id:
            return RecoveryDisposition.REPLAN, "attempt requires an eligibility replan"
        return RecoveryDisposition.MANUAL_RECONCILIATION, "safe replay cannot be proven"

    def recover_interrupted(self) -> tuple[RecoveryRecord, ...]:
        records: list[RecoveryRecord] = []
        for attempt in self.store.interrupted_attempts():
            disposition, reason = self.classify(attempt)
            interrupted = attempt.model_copy(
                update={
                    "state": ExecutionState.INTERRUPTED,
                    "updated_at_ms": now_ms(),
                    "detail": reason,
                }
            )
            self.store.save_attempt(interrupted)
            record = RecoveryRecord(
                recovery_id=str(uuid4()),
                attempt_id=attempt.attempt_id,
                objective_id=attempt.objective_id,
                task_id=attempt.task_id,
                disposition=disposition,
                reason=reason,
                authorization=attempt.authorization,
            )
            self.store.save_recovery(record)
            records.append(record)
        return tuple(records)

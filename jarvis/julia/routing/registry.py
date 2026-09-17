"""Authoritative in-process worker registry with durable availability updates."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from .contracts import (
    AvailabilityRecord,
    AvailabilityState,
    FailureRecord,
    FailureType,
    WorkerDescriptor,
)

if TYPE_CHECKING:
    from .store import WorkerRoutingStore


_FAILURE_AVAILABILITY = {
    FailureType.RATE_LIMITED: AvailabilityState.RATE_LIMITED,
    FailureType.QUOTA_EXHAUSTED: AvailabilityState.QUOTA_EXHAUSTED,
    FailureType.AUTH_FAILURE: AvailabilityState.AUTH_REQUIRED,
    FailureType.PROVIDER_UNAVAILABLE: AvailabilityState.PROVIDER_UNAVAILABLE,
    FailureType.TOOL_FAILURE: AvailabilityState.TOOL_UNAVAILABLE,
    FailureType.TIMEOUT: AvailabilityState.DEGRADED,
}


class WorkerRegistry:
    def __init__(self, *, store: WorkerRoutingStore | None = None) -> None:
        self._workers: dict[str, WorkerDescriptor] = {}
        self._lock = threading.RLock()
        self._store = store

    def register(self, worker: WorkerDescriptor) -> None:
        with self._lock:
            self._workers[worker.worker_id] = worker
            if self._store is not None:
                self._store.upsert_worker(worker)

    def register_many(self, workers: list[WorkerDescriptor] | tuple[WorkerDescriptor, ...]) -> None:
        for worker in workers:
            self.register(worker)

    def get(self, worker_id: str) -> WorkerDescriptor | None:
        with self._lock:
            return self._workers.get(worker_id)

    def snapshot(self, *, now_ms: int | None = None) -> tuple[WorkerDescriptor, ...]:
        now = now_ms if now_ms is not None else time.time_ns() // 1_000_000
        with self._lock:
            for worker_id, worker in tuple(self._workers.items()):
                availability = worker.availability
                if (
                    availability.retry_after_ms is not None
                    and availability.retry_after_ms <= now
                    and availability.state
                    in {
                        AvailabilityState.DEGRADED,
                        AvailabilityState.RATE_LIMITED,
                        AvailabilityState.QUOTA_EXHAUSTED,
                        AvailabilityState.PROVIDER_UNAVAILABLE,
                        AvailabilityState.TOOL_UNAVAILABLE,
                    }
                ):
                    recovered = worker.model_copy(
                        update={
                            "availability": AvailabilityRecord(
                                state=AvailabilityState.AVAILABLE,
                                reason="retry window elapsed",
                                observed_at_ms=now,
                            ),
                            "retry_after_ms": None,
                        }
                    )
                    self._workers[worker_id] = recovered
                    if self._store is not None:
                        self._store.upsert_worker(recovered)
            return tuple(sorted(self._workers.values(), key=lambda item: item.worker_id))

    def set_availability(self, worker_id: str, availability: AvailabilityRecord) -> WorkerDescriptor:
        with self._lock:
            current = self._workers[worker_id]
            updated = current.model_copy(
                update={
                    "availability": availability,
                    "last_health_check_ms": availability.observed_at_ms,
                    "retry_after_ms": availability.retry_after_ms,
                }
            )
            self._workers[worker_id] = updated
            if self._store is not None:
                self._store.upsert_worker(updated)
            return updated

    def record_failure(self, worker_id: str, failure: FailureRecord) -> WorkerDescriptor:
        current = self.get(worker_id)
        if current is None:
            raise KeyError(worker_id)
        state = _FAILURE_AVAILABILITY.get(failure.failure_type, current.availability.state)
        availability = AvailabilityRecord(
            state=state,
            reason=failure.reason,
            observed_at_ms=failure.observed_at_ms,
            retry_after_ms=failure.retry_after_ms,
        )
        with self._lock:
            updated = current.model_copy(
                update={
                    "availability": availability,
                    "last_failure": failure.failure_type,
                    "last_health_check_ms": failure.observed_at_ms,
                    "retry_after_ms": failure.retry_after_ms,
                }
            )
            self._workers[worker_id] = updated
            if self._store is not None:
                self._store.upsert_worker(updated)
            return updated

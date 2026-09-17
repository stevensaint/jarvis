"""Durable contracts for Julia lifecycle, nodes, and restart recovery."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def now_ms() -> int:
    return time.time_ns() // 1_000_000


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RuntimeState(StrEnum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"


class NodeAvailability(StrEnum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    BUSY = "BUSY"
    PAUSED = "PAUSED"
    DRAINING = "DRAINING"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


ELIGIBLE_NODE_STATES = frozenset(
    {NodeAvailability.ONLINE, NodeAvailability.DEGRADED}
)


class ExecutionState(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class SideEffectState(StrEnum):
    NONE = "NONE"
    IDEMPOTENT = "IDEMPOTENT"
    COMMITTED = "COMMITTED"
    UNKNOWN = "UNKNOWN"


class RecoveryDisposition(StrEnum):
    RESUME = "RESUME"
    RETRY = "RETRY"
    REPLAN = "REPLAN"
    VERIFY = "VERIFY"
    AWAIT_APPROVAL = "AWAIT_APPROVAL"
    MANUAL_RECONCILIATION = "MANUAL_RECONCILIATION"
    CANCEL = "CANCEL"


class NodeDescriptor(_FrozenModel):
    node_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    architecture: str = Field(min_length=1)
    hardware_profile: str = "unknown"
    runtime_version: str = "unknown"
    capabilities: frozenset[str] = frozenset()
    tools: frozenset[str] = frozenset()
    execution_modes: frozenset[str] = frozenset()
    authorization_scope: frozenset[str] = frozenset()
    availability_state: NodeAvailability = NodeAvailability.UNKNOWN
    last_seen_ms: int = Field(default_factory=now_ms)
    started_at_ms: int | None = None
    current_load: float = Field(default=0.0, ge=0.0, le=1.0)
    local_worker_inventory: tuple[str, ...] = ()
    storage_scope: frozenset[str] = frozenset()
    network_scope: frozenset[str] = frozenset()
    is_primary: bool = False


class RuntimeSnapshot(_FrozenModel):
    state: RuntimeState
    desired_state: RuntimeState
    primary_node_id: str | None = None
    started_at_ms: int | None = None
    updated_at_ms: int = Field(default_factory=now_ms)
    heartbeat_at_ms: int | None = None
    pid: int | None = None
    detail: str = ""


class ExecutionAttempt(_FrozenModel):
    attempt_id: str
    idempotency_key: str = Field(min_length=1)
    objective_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    iteration: int = Field(default=0, ge=0)
    node_id: str | None = None
    worker_id: str | None = None
    state: ExecutionState = ExecutionState.PLANNED
    side_effect_state: SideEffectState = SideEffectState.NONE
    authorization: dict[str, Any] = Field(default_factory=dict)
    resumable: bool = False
    retry_safe: bool = False
    created_at_ms: int = Field(default_factory=now_ms)
    updated_at_ms: int = Field(default_factory=now_ms)
    detail: str = ""


class RecoveryRecord(_FrozenModel):
    recovery_id: str
    attempt_id: str
    objective_id: str
    task_id: str
    disposition: RecoveryDisposition
    reason: str
    authorization: dict[str, Any] = Field(default_factory=dict)
    created_at_ms: int = Field(default_factory=now_ms)

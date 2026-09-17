"""Stable contracts for Julia's provider-neutral worker routing layer.

These values cross persistence and the diagnostics API. Keep the matching SQL
checks and ``frontend/src/types/workerRouting.ts`` in parity when editing them.
"""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AvailabilityState(StrEnum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


AVAILABILITY_STATES = tuple(state.value for state in AvailabilityState)
ELIGIBLE_AVAILABILITY_STATES = frozenset(
    {AvailabilityState.AVAILABLE, AvailabilityState.DEGRADED}
)


class FailureType(StrEnum):
    WORKER_FAILURE = "WORKER_FAILURE"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    AUTH_FAILURE = "AUTH_FAILURE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TOOL_FAILURE = "TOOL_FAILURE"
    TIMEOUT = "TIMEOUT"
    CONTEXT_LIMIT = "CONTEXT_LIMIT"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    POLICY_BLOCK = "POLICY_BLOCK"
    UNKNOWN = "UNKNOWN"


FAILURE_TYPES = tuple(kind.value for kind in FailureType)


class PrivacyClass(StrEnum):
    LOCAL_ONLY = "LOCAL_ONLY"
    REPOSITORY_ONLY = "REPOSITORY_ONLY"
    PRIVATE_CLOUD = "PRIVATE_CLOUD"
    PUBLIC_CLOUD = "PUBLIC_CLOUD"


PRIVACY_CLASSES = tuple(kind.value for kind in PrivacyClass)


class AuthorizationState(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    UNAUTHORIZED = "UNAUTHORIZED"
    DISABLED = "DISABLED"


AUTHORIZATION_STATES = tuple(state.value for state in AuthorizationState)


class AvailabilityRecord(_FrozenModel):
    state: AvailabilityState
    reason: str = ""
    observed_at_ms: int = Field(default_factory=lambda: time.time_ns() // 1_000_000)
    retry_after_ms: int | None = None


class HistoricalMetrics(_FrozenModel):
    attempts: int = Field(default=0, ge=0)
    successes: int = Field(default=0, ge=0)
    critic_acceptances: int = Field(default=0, ge=0)
    human_corrections: int = Field(default=0, ge=0)
    average_cost_usd: float = Field(default=0.0, ge=0.0)
    average_latency_ms: float = Field(default=0.0, ge=0.0)

    @property
    def success_rate(self) -> float | None:
        return self.successes / self.attempts if self.attempts else None


class WorkerDescriptor(_FrozenModel):
    worker_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = ""
    worker_class: str = Field(min_length=1)
    node_id: str | None = None
    capabilities: frozenset[str] = frozenset()
    tools: frozenset[str] = frozenset()
    execution_modes: frozenset[str] = frozenset()
    authorization_state: AuthorizationState = AuthorizationState.AUTHORIZED
    availability: AvailabilityRecord
    privacy_class: PrivacyClass = PrivacyClass.PRIVATE_CLOUD
    context_capacity: int = Field(default=0, ge=0)
    expected_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    capability_quality: dict[str, float] = Field(default_factory=dict)
    expected_cost_usd: float = Field(default=0.0, ge=0.0)
    expected_latency_ms: float = Field(default=0.0, ge=0.0)
    reliability: float = Field(default=0.5, ge=0.0, le=1.0)
    execution_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    historical_metrics: HistoricalMetrics = Field(default_factory=HistoricalMetrics)
    last_health_check_ms: int | None = None
    last_failure: FailureType | None = None
    retry_after_ms: int | None = None

    @field_validator("capability_quality")
    @classmethod
    def _quality_values_are_normalized(cls, value: dict[str, float]) -> dict[str, float]:
        if any(score < 0.0 or score > 1.0 for score in value.values()):
            raise ValueError("capability quality values must be between 0 and 1")
        return value


class AuthorizationContract(_FrozenModel):
    """Authority fixed when the objective is accepted.

    Empty provider/worker sets authorize nothing. This makes ambiguous legacy
    calls fail closed instead of turning credential discovery into permission.
    """

    authorized_worker_ids: frozenset[str] = frozenset()
    authorized_providers: frozenset[str] = frozenset()
    authorized_node_ids: frozenset[str] = frozenset()
    allowed_tools: frozenset[str] = frozenset()
    allowed_execution_modes: frozenset[str] = frozenset()
    allowed_privacy_classes: frozenset[PrivacyClass] = frozenset()

    def authorizes(self, worker: WorkerDescriptor) -> bool:
        return bool(
            worker.worker_id in self.authorized_worker_ids
            or worker.provider in self.authorized_providers
        )


class TaskProfile(_FrozenModel):
    objective_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    task_category: str = Field(min_length=1)
    objective: str = Field(min_length=1, max_length=8_000)
    required_capabilities: frozenset[str] = frozenset()
    required_tools: frozenset[str] = frozenset()
    required_execution_modes: frozenset[str] = frozenset()
    privacy: PrivacyClass = PrivacyClass.PRIVATE_CLOUD
    minimum_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_context_tokens: int = Field(default=0, ge=0)
    cost_preference: str = "balanced"
    latency_preference: str = "normal"
    authorization: AuthorizationContract
    excluded_worker_ids: frozenset[str] = frozenset()


class RoutingPolicy(_FrozenModel):
    quality_weight: float = Field(default=0.34, ge=0.0)
    success_weight: float = Field(default=0.24, ge=0.0)
    cost_weight: float = Field(default=0.12, ge=0.0)
    latency_weight: float = Field(default=0.10, ge=0.0)
    reliability_weight: float = Field(default=0.10, ge=0.0)
    context_weight: float = Field(default=0.05, ge=0.0)
    risk_weight: float = Field(default=0.05, ge=0.0)
    reference_cost_usd: float = Field(default=1.0, gt=0.0)
    reference_latency_ms: float = Field(default=60_000.0, gt=0.0)


class CandidateEvaluation(_FrozenModel):
    worker_id: str
    eligible: bool
    rejection_reasons: tuple[str, ...] = ()
    score: float | None = None
    score_components: dict[str, float] = Field(default_factory=dict)


class RoutingDecision(_FrozenModel):
    decision_id: str
    objective_id: str
    task_id: str
    task_category: str
    task_profile: TaskProfile
    candidates: tuple[CandidateEvaluation, ...]
    selected_worker_id: str | None
    selected_provider: str | None
    selected_model: str | None
    selected_node_id: str | None = None
    created_at_ms: int = Field(default_factory=lambda: time.time_ns() // 1_000_000)
    reason: str


class FailureRecord(_FrozenModel):
    failure_type: FailureType
    reason: str
    observed_at_ms: int = Field(default_factory=lambda: time.time_ns() // 1_000_000)
    retry_after_ms: int | None = None


class OutcomeRecord(_FrozenModel):
    objective_id: str
    task_id: str
    task_category: str
    worker_id: str
    provider: str
    model: str
    duration_ms: int = Field(ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    actual_cost_usd: float = Field(default=0.0, ge=0.0)
    attempts: int = Field(default=1, ge=1)
    worker_result: str
    critic_result: str | None = None
    verification_result: str | None = None
    failure_type: FailureType | None = None
    human_correction: bool = False
    final_status: str
    recorded_at_ms: int = Field(default_factory=lambda: time.time_ns() // 1_000_000)


def jsonable(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json")

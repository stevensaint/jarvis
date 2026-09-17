"""Provider-neutral worker registry and dynamic routing engine."""

from .contracts import (
    AuthorizationContract,
    AvailabilityRecord,
    AvailabilityState,
    CandidateEvaluation,
    FailureRecord,
    FailureType,
    OutcomeRecord,
    PrivacyClass,
    RoutingDecision,
    RoutingPolicy,
    TaskProfile,
    WorkerDescriptor,
)
from .registry import WorkerRegistry
from .router import DynamicWorkerRouter, NoEligibleWorkerError

__all__ = [
    "AuthorizationContract",
    "AvailabilityRecord",
    "AvailabilityState",
    "CandidateEvaluation",
    "DynamicWorkerRouter",
    "FailureRecord",
    "FailureType",
    "NoEligibleWorkerError",
    "OutcomeRecord",
    "PrivacyClass",
    "RoutingDecision",
    "RoutingPolicy",
    "TaskProfile",
    "WorkerDescriptor",
    "WorkerRegistry",
]

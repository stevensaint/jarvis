"""Hard-gated utility routing and authority-preserving replanning."""

from __future__ import annotations

from uuid import uuid4

from .contracts import (
    CandidateEvaluation,
    ELIGIBLE_AVAILABILITY_STATES,
    FailureRecord,
    RoutingDecision,
    RoutingPolicy,
    TaskProfile,
    WorkerDescriptor,
)
from .registry import WorkerRegistry


class NoEligibleWorkerError(RuntimeError):
    def __init__(self, decision: RoutingDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


def _quality_for(worker: WorkerDescriptor, task: TaskProfile) -> float:
    if not task.required_capabilities:
        return worker.expected_quality
    values = [
        worker.capability_quality.get(capability, worker.expected_quality)
        for capability in task.required_capabilities
    ]
    return min(values)


def evaluate_eligibility(worker: WorkerDescriptor, task: TaskProfile) -> tuple[str, ...]:
    reasons: list[str] = []
    if worker.worker_id in task.excluded_worker_ids:
        reasons.append("worker_excluded_after_failure")
    if worker.authorization_state.value != "AUTHORIZED" or not task.authorization.authorizes(worker):
        reasons.append("not_authorized")
    if worker.availability.state not in ELIGIBLE_AVAILABILITY_STATES:
        reasons.append(f"availability:{worker.availability.state.value}")
    missing_caps = sorted(task.required_capabilities - worker.capabilities)
    if missing_caps:
        reasons.append("missing_capabilities:" + ",".join(missing_caps))
    missing_tools = sorted(task.required_tools - worker.tools)
    if missing_tools:
        reasons.append("missing_tools:" + ",".join(missing_tools))
    if worker.privacy_class not in task.authorization.allowed_privacy_classes:
        reasons.append(f"privacy_not_allowed:{worker.privacy_class.value}")
    missing_modes = sorted(task.required_execution_modes - worker.execution_modes)
    if missing_modes:
        reasons.append("execution_scope:" + ",".join(missing_modes))
    unauthorized_modes = sorted(
        task.required_execution_modes - task.authorization.allowed_execution_modes
    )
    if unauthorized_modes:
        reasons.append("execution_scope_not_authorized:" + ",".join(unauthorized_modes))
    unauthorized_tools = sorted(task.required_tools - task.authorization.allowed_tools)
    if unauthorized_tools:
        reasons.append("tools_not_authorized:" + ",".join(unauthorized_tools))
    quality = _quality_for(worker, task)
    if quality < task.minimum_quality:
        reasons.append(f"quality_below_threshold:{quality:.3f}<{task.minimum_quality:.3f}")
    if task.estimated_context_tokens > worker.context_capacity:
        reasons.append(
            f"context_limit:{task.estimated_context_tokens}>{worker.context_capacity}"
        )
    return tuple(reasons)


def score_worker(
    worker: WorkerDescriptor,
    task: TaskProfile,
    policy: RoutingPolicy,
) -> tuple[float, dict[str, float]]:
    quality = _quality_for(worker, task)
    historical_success = worker.historical_metrics.success_rate
    expected_success = (
        worker.reliability
        if historical_success is None
        else 0.6 * historical_success + 0.4 * worker.reliability
    )
    cost_penalty = min(worker.expected_cost_usd / policy.reference_cost_usd, 1.0)
    latency_penalty = min(worker.expected_latency_ms / policy.reference_latency_ms, 1.0)
    context_fit = (
        1.0
        if task.estimated_context_tokens <= 0
        else min(worker.context_capacity / task.estimated_context_tokens, 2.0) / 2.0
    )
    components = {
        "quality": policy.quality_weight * quality,
        "expected_success": policy.success_weight * expected_success,
        "cost_penalty": -policy.cost_weight * cost_penalty,
        "latency_penalty": -policy.latency_weight * latency_penalty,
        "reliability": policy.reliability_weight * worker.reliability,
        "context_fit": policy.context_weight * context_fit,
        "risk_penalty": -policy.risk_weight * worker.execution_risk,
    }
    return sum(components.values()), components


class DynamicWorkerRouter:
    def __init__(
        self,
        registry: WorkerRegistry,
        *,
        policy: RoutingPolicy | None = None,
        store: object | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or RoutingPolicy()
        self.store = store

    def route(self, task: TaskProfile, *, require_selection: bool = True) -> RoutingDecision:
        evaluations: list[CandidateEvaluation] = []
        eligible: list[tuple[float, WorkerDescriptor, dict[str, float]]] = []
        for worker in self.registry.snapshot():
            reasons = evaluate_eligibility(worker, task)
            if reasons:
                evaluations.append(
                    CandidateEvaluation(
                        worker_id=worker.worker_id,
                        eligible=False,
                        rejection_reasons=reasons,
                    )
                )
                continue
            score, components = score_worker(worker, task, self.policy)
            eligible.append((score, worker, components))
            evaluations.append(
                CandidateEvaluation(
                    worker_id=worker.worker_id,
                    eligible=True,
                    score=score,
                    score_components=components,
                )
            )

        selected: WorkerDescriptor | None = None
        if eligible:
            _score, selected, _components = max(
                eligible, key=lambda item: (item[0], item[1].reliability, item[1].worker_id)
            )
        reason = (
            f"selected {selected.worker_id} from {len(eligible)} eligible worker(s)"
            if selected is not None
            else "no worker passed all authorization and eligibility gates"
        )
        decision = RoutingDecision(
            decision_id=str(uuid4()),
            objective_id=task.objective_id,
            task_id=task.task_id,
            task_category=task.task_category,
            task_profile=task,
            candidates=tuple(evaluations),
            selected_worker_id=selected.worker_id if selected else None,
            selected_provider=selected.provider if selected else None,
            selected_model=selected.model if selected else None,
            reason=reason,
        )
        saver = getattr(self.store, "save_decision", None)
        if callable(saver):
            saver(decision)
        if selected is None and require_selection:
            raise NoEligibleWorkerError(decision)
        return decision

    def replan_after_failure(
        self,
        task: TaskProfile,
        *,
        failed_worker_id: str,
        failure: FailureRecord,
        require_selection: bool = True,
    ) -> RoutingDecision:
        self.registry.record_failure(failed_worker_id, failure)
        preserved = task.model_copy(
            update={"excluded_worker_ids": task.excluded_worker_ids | {failed_worker_id}}
        )
        return self.route(preserved, require_selection=require_selection)


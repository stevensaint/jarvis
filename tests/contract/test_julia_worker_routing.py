"""Sprint 1 contract for Julia's provider-neutral worker routing engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.julia.routing import (
    AuthorizationContract,
    AvailabilityRecord,
    AvailabilityState,
    DynamicWorkerRouter,
    FailureRecord,
    FailureType,
    NoEligibleWorkerError,
    OutcomeRecord,
    PrivacyClass,
    TaskProfile,
    WorkerDescriptor,
    WorkerRegistry,
)
from jarvis.julia.routing.contracts import (
    AUTHORIZATION_STATES,
    AVAILABILITY_STATES,
    FAILURE_TYPES,
    PRIVACY_CLASSES,
)
from jarvis.julia.routing.profiler import profile_task
from jarvis.julia.routing.store import WorkerRoutingStore


def _worker(
    worker_id: str,
    provider: str,
    *,
    capabilities: frozenset[str] = frozenset({"reasoning", "coding", "structured_output"}),
    tools: frozenset[str] = frozenset({"filesystem", "shell"}),
    modes: frozenset[str] = frozenset({"repository"}),
    state: AvailabilityState = AvailabilityState.AVAILABLE,
    quality: float = 0.85,
    cost: float = 0.20,
    latency: float = 5_000,
    reliability: float = 0.90,
    privacy: PrivacyClass = PrivacyClass.PRIVATE_CLOUD,
    worker_class: str = "api_agent",
) -> WorkerDescriptor:
    return WorkerDescriptor(
        worker_id=worker_id,
        provider=provider,
        model=f"{provider}-model",
        worker_class=worker_class,
        capabilities=capabilities,
        tools=tools,
        execution_modes=modes,
        availability=AvailabilityRecord(state=state),
        privacy_class=privacy,
        context_capacity=100_000,
        expected_quality=quality,
        capability_quality={capability: quality for capability in capabilities},
        expected_cost_usd=cost,
        expected_latency_ms=latency,
        reliability=reliability,
    )


def _profile(
    *providers: str,
    required_capabilities: frozenset[str] = frozenset({"coding"}),
    required_tools: frozenset[str] = frozenset({"filesystem", "shell"}),
    minimum_quality: float = 0.70,
) -> TaskProfile:
    return TaskProfile(
        objective_id="objective-1",
        task_id="task-1",
        task_category="coding",
        objective="Implement and test the repository change.",
        required_capabilities=required_capabilities,
        required_tools=required_tools,
        required_execution_modes=frozenset({"repository"}),
        minimum_quality=minimum_quality,
        estimated_context_tokens=2_000,
        authorization=AuthorizationContract(
            authorized_providers=frozenset(providers),
            allowed_tools=frozenset({"filesystem", "shell"}),
            allowed_execution_modes=frozenset({"repository"}),
            allowed_privacy_classes=frozenset(
                {PrivacyClass.LOCAL_ONLY, PrivacyClass.PRIVATE_CLOUD}
            ),
        ),
    )


def test_a_registry_supports_three_heterogeneous_workers() -> None:
    registry = WorkerRegistry()
    registry.register_many(
        (
            _worker("codex-subscription", "openai-codex", worker_class="codex_direct"),
            _worker("claude-subscription", "claude-api", worker_class="claude_direct"),
            _worker(
                "local-control",
                "ollama",
                worker_class="api_agent",
                privacy=PrivacyClass.LOCAL_ONLY,
                cost=0.0,
            ),
        )
    )
    assert len(registry.snapshot()) == 3
    assert {worker.worker_class for worker in registry.snapshot()} == {
        "codex_direct",
        "claude_direct",
        "api_agent",
    }


def test_b_capability_gate_excludes_before_scoring() -> None:
    registry = WorkerRegistry()
    registry.register(_worker("research-only", "provider-a", capabilities=frozenset({"research"})))
    decision = DynamicWorkerRouter(registry).route(
        _profile("provider-a"), require_selection=False
    )
    candidate = decision.candidates[0]
    assert candidate.eligible is False
    assert candidate.score is None
    assert "missing_capabilities:coding" in candidate.rejection_reasons


def test_c_unauthorized_optimal_worker_is_excluded() -> None:
    registry = WorkerRegistry()
    registry.register_many(
        (
            _worker("unauthorized-best", "provider-x", quality=0.99, cost=0.0),
            _worker("authorized", "provider-a", quality=0.82, cost=0.30),
        )
    )
    decision = DynamicWorkerRouter(registry).route(_profile("provider-a"))
    assert decision.selected_worker_id == "authorized"
    rejected = next(item for item in decision.candidates if item.worker_id == "unauthorized-best")
    assert "not_authorized" in rejected.rejection_reasons


def test_d_quota_exhausted_worker_is_excluded() -> None:
    registry = WorkerRegistry()
    registry.register(_worker("codex", "openai-codex", state=AvailabilityState.QUOTA_EXHAUSTED))
    decision = DynamicWorkerRouter(registry).route(
        _profile("openai-codex"), require_selection=False
    )
    assert decision.selected_worker_id is None
    assert "availability:QUOTA_EXHAUSTED" in decision.candidates[0].rejection_reasons


def test_e_quality_threshold_beats_cheap_inadequate_worker() -> None:
    registry = WorkerRegistry()
    registry.register_many(
        (
            _worker("cheap", "provider-a", quality=0.55, cost=0.0),
            _worker("qualified", "provider-b", quality=0.85, cost=0.40),
        )
    )
    decision = DynamicWorkerRouter(registry).route(_profile("provider-a", "provider-b"))
    assert decision.selected_worker_id == "qualified"
    cheap = next(item for item in decision.candidates if item.worker_id == "cheap")
    assert any(reason.startswith("quality_below_threshold") for reason in cheap.rejection_reasons)


def test_f_cost_differentiates_similarly_qualified_workers() -> None:
    registry = WorkerRegistry()
    registry.register_many(
        (
            _worker("expensive", "provider-a", cost=0.80),
            _worker("efficient", "provider-b", cost=0.10),
        )
    )
    decision = DynamicWorkerRouter(registry).route(_profile("provider-a", "provider-b"))
    assert decision.selected_worker_id == "efficient"


def test_g_required_codex_quota_scenario_persists_and_replans(tmp_path: Path) -> None:
    store = WorkerRoutingStore(tmp_path / "routing.db")
    store.open()
    registry = WorkerRegistry(store=store)
    registry.register_many(
        (
            _worker("codex", "openai-codex", quality=0.92),
            _worker("alternative", "provider-b", quality=0.82),
        )
    )
    router = DynamicWorkerRouter(registry, store=store)
    task = _profile("openai-codex", "provider-b")
    first = router.route(task)
    assert first.selected_worker_id == "codex"

    second = router.replan_after_failure(
        task,
        failed_worker_id="codex",
        failure=FailureRecord(
            failure_type=FailureType.QUOTA_EXHAUSTED,
            reason="usage window exhausted",
            retry_after_ms=9_999_999_999_999,
        ),
    )
    assert second.selected_worker_id == "alternative"
    assert second.task_profile.objective == task.objective
    codex = registry.get("codex")
    assert codex is not None
    assert codex.availability.state is AvailabilityState.QUOTA_EXHAUSTED
    assert len(store.decisions_for_task(task.task_id)) == 2
    persisted = {worker.worker_id: worker for worker in store.list_workers()}
    assert persisted["codex"].availability.state is AvailabilityState.QUOTA_EXHAUSTED


def test_h_fail_closed_without_authorized_alternative() -> None:
    registry = WorkerRegistry()
    registry.register_many(
        (
            _worker("codex", "openai-codex", quality=0.92),
            _worker("claude", "claude-api", quality=0.99),
        )
    )
    router = DynamicWorkerRouter(registry)
    task = _profile("openai-codex")
    with pytest.raises(NoEligibleWorkerError) as caught:
        router.replan_after_failure(
            task,
            failed_worker_id="codex",
            failure=FailureRecord(
                failure_type=FailureType.QUOTA_EXHAUSTED,
                reason="quota",
            ),
        )
    claude = next(item for item in caught.value.decision.candidates if item.worker_id == "claude")
    assert "not_authorized" in claude.rejection_reasons


def test_i_failure_cannot_expand_computer_use_authority() -> None:
    registry = WorkerRegistry()
    registry.register_many(
        (
            _worker("safe", "provider-a"),
            _worker(
                "gui",
                "provider-b",
                capabilities=frozenset({"coding", "computer_use"}),
                tools=frozenset({"computer_use"}),
                modes=frozenset({"computer_use"}),
                quality=0.99,
            ),
        )
    )
    task = _profile("provider-a", "provider-b")
    router = DynamicWorkerRouter(registry)
    first = router.route(task)
    assert first.selected_worker_id == "safe"
    with pytest.raises(NoEligibleWorkerError):
        router.replan_after_failure(
            task,
            failed_worker_id="safe",
            failure=FailureRecord(failure_type=FailureType.WORKER_FAILURE, reason="failed"),
        )


def test_j_explainability_roundtrips_from_store(tmp_path: Path) -> None:
    store = WorkerRoutingStore(tmp_path / "routing.db")
    store.open()
    registry = WorkerRegistry(store=store)
    registry.register(_worker("worker", "provider-a"))
    decision = DynamicWorkerRouter(registry, store=store).route(_profile("provider-a"))
    loaded = store.decisions_for_task("task-1")[0]
    assert loaded == decision
    assert loaded.candidates[0].score_components["quality"] > 0


def test_k_outcomes_produce_empirical_aggregates(tmp_path: Path) -> None:
    store = WorkerRoutingStore(tmp_path / "routing.db")
    store.open()
    for status, correction in (("success", False), ("failed", True)):
        store.record_outcome(
            OutcomeRecord(
                objective_id="objective-1",
                task_id=f"task-{status}",
                task_category="coding",
                worker_id="worker",
                provider="provider-a",
                model="model-a",
                duration_ms=1_000,
                actual_cost_usd=0.20,
                attempts=2,
                worker_result=status,
                critic_result="approve" if status == "success" else "reject",
                human_correction=correction,
                final_status=status,
            )
        )
    metric = store.aggregate_metrics()[0]
    assert metric["attempts"] == 2
    assert metric["success_rate"] == 0.5
    assert metric["critic_acceptance_rate"] == 0.5
    assert metric["human_correction_rate"] == 0.5


def test_l_local_worker_routes_simple_control_task_and_escalates_unsuitable() -> None:
    registry = WorkerRegistry()
    registry.register(
        _worker(
            "local-control",
            "ollama",
            capabilities=frozenset({"reasoning", "structured_output"}),
            tools=frozenset(),
            modes=frozenset(),
            privacy=PrivacyClass.LOCAL_ONLY,
            quality=0.78,
            cost=0.0,
        )
    )
    simple = TaskProfile(
        objective_id="objective-local",
        task_id="task-local",
        task_category="reasoning",
        objective="Choose a route from the supplied matrix.",
        required_capabilities=frozenset({"reasoning", "structured_output"}),
        minimum_quality=0.70,
        authorization=AuthorizationContract(
            authorized_providers=frozenset({"ollama"}),
            allowed_privacy_classes=frozenset({PrivacyClass.LOCAL_ONLY}),
        ),
    )
    router = DynamicWorkerRouter(registry)
    assert router.route(simple).selected_worker_id == "local-control"
    unsuitable = simple.model_copy(
        update={
            "task_id": "task-vision",
            "required_capabilities": frozenset({"vision"}),
        }
    )
    assert router.route(unsuitable, require_selection=False).selected_worker_id is None


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_router_contract_is_platform_neutral(platform: str) -> None:
    registry = WorkerRegistry()
    registry.register(_worker(f"worker-{platform}", "provider-a"))
    assert DynamicWorkerRouter(registry).route(_profile("provider-a")).selected_worker_id


def test_profiler_combines_structured_plan_fields_with_compact_prompt() -> None:
    authorization = _profile("provider-a").authorization
    profile = profile_task(
        objective_id="mission",
        task_id="step",
        objective="Implement the parser.",
        authorization=authorization,
        needs_repository=True,
    )
    assert profile.task_category == "coding"
    assert profile.required_tools == {"filesystem", "shell"}
    assert profile.required_execution_modes == {"repository"}
    assert len(profile.objective) < 8_001


def test_wire_enum_parity_across_python_sql_and_typescript() -> None:
    root = Path(__file__).resolve().parents[2]
    sql = (root / "jarvis/julia/routing/schema.sql").read_text(encoding="utf-8")
    ts = (root / "jarvis/ui/web/frontend/src/types/workerRouting.ts").read_text(
        encoding="utf-8"
    )
    for token in (*AVAILABILITY_STATES, *FAILURE_TYPES, *PRIVACY_CLASSES):
        assert f"'{token}'" in sql
        assert f"'{token}'" in ts
    for token in AUTHORIZATION_STATES:
        assert f"'{token}'" in sql

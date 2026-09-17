"""Sprint 2 contract tests for persistent Julia Core and node-aware routing."""

from __future__ import annotations

import plistlib
import sqlite3
from pathlib import Path

import pytest

from jarvis.julia.routing import (
    AuthorizationContract,
    AvailabilityRecord,
    AvailabilityState,
    DynamicWorkerRouter,
    PrivacyClass,
    TaskProfile,
    WorkerDescriptor,
    WorkerRegistry,
)
from jarvis.julia.runtime import (
    DuplicateExecutionError,
    ExecutionRecoveryManager,
    ExecutionState,
    JuliaRuntimeStore,
    JuliaRuntimeSupervisor,
    NodeAvailability,
    NodeDescriptor,
    NodeRegistry,
    RecoveryDisposition,
    RuntimePaths,
    RuntimeState,
    SideEffectState,
    load_or_create_node_identity,
)
from jarvis.julia.runtime.macos_service import MacOSRuntimeService
from jarvis.julia.runtime.portability import export_julia_state


def _node(node_id: str, state: NodeAvailability, *, primary: bool = True) -> NodeDescriptor:
    return NodeDescriptor(
        node_id=node_id,
        display_name="Replaceable test node",
        node_type="personal-computer",
        platform="test-os",
        architecture="arm64",
        capabilities=frozenset({"coding"}),
        tools=frozenset({"filesystem", "shell"}),
        execution_modes=frozenset({"repository"}),
        availability_state=state,
        is_primary=primary,
    )


def _worker(node_id: str) -> WorkerDescriptor:
    return WorkerDescriptor(
        worker_id="local-worker",
        provider="local",
        worker_class="api_agent",
        node_id=node_id,
        capabilities=frozenset({"coding"}),
        tools=frozenset({"filesystem", "shell"}),
        execution_modes=frozenset({"repository"}),
        availability=AvailabilityRecord(state=AvailabilityState.AVAILABLE),
        privacy_class=PrivacyClass.LOCAL_ONLY,
        context_capacity=32_000,
        expected_quality=0.8,
        capability_quality={"coding": 0.8},
    )


def _task(node_id: str) -> TaskProfile:
    return TaskProfile(
        objective_id="objective",
        task_id="task",
        task_category="coding",
        objective="Implement a safe local change",
        required_capabilities=frozenset({"coding"}),
        required_tools=frozenset({"filesystem", "shell"}),
        required_execution_modes=frozenset({"repository"}),
        privacy=PrivacyClass.LOCAL_ONLY,
        minimum_quality=0.7,
        authorization=AuthorizationContract(
            authorized_providers=frozenset({"local"}),
            authorized_node_ids=frozenset({node_id}),
            allowed_tools=frozenset({"filesystem", "shell"}),
            allowed_execution_modes=frozenset({"repository"}),
            allowed_privacy_classes=frozenset({PrivacyClass.LOCAL_ONLY}),
        ),
    )


def test_f_stable_node_identity_survives_process_restarts(tmp_path: Path) -> None:
    identity = tmp_path / "node" / "node_identity.json"
    first = load_or_create_node_identity(identity)
    second = load_or_create_node_identity(identity)
    assert first == second
    assert first.startswith("node-")
    assert not first.endswith("test-host")


def test_runtime_lifecycle_and_node_state_are_durable(tmp_path: Path) -> None:
    paths = RuntimePaths(core_root=tmp_path / "core", node_root=tmp_path / "node")
    first = JuliaRuntimeSupervisor(paths)
    started, recovered = first.start()
    assert started.state is RuntimeState.RUNNING
    assert recovered == ()
    node_id = first.node_id
    assert node_id is not None
    assert first.pause().state is RuntimeState.PAUSED
    assert first.nodes.get(node_id).availability_state is NodeAvailability.PAUSED  # type: ignore[union-attr]
    assert first.resume().state is RuntimeState.RUNNING
    first.stop()
    first.store.close()

    second = JuliaRuntimeSupervisor(paths)
    restarted, _ = second.start()
    assert second.node_id == node_id
    assert restarted.state is RuntimeState.RUNNING
    assert len(second.store.lifecycle_events()) >= 6
    second.stop()
    second.store.close()


def test_g_offline_node_blocks_otherwise_optimal_local_worker(tmp_path: Path) -> None:
    store = JuliaRuntimeStore(tmp_path / "runtime.db")
    store.open()
    nodes = NodeRegistry(store)
    nodes.register(_node("node-a", NodeAvailability.OFFLINE))
    workers = WorkerRegistry()
    workers.register(_worker("node-a"))
    router = DynamicWorkerRouter(workers, node_registry=nodes)

    blocked = router.route(_task("node-a"), require_selection=False)
    assert blocked.selected_worker_id is None
    assert "node_availability:OFFLINE" in blocked.candidates[0].rejection_reasons

    nodes.set_availability("node-a", NodeAvailability.ONLINE)
    selected = router.route(_task("node-a"))
    assert selected.selected_worker_id == "local-worker"
    assert selected.selected_node_id == "node-a"
    store.close()


def test_node_authorization_is_a_hard_gate(tmp_path: Path) -> None:
    store = JuliaRuntimeStore(tmp_path / "runtime.db")
    store.open()
    nodes = NodeRegistry(store)
    nodes.register(_node("node-a", NodeAvailability.ONLINE))
    workers = WorkerRegistry()
    workers.register(_worker("node-a"))
    task = _task("different-node")
    decision = DynamicWorkerRouter(workers, node_registry=nodes).route(
        task, require_selection=False
    )
    assert decision.selected_worker_id is None
    assert "node_not_authorized" in decision.candidates[0].rejection_reasons
    store.close()


def test_d_e_i_recovery_preserves_authority_and_prevents_duplicate_execution(
    tmp_path: Path,
) -> None:
    store = JuliaRuntimeStore(tmp_path / "runtime.db")
    store.open()
    recovery = ExecutionRecoveryManager(store)
    authority = {
        "authorized_providers": ["local"],
        "authorized_node_ids": ["node-a"],
        "allowed_tools": ["filesystem"],
    }
    attempt = recovery.begin(
        idempotency_key="objective:task:iteration-0",
        objective_id="objective",
        task_id="task",
        iteration=0,
        authorization=authority,
        node_id="node-a",
        worker_id="local-worker",
        resumable=False,
        retry_safe=False,
    )
    recovery.checkpoint(
        attempt.attempt_id,
        state=ExecutionState.RUNNING,
        side_effect_state=SideEffectState.UNKNOWN,
        detail="process disappeared after external command submission",
    )

    records = recovery.recover_interrupted()
    assert len(records) == 1
    assert records[0].disposition is RecoveryDisposition.MANUAL_RECONCILIATION
    assert records[0].authorization == authority
    with pytest.raises(DuplicateExecutionError):
        recovery.begin(
            idempotency_key="objective:task:iteration-0",
            objective_id="objective",
            task_id="task",
            iteration=0,
            authorization=authority,
            node_id="node-a",
            worker_id="local-worker",
            resumable=True,
            retry_safe=True,
        )
    store.close()


@pytest.mark.parametrize(
    ("state", "side_effect", "resumable", "retry_safe", "expected"),
    (
        (ExecutionState.AWAITING_VERIFICATION, SideEffectState.COMMITTED, False, False, RecoveryDisposition.VERIFY),
        (ExecutionState.AWAITING_APPROVAL, SideEffectState.NONE, False, False, RecoveryDisposition.AWAIT_APPROVAL),
        (ExecutionState.RUNNING, SideEffectState.NONE, True, False, RecoveryDisposition.RESUME),
        (ExecutionState.RUNNING, SideEffectState.IDEMPOTENT, False, True, RecoveryDisposition.RETRY),
    ),
)
def test_recovery_dispositions_are_explicit(
    state: ExecutionState,
    side_effect: SideEffectState,
    resumable: bool,
    retry_safe: bool,
    expected: RecoveryDisposition,
) -> None:
    from jarvis.julia.runtime import ExecutionAttempt

    attempt = ExecutionAttempt(
        attempt_id="attempt",
        idempotency_key="key",
        objective_id="objective",
        task_id="task",
        state=state,
        side_effect_state=side_effect,
        resumable=resumable,
        retry_safe=retry_safe,
    )
    disposition, _reason = ExecutionRecoveryManager.classify(attempt)
    assert disposition is expected


def test_l_primary_node_contract_has_no_macbook_dependency(tmp_path: Path) -> None:
    store = JuliaRuntimeStore(tmp_path / "runtime.db")
    store.open()
    registry = NodeRegistry(store)
    registry.register(_node("mobile", NodeAvailability.ONLINE, primary=True))
    registry.register(_node("always-on", NodeAvailability.ONLINE, primary=True))
    by_id = {node.node_id: node for node in registry.snapshot()}
    assert by_id["always-on"].is_primary is True
    assert by_id["mobile"].is_primary is False
    assert all("MacBook" not in node.display_name for node in by_id.values())
    store.close()


def test_l_portability_export_excludes_node_identity(tmp_path: Path) -> None:
    source = RuntimePaths(core_root=tmp_path / "core-a", node_root=tmp_path / "node-a")
    source.ensure()
    identity = load_or_create_node_identity(source.identity_file)
    runtime = JuliaRuntimeStore(source.runtime_db)
    runtime.open()
    runtime.save_runtime(
        runtime.runtime_snapshot().model_copy(
            update={"state": RuntimeState.PAUSED, "desired_state": RuntimeState.PAUSED}
        )
    )
    runtime.close()
    with sqlite3.connect(source.missions_db) as conn:
        conn.execute("CREATE TABLE objective(id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO objective VALUES ('objective-1')")

    destination = tmp_path / "core-b"
    written = export_julia_state(source, destination)
    assert destination / "missions.db" in written
    assert not (destination / "node_identity.json").exists()
    promoted = RuntimePaths(core_root=destination, node_root=tmp_path / "node-b")
    new_identity = load_or_create_node_identity(promoted.identity_file)
    assert new_identity != identity
    with sqlite3.connect(destination / "missions.db") as conn:
        assert conn.execute("SELECT id FROM objective").fetchone() == ("objective-1",)


def test_a_b_c_macos_service_plist_is_headless_and_restart_safe(tmp_path: Path) -> None:
    paths = RuntimePaths(core_root=tmp_path / "core", node_root=tmp_path / "node")
    service = MacOSRuntimeService(paths, working_dir=tmp_path)
    plist = service.plist()
    encoded = plistlib.dumps(plist)
    decoded = plistlib.loads(encoded)
    assert decoded["RunAtLoad"] is True
    assert decoded["KeepAlive"] == {"SuccessfulExit": False}
    assert decoded["ProcessType"] == "Background"
    assert "jarvis.julia.runtime.service" in decoded["ProgramArguments"]
    assert "jarvis.ui.web.launcher" not in decoded["ProgramArguments"]


def test_python_sql_typescript_node_state_parity() -> None:
    root = Path(__file__).resolve().parents[2]
    sql = (root / "jarvis/julia/runtime/schema.sql").read_text(encoding="utf-8")
    typescript = (
        root / "jarvis/ui/web/frontend/src/types/workerRouting.ts"
    ).read_text(encoding="utf-8")
    for state in NodeAvailability:
        assert f"'{state.value}'" in sql
        assert f"'{state.value}'" in typescript

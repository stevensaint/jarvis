"""Persistent Julia Core lifecycle supervisor."""

from __future__ import annotations

import os

from jarvis import __version__

from .contracts import NodeAvailability, RuntimeSnapshot, RuntimeState, now_ms
from .nodes import NodeRegistry, load_or_create_node_identity, local_node_descriptor
from .paths import RuntimePaths
from .recovery import ExecutionRecoveryManager
from .store import JuliaRuntimeStore


class JuliaRuntimeSupervisor:
    def __init__(self, paths: RuntimePaths) -> None:
        self.paths = paths
        self.store = JuliaRuntimeStore(paths.runtime_db)
        self.nodes = NodeRegistry(self.store)
        self.recovery = ExecutionRecoveryManager(self.store)
        self.node_id: str | None = None
        self.started_at_ms: int | None = None

    def _transition(self, state: RuntimeState, detail: str) -> RuntimeSnapshot:
        current = self.store.runtime_snapshot()
        snapshot = RuntimeSnapshot(
            state=state,
            desired_state=current.desired_state,
            primary_node_id=self.node_id or current.primary_node_id,
            started_at_ms=self.started_at_ms or current.started_at_ms,
            heartbeat_at_ms=now_ms(),
            pid=os.getpid(),
            detail=detail,
        )
        self.store.save_runtime(snapshot)
        return snapshot

    def start(self) -> tuple[RuntimeSnapshot, tuple[object, ...]]:
        self.paths.ensure()
        self.store.open()
        self.started_at_ms = now_ms()
        self.node_id = load_or_create_node_identity(self.paths.identity_file)
        self.store.save_runtime(
            RuntimeSnapshot(
                state=RuntimeState.STARTING,
                desired_state=RuntimeState.RUNNING,
                primary_node_id=self.node_id,
                started_at_ms=self.started_at_ms,
                heartbeat_at_ms=now_ms(),
                pid=os.getpid(),
                detail="persistent runtime process started",
            )
        )
        node = local_node_descriptor(
            node_id=self.node_id,
            runtime_version=__version__,
            is_primary=True,
            availability=NodeAvailability.UNKNOWN,
            started_at_ms=self.started_at_ms,
            storage_scope=frozenset({str(self.paths.core_root)}),
        )
        self.nodes.register(node)
        self._transition(RuntimeState.RECOVERING, "classifying interrupted execution")
        recovered = self.recovery.recover_interrupted()
        self.nodes.set_availability(self.node_id, NodeAvailability.ONLINE)
        snapshot = self._transition(
            RuntimeState.RUNNING,
            f"runtime healthy; recovery records={len(recovered)}",
        )
        return snapshot, recovered

    def heartbeat(self) -> RuntimeSnapshot:
        if self.node_id is None:
            raise RuntimeError("runtime has not started")
        current = self.store.runtime_snapshot()
        state = current.state
        node_state = (
            NodeAvailability.PAUSED if state is RuntimeState.PAUSED else NodeAvailability.ONLINE
        )
        self.nodes.set_availability(self.node_id, node_state)
        snapshot = current.model_copy(
            update={"heartbeat_at_ms": now_ms(), "updated_at_ms": now_ms(), "pid": os.getpid()}
        )
        self.store.save_runtime(snapshot, event=False)
        return snapshot

    def pause(self) -> RuntimeSnapshot:
        if self.node_id is None:
            raise RuntimeError("runtime has not started")
        self.nodes.set_availability(self.node_id, NodeAvailability.PAUSED)
        return self._transition(RuntimeState.PAUSED, "new execution paused by operator")

    def resume(self) -> RuntimeSnapshot:
        if self.node_id is None:
            raise RuntimeError("runtime has not started")
        self.nodes.set_availability(self.node_id, NodeAvailability.ONLINE)
        return self._transition(RuntimeState.RUNNING, "runtime resumed by operator")

    def stop(self) -> RuntimeSnapshot:
        if self.node_id is None:
            raise RuntimeError("runtime has not started")
        self._transition(RuntimeState.STOPPING, "clean shutdown requested")
        self.nodes.set_availability(self.node_id, NodeAvailability.OFFLINE)
        return self._transition(RuntimeState.STOPPED, "clean shutdown complete")

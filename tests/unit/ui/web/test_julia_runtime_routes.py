from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis.julia.runtime import JuliaRuntimeSupervisor, RuntimePaths
from jarvis.ui.web.julia_runtime_routes import router


def test_runtime_diagnostics_and_pause_resume(tmp_path: Path) -> None:
    supervisor = JuliaRuntimeSupervisor(
        RuntimePaths(core_root=tmp_path / "core", node_root=tmp_path / "node")
    )
    supervisor.start()
    app = FastAPI()
    app.state.julia_runtime_store = supervisor.store
    app.include_router(router)

    with TestClient(app) as client:
        status = client.get("/api/julia/runtime/status")
        assert status.status_code == 200
        assert status.json()["primary_node_id"] == supervisor.node_id
        assert status.json()["healthy"] is True

        paused = client.post("/api/julia/runtime/pause")
        assert paused.status_code == 200
        assert paused.json()["desired_state"] == "PAUSED"

        resumed = client.post("/api/julia/runtime/resume")
        assert resumed.status_code == 200
        assert resumed.json()["desired_state"] == "RUNNING"

        nodes = client.get("/api/julia/runtime/nodes")
        assert nodes.status_code == 200
        assert len(nodes.json()["nodes"]) == 1

    supervisor.stop()
    supervisor.store.close()

"""Diagnostics API coverage for Julia Sprint 1 worker routing."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

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
from jarvis.julia.routing.store import WorkerRoutingStore
from jarvis.ui.web.missions_routes import router as missions_router


def _app(tmp_path: Path) -> tuple[FastAPI, WorkerRoutingStore]:
    store = WorkerRoutingStore(tmp_path / "routing.db")
    store.open()
    registry = WorkerRegistry(store=store)
    registry.register(
        WorkerDescriptor(
            worker_id="local",
            provider="ollama",
            model="replaceable-model",
            worker_class="api_agent",
            capabilities=frozenset({"reasoning"}),
            availability=AvailabilityRecord(state=AvailabilityState.AVAILABLE),
            privacy_class=PrivacyClass.LOCAL_ONLY,
            context_capacity=8_000,
            expected_quality=0.8,
        )
    )
    router = DynamicWorkerRouter(registry, store=store)
    router.route(
        TaskProfile(
            objective_id="mission-1",
            task_id="step-1",
            task_category="reasoning",
            objective="Choose a route.",
            required_capabilities=frozenset({"reasoning"}),
            minimum_quality=0.7,
            authorization=AuthorizationContract(
                authorized_providers=frozenset({"ollama"}),
                allowed_privacy_classes=frozenset({PrivacyClass.LOCAL_ONLY}),
            ),
        )
    )
    app = FastAPI()
    app.include_router(missions_router)
    app.state.worker_registry = registry
    app.state.worker_routing_store = store
    return app, store


def test_routing_diagnostics_are_retrievable(tmp_path: Path) -> None:
    app, store = _app(tmp_path)
    try:
        with TestClient(app) as client:
            workers = client.get("/api/missions/routing/workers")
            decisions = client.get("/api/missions/routing/decisions/mission-1")
            metrics = client.get("/api/missions/routing/metrics")
        assert workers.status_code == 200
        assert workers.json()["workers"][0]["worker_id"] == "local"
        assert decisions.status_code == 200
        assert decisions.json()["decisions"][0]["selected_worker_id"] == "local"
        assert metrics.status_code == 200
        assert metrics.json() == {"metrics": []}
    finally:
        store.close()


def test_routing_diagnostics_fail_closed_when_unavailable() -> None:
    app = FastAPI()
    app.include_router(missions_router)
    with TestClient(app) as client:
        response = client.get("/api/missions/routing/workers")
    assert response.status_code == 503

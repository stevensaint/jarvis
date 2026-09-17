"""Local diagnostics and pause/resume controls for persistent Julia Core."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from jarvis.julia.runtime import RuntimeState
from jarvis.julia.runtime.contracts import now_ms

router = APIRouter(prefix="/api/julia/runtime", tags=["julia-runtime"])


def _store(request: Request):  # noqa: ANN202
    store = getattr(request.app.state, "julia_runtime_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Julia runtime ledger is not available")
    return store


def _payload(request: Request) -> dict[str, object]:
    store = _store(request)
    snapshot = store.runtime_snapshot()
    age = (
        max(0, now_ms() - snapshot.heartbeat_at_ms)
        if snapshot.heartbeat_at_ms is not None
        else None
    )
    return {
        "runtime": snapshot.model_dump(mode="json"),
        "healthy": snapshot.state in {RuntimeState.RUNNING, RuntimeState.PAUSED}
        and age is not None
        and age < 30_000,
        "heartbeat_age_ms": age,
        "primary_node_id": snapshot.primary_node_id,
        "nodes": [node.model_dump(mode="json") for node in store.nodes()],
        "recovering": [
            record.model_dump(mode="json") for record in store.recovery_records(limit=100)
        ],
    }


@router.get("/status")
def status(request: Request) -> dict[str, object]:
    return _payload(request)


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    payload = _payload(request)
    return {
        "healthy": payload["healthy"],
        "runtime": payload["runtime"],
        "primary_node_id": payload["primary_node_id"],
    }


@router.get("/nodes")
def nodes(request: Request) -> dict[str, object]:
    payload = _payload(request)
    return {"primary_node_id": payload["primary_node_id"], "nodes": payload["nodes"]}


@router.get("/recovery")
def recovery(request: Request) -> dict[str, object]:
    return {"records": _payload(request)["recovering"]}


@router.post("/pause")
def pause(request: Request) -> dict[str, object]:
    snapshot = _store(request).set_desired_state(
        RuntimeState.PAUSED, detail="pause requested through local API"
    )
    return snapshot.model_dump(mode="json")


@router.post("/resume")
def resume(request: Request) -> dict[str, object]:
    snapshot = _store(request).set_desired_state(
        RuntimeState.RUNNING, detail="resume requested through local API"
    )
    return snapshot.model_dump(mode="json")

"""Operator CLI for the persistent Julia runtime."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .contracts import RuntimeState, now_ms
from .macos_service import MacOSRuntimeService
from .paths import RuntimePaths
from .portability import export_julia_state
from .store import JuliaRuntimeStore


def _default_data_root() -> Path:
    try:
        from jarvis.core.config import load_config

        return Path(load_config().memory.data_dir)
    except Exception:
        return Path("data")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="julia-runtime")
    parser.add_argument("--core-root", type=Path, default=None)
    parser.add_argument("--node-root", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "start", "stop", "restart", "pause", "resume", "health", "nodes"):
        commands.add_parser(name)
    commands.add_parser("install")
    commands.add_parser("uninstall")
    export = commands.add_parser("export-state")
    export.add_argument("destination", type=Path)
    return parser


def _paths(args: argparse.Namespace) -> RuntimePaths:
    data_root = args.core_root or _default_data_root()
    return RuntimePaths.from_data_root(data_root, node_root=args.node_root)


def _store(paths: RuntimePaths) -> JuliaRuntimeStore:
    store = JuliaRuntimeStore(paths.runtime_db)
    store.open()
    return store


def _payload(paths: RuntimePaths) -> dict[str, object]:
    store = _store(paths)
    try:
        snapshot = store.runtime_snapshot()
        nodes = [node.model_dump(mode="json") for node in store.nodes()]
        recovery = [item.model_dump(mode="json") for item in store.recovery_records(limit=100)]
    finally:
        store.close()
    heartbeat_age_ms = (
        max(0, now_ms() - snapshot.heartbeat_at_ms)
        if snapshot.heartbeat_at_ms is not None
        else None
    )
    return {
        "runtime": snapshot.model_dump(mode="json"),
        "healthy": snapshot.state in {RuntimeState.RUNNING, RuntimeState.PAUSED}
        and heartbeat_age_ms is not None
        and heartbeat_age_ms < 30_000,
        "heartbeat_age_ms": heartbeat_age_ms,
        "primary_node_id": snapshot.primary_node_id,
        "nodes": nodes,
        "recovery": recovery,
    }


def _emit(payload: object, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = _paths(args)
    paths.ensure()
    service = MacOSRuntimeService(paths, working_dir=Path.cwd())
    if args.command == "install":
        _emit(asdict(service.install()), as_json=args.json)
        return 0
    if args.command == "uninstall":
        _emit(asdict(service.uninstall()), as_json=args.json)
        return 0
    if args.command == "start":
        store = _store(paths)
        try:
            store.set_desired_state(RuntimeState.RUNNING, detail="start requested by operator")
        finally:
            store.close()
        _emit(asdict(service.start()), as_json=args.json)
        return 0
    if args.command == "restart":
        store = _store(paths)
        try:
            store.set_desired_state(RuntimeState.RUNNING, detail="restart requested by operator")
        finally:
            store.close()
        _emit(asdict(service.restart()), as_json=args.json)
        return 0
    if args.command in {"stop", "pause", "resume"}:
        desired = {
            "stop": RuntimeState.STOPPED,
            "pause": RuntimeState.PAUSED,
            "resume": RuntimeState.RUNNING,
        }[args.command]
        store = _store(paths)
        try:
            snapshot = store.set_desired_state(
                desired, detail=f"{args.command} requested by operator"
            )
        finally:
            store.close()
        _emit(snapshot.model_dump(mode="json"), as_json=args.json)
        return 0
    if args.command == "export-state":
        written = export_julia_state(paths, args.destination)
        _emit({"written": [str(path) for path in written]}, as_json=args.json)
        return 0
    payload = _payload(paths)
    if args.command == "health":
        _emit(
            {
                "healthy": payload["healthy"],
                "runtime": payload["runtime"],
                "primary_node_id": payload["primary_node_id"],
            },
            as_json=args.json,
        )
        return 0 if payload["healthy"] else 1
    if args.command == "nodes":
        _emit(payload["nodes"], as_json=args.json)
        return 0
    _emit(payload, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

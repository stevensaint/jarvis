"""Long-lived headless Julia Core process."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import threading
from pathlib import Path

from .contracts import RuntimeState
from .paths import RuntimePaths
from .supervisor import JuliaRuntimeSupervisor

log = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="julia-runtime-service")
    parser.add_argument("--core-root", type=Path, required=True)
    parser.add_argument("--node-root", type=Path, required=True)
    parser.add_argument("--heartbeat-seconds", type=float, default=5.0)
    return parser


def run(paths: RuntimePaths, *, heartbeat_seconds: float = 5.0) -> int:
    stop_event = threading.Event()

    def _request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    supervisor = JuliaRuntimeSupervisor(paths)
    try:
        supervisor.start()
        paths.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
        while not stop_event.wait(max(0.2, heartbeat_seconds)):
            desired = supervisor.store.runtime_snapshot().desired_state
            current = supervisor.store.runtime_snapshot().state
            if desired is RuntimeState.STOPPED:
                break
            if desired is RuntimeState.PAUSED and current is not RuntimeState.PAUSED:
                supervisor.pause()
            elif desired is RuntimeState.RUNNING and current is RuntimeState.PAUSED:
                supervisor.resume()
            supervisor.heartbeat()
        supervisor.stop()
        return 0
    except Exception:
        log.exception("Julia runtime failed")
        try:
            supervisor._transition(RuntimeState.FAILED, "runtime terminated unexpectedly")
        except Exception:
            log.exception("Julia runtime could not persist FAILED state")
        return 1
    finally:
        paths.pid_file.unlink(missing_ok=True)
        supervisor.store.close()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    return run(
        RuntimePaths(core_root=args.core_root.resolve(), node_root=args.node_root.resolve()),
        heartbeat_seconds=args.heartbeat_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())

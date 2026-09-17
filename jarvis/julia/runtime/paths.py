"""Explicit Julia-wide and node-local storage boundaries."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    core_root: Path
    node_root: Path

    @classmethod
    def from_data_root(
        cls,
        data_root: Path,
        *,
        node_root: Path | None = None,
    ) -> RuntimePaths:
        core_override = os.environ.get("JULIA_STATE_ROOT")
        node_override = os.environ.get("JULIA_NODE_STATE_ROOT")
        core = Path(core_override).expanduser() if core_override else data_root
        local = (
            Path(node_override).expanduser()
            if node_override
            else node_root or core.with_name(f"{core.name}-node")
        )
        return cls(core_root=core.resolve(), node_root=local.resolve())

    @property
    def runtime_db(self) -> Path:
        return self.core_root / "julia_runtime.db"

    @property
    def missions_db(self) -> Path:
        return self.core_root / "missions.db"

    @property
    def routing_db(self) -> Path:
        return self.core_root / "julia_worker_routing.db"

    @property
    def identity_file(self) -> Path:
        return self.node_root / "node_identity.json"

    @property
    def pid_file(self) -> Path:
        return self.node_root / "runtime.pid"

    @property
    def log_dir(self) -> Path:
        return self.node_root / "logs"

    def ensure(self) -> None:
        self.core_root.mkdir(parents=True, exist_ok=True)
        self.node_root.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

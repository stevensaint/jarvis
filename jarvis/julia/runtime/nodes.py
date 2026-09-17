"""Stable node identity, local host description, and durable registry."""

from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from jarvis.core.process_utils import NO_WINDOW_CREATIONFLAGS

from .contracts import NodeAvailability, NodeDescriptor, now_ms
from .store import JuliaRuntimeStore


def load_or_create_node_identity(path: Path) -> str:
    """Return a stable random node id; hostname is never identity."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        node_id = str(payload.get("node_id", "")).strip()
        if node_id:
            return node_id
        raise ValueError(f"Node identity file has no node_id: {path}")
    node_id = f"node-{uuid4()}"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"node_id": node_id}, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    return node_id


def _command_text(argv: list[str]) -> str:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=3,
            creationflags=NO_WINDOW_CREATIONFLAGS,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _hardware_profile() -> str:
    if sys.platform == "darwin":
        chip = _command_text(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"])
        memory_raw = _command_text(["/usr/sbin/sysctl", "-n", "hw.memsize"])
        memory = ""
        if memory_raw.isdigit():
            memory = f"{round(int(memory_raw) / (1024**3))} GB"
        values = [value for value in (chip, memory) if value]
        if values:
            return " / ".join(values)
        # Hardened/sandboxed macOS processes may be denied sysctl reads. The
        # public hardware section is the fallback; parse only chip + memory so
        # serial numbers and platform identifiers never enter diagnostics.
        raw = _command_text(
            ["/usr/sbin/system_profiler", "SPHardwareDataType", "-json"]
        )
        try:
            hardware = json.loads(raw).get("SPHardwareDataType", [{}])[0]
            safe_values = [
                str(hardware.get(key, "")).strip()
                for key in ("chip_type", "physical_memory")
            ]
            safe_values = [value for value in safe_values if value]
            if safe_values:
                return " / ".join(safe_values)
        except (AttributeError, IndexError, TypeError, ValueError):
            pass
    return platform.platform()


def _display_name() -> str:
    override = os.environ.get("JULIA_NODE_DISPLAY_NAME")
    if override:
        return override
    if sys.platform == "darwin":
        computer_name = _command_text(["/usr/sbin/scutil", "--get", "ComputerName"])
        if computer_name:
            return computer_name
    return socket.gethostname() or "Julia node"


def local_node_descriptor(
    *,
    node_id: str,
    runtime_version: str,
    is_primary: bool,
    availability: NodeAvailability = NodeAvailability.ONLINE,
    started_at_ms: int | None = None,
    storage_scope: frozenset[str] = frozenset(),
) -> NodeDescriptor:
    return NodeDescriptor(
        node_id=node_id,
        display_name=_display_name(),
        node_type="personal-computer",
        platform=platform.system() or sys.platform,
        architecture=platform.machine() or "unknown",
        hardware_profile=_hardware_profile(),
        runtime_version=runtime_version,
        capabilities=frozenset(
            {"reasoning", "coding", "research", "local_execution", "structured_output"}
        ),
        tools=frozenset({"filesystem", "shell"}),
        execution_modes=frozenset({"repository", "local"}),
        authorization_scope=frozenset({"objective_contract"}),
        availability_state=availability,
        last_seen_ms=now_ms(),
        started_at_ms=started_at_ms,
        local_worker_inventory=(),
        storage_scope=storage_scope,
        network_scope=frozenset({"loopback", "authorized_provider_egress"}),
        is_primary=is_primary,
    )


class NodeRegistry:
    def __init__(self, store: JuliaRuntimeStore) -> None:
        self.store = store

    def register(self, node: NodeDescriptor) -> None:
        self.store.upsert_node(node)

    def get(self, node_id: str) -> NodeDescriptor | None:
        return self.store.node(node_id)

    def snapshot(self) -> tuple[NodeDescriptor, ...]:
        return self.store.nodes()

    def set_availability(
        self,
        node_id: str,
        state: NodeAvailability,
        *,
        current_load: float | None = None,
    ) -> NodeDescriptor:
        current = self.get(node_id)
        if current is None:
            raise KeyError(node_id)
        updated = current.model_copy(
            update={
                "availability_state": state,
                "last_seen_ms": now_ms(),
                "current_load": current.current_load if current_load is None else current_load,
            }
        )
        self.register(updated)
        return updated

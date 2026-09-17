"""Portable export of Julia-wide state without cloning node-local identity."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .paths import RuntimePaths

_PORTABLE_DATABASES = ("missions.db", "julia_worker_routing.db", "julia_runtime.db")


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_db:
        with sqlite3.connect(destination) as destination_db:
            source_db.backup(destination_db)


def export_julia_state(source: RuntimePaths, destination_core_root: Path) -> tuple[Path, ...]:
    """Copy Julia-owned databases through SQLite backup; never copy node identity."""
    destination = destination_core_root.resolve()
    if destination == source.core_root:
        raise ValueError("destination must differ from the active Julia state root")
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in _PORTABLE_DATABASES:
        src = source.core_root / name
        if not src.exists():
            continue
        dst = destination / name
        _backup_sqlite(src, dst)
        written.append(dst)
    manifest = destination / "julia-state-export.txt"
    manifest.write_text(
        "Julia-wide state export\nNode-local identity intentionally excluded.\n",
        encoding="utf-8",
    )
    written.append(manifest)
    return tuple(written)

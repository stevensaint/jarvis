"""Native macOS LaunchAgent integration for the headless Julia runtime."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from jarvis.core.process_utils import NO_WINDOW_CREATIONFLAGS

from .paths import RuntimePaths

LABEL = "com.julia.core"


@dataclass(frozen=True, slots=True)
class ServiceStatus:
    supported: bool
    installed: bool
    loaded: bool
    entry_path: str
    detail: str


class MacOSRuntimeService:
    def __init__(self, paths: RuntimePaths, *, working_dir: Path) -> None:
        self.paths = paths
        self.working_dir = working_dir.resolve()
        self.entry_path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    @property
    def domain(self) -> str:
        return f"gui/{os.getuid()}"

    @property
    def service_target(self) -> str:
        return f"{self.domain}/{LABEL}"

    def _launchctl(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/launchctl", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=15,
            creationflags=NO_WINDOW_CREATIONFLAGS,
        )

    def plist(self) -> dict[str, object]:
        self.paths.ensure()
        return {
            "Label": LABEL,
            "ProgramArguments": [
                sys.executable,
                "-m",
                "jarvis.julia.runtime.service",
                "--core-root",
                str(self.paths.core_root),
                "--node-root",
                str(self.paths.node_root),
            ],
            "WorkingDirectory": str(self.working_dir),
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ProcessType": "Background",
            "ThrottleInterval": 5,
            "StandardOutPath": str(self.paths.log_dir / "runtime.stdout.log"),
            "StandardErrorPath": str(self.paths.log_dir / "runtime.stderr.log"),
        }

    def status(self) -> ServiceStatus:
        supported = sys.platform == "darwin"
        installed = self.entry_path.exists()
        loaded = False
        detail = "LaunchAgent is not installed"
        if supported:
            result = self._launchctl("print", self.service_target)
            loaded = result.returncode == 0
            if loaded:
                detail = "LaunchAgent is loaded"
            elif installed:
                detail = "LaunchAgent is installed but not loaded"
        return ServiceStatus(
            supported=supported,
            installed=installed,
            loaded=loaded,
            entry_path=str(self.entry_path),
            detail=detail,
        )

    def install(self) -> ServiceStatus:
        if sys.platform != "darwin":
            raise RuntimeError("macOS LaunchAgent installation is only supported on macOS")
        self.entry_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.entry_path.with_suffix(".plist.tmp")
        try:
            with tmp.open("wb") as handle:
                plistlib.dump(self.plist(), handle)
            tmp.replace(self.entry_path)
        finally:
            tmp.unlink(missing_ok=True)
        current = self.status()
        if current.loaded:
            self._launchctl("bootout", self.service_target)
        loaded = self._launchctl("bootstrap", self.domain, str(self.entry_path))
        if loaded.returncode != 0:
            raise RuntimeError(
                "launchctl bootstrap failed: "
                + (loaded.stderr or loaded.stdout or "unknown error").strip()
            )
        return self.status()

    def start(self) -> ServiceStatus:
        status = self.status()
        if not status.installed:
            status = self.install()
        result = self._launchctl("kickstart", self.service_target)
        if result.returncode != 0:
            raise RuntimeError(
                "launchctl kickstart failed: "
                + (result.stderr or result.stdout or "unknown error").strip()
            )
        return self.status()

    def restart(self) -> ServiceStatus:
        status = self.status()
        if not status.installed:
            return self.install()
        result = self._launchctl("kickstart", "-k", self.service_target)
        if result.returncode != 0:
            raise RuntimeError(
                "launchctl restart failed: "
                + (result.stderr or result.stdout or "unknown error").strip()
            )
        return self.status()

    def uninstall(self) -> ServiceStatus:
        if sys.platform == "darwin":
            self._launchctl("bootout", self.service_target)
        self.entry_path.unlink(missing_ok=True)
        return self.status()

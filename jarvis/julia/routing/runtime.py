"""Adapters from the accepted mission workers into Julia's registry contract."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import (
    AuthorizationContract,
    AvailabilityRecord,
    AvailabilityState,
    PrivacyClass,
    WorkerDescriptor,
)
from .registry import WorkerRegistry


@dataclass(frozen=True, slots=True)
class WorkerAdapterSpec:
    provider: str
    worker_class: str
    default_model: str = ""
    local: bool = False
    expected_quality: float = 0.84
    expected_cost_usd: float = 0.25
    expected_latency_ms: float = 12_000.0
    reliability: float = 0.85

    @property
    def worker_id(self) -> str:
        return f"{self.provider}:{self.worker_class}"


# Adapters are data. The router itself contains no provider branches; adding a
# provider means registering another descriptor/factory adapter, not redesigning
# eligibility or scoring.
DEFAULT_WORKER_ADAPTERS: tuple[WorkerAdapterSpec, ...] = (
    WorkerAdapterSpec("openai-codex", "codex_direct", expected_cost_usd=0.0),
    WorkerAdapterSpec("chatgpt", "codex_direct", expected_cost_usd=0.0),
    WorkerAdapterSpec("claude-api", "claude_direct", expected_cost_usd=0.0),
    WorkerAdapterSpec("antigravity", "google_cli", expected_cost_usd=0.0),
    WorkerAdapterSpec("grok-build", "grok_build", expected_cost_usd=0.0),
    WorkerAdapterSpec("gemini", "gemini", expected_cost_usd=0.18),
    WorkerAdapterSpec("openai", "api_agent", expected_cost_usd=0.30),
    WorkerAdapterSpec("openrouter", "api_agent", expected_cost_usd=0.25),
    WorkerAdapterSpec("grok", "api_agent", expected_cost_usd=0.25),
    WorkerAdapterSpec("nvidia", "api_agent", expected_cost_usd=0.10),
    WorkerAdapterSpec("vertex", "api_agent", expected_cost_usd=0.25),
    WorkerAdapterSpec(
        "ollama",
        "api_agent",
        local=True,
        expected_quality=0.72,
        expected_cost_usd=0.0,
        expected_latency_ms=8_000.0,
    ),
    WorkerAdapterSpec(
        "local-openai",
        "api_agent",
        local=True,
        expected_quality=0.72,
        expected_cost_usd=0.0,
        expected_latency_ms=8_000.0,
    ),
)


def configured_authorized_providers(cfg: Any, primary: str | None) -> tuple[str, ...]:
    """Return only provider families the user explicitly configured for workers."""
    providers: list[str] = []
    worker_cfg = getattr(getattr(cfg, "brain", None), "worker", None)
    for value in (
        primary,
        getattr(worker_cfg, "fallback_provider", None),
        getattr(worker_cfg, "fallback_provider_2", None),
    ):
        normalized = str(value or "").strip().lower()
        if normalized and normalized not in providers:
            providers.append(normalized)
    return tuple(providers)


def authorization_for_step(
    providers: tuple[str, ...],
    *,
    needs_repository: bool,
    node_ids: tuple[str, ...] = (),
) -> AuthorizationContract:
    tools = {"filesystem", "shell"} if needs_repository else set()
    modes = {"repository"} if needs_repository else set()
    return AuthorizationContract(
        authorized_providers=frozenset(providers),
        authorized_node_ids=frozenset(node_ids),
        allowed_tools=frozenset(tools),
        allowed_execution_modes=frozenset(modes),
        allowed_privacy_classes=frozenset(
            {
                PrivacyClass.LOCAL_ONLY,
                PrivacyClass.REPOSITORY_ONLY,
                PrivacyClass.PRIVATE_CLOUD,
            }
        ),
    )


def _configured_model(cfg: Any, spec: WorkerAdapterSpec) -> str:
    worker_cfg = getattr(getattr(cfg, "brain", None), "worker", None)
    if worker_cfg is not None and getattr(worker_cfg, "provider", None) == spec.provider:
        model = getattr(worker_cfg, "model", None)
        if model:
            return str(model)
    providers = getattr(getattr(cfg, "brain", None), "providers", {}) or {}
    provider_cfg = providers.get(spec.provider)
    if provider_cfg is not None:
        model = getattr(provider_cfg, "deep_model", None) or getattr(provider_cfg, "model", None)
        if model:
            return str(model)
    return spec.default_model


def _provider_availability(provider: str) -> AvailabilityRecord:
    """Cheap local health projection. Never performs a network request."""
    now = time.time_ns() // 1_000_000
    try:
        if provider in {"openai-codex", "chatgpt"}:
            from jarvis.codex_auth_state import codex_needs_reauth
            from jarvis.codex_quota_state import codex_in_quota_cooldown
            from jarvis.missions.workers.codex_direct_worker import _codex_oauth_available

            if codex_needs_reauth() or not _codex_oauth_available():
                return AvailabilityRecord(
                    state=AvailabilityState.AUTH_REQUIRED,
                    reason="Codex login unavailable",
                    observed_at_ms=now,
                )
            if codex_in_quota_cooldown():
                return AvailabilityRecord(
                    state=AvailabilityState.QUOTA_EXHAUSTED,
                    reason="Codex quota cooldown active",
                    observed_at_ms=now,
                )
            return AvailabilityRecord(
                state=AvailabilityState.AVAILABLE,
                reason="Codex login available",
                observed_at_ms=now,
            )
        if provider == "claude-api":
            from jarvis.missions.init import _api_key_family_viable, _claude_cli_auth_viable
            from jarvis.missions.workers.claude_direct_worker import _resolve_claude_binary

            available = (
                _resolve_claude_binary() is not None and _claude_cli_auth_viable()
            ) or _api_key_family_viable("claude-api")
            return AvailabilityRecord(
                state=AvailabilityState.AVAILABLE if available else AvailabilityState.AUTH_REQUIRED,
                reason="Claude credential available" if available else "Claude credential unavailable",
                observed_at_ms=now,
            )
        if provider in {"gemini", "openai", "openrouter", "grok", "nvidia", "vertex", "ollama", "local-openai"}:
            from jarvis.missions.init import _api_key_family_viable

            available = _api_key_family_viable(provider)
            return AvailabilityRecord(
                state=AvailabilityState.AVAILABLE if available else AvailabilityState.AUTH_REQUIRED,
                reason="provider credential available" if available else "provider credential unavailable",
                observed_at_ms=now,
            )
    except Exception as exc:  # noqa: BLE001 - health evidence degrades explicitly
        return AvailabilityRecord(
            state=AvailabilityState.UNKNOWN,
            reason=f"health probe failed: {type(exc).__name__}",
            observed_at_ms=now,
        )
    return AvailabilityRecord(
        state=AvailabilityState.AVAILABLE,
        reason="legacy worker adapter has no cheap health probe",
        observed_at_ms=now,
    )


def descriptor_from_spec(
    spec: WorkerAdapterSpec,
    *,
    cfg: Any,
    availability: AvailabilityRecord | None = None,
    node_id: str | None = None,
) -> WorkerDescriptor:
    capabilities = {
        "reasoning",
        "coding",
        "research",
        "structured_output",
        "summarization",
        "long_context",
    }
    if spec.local:
        capabilities.add("local_execution")
    quality = spec.expected_quality
    return WorkerDescriptor(
        worker_id=spec.worker_id,
        provider=spec.provider,
        model=_configured_model(cfg, spec),
        worker_class=spec.worker_class,
        node_id=node_id,
        capabilities=frozenset(capabilities),
        tools=frozenset({"filesystem", "shell"}),
        execution_modes=frozenset({"repository"}),
        availability=availability or _provider_availability(spec.provider),
        privacy_class=PrivacyClass.LOCAL_ONLY if spec.local else PrivacyClass.PRIVATE_CLOUD,
        context_capacity=128_000,
        expected_quality=quality,
        capability_quality={capability: quality for capability in capabilities},
        expected_cost_usd=spec.expected_cost_usd,
        expected_latency_ms=spec.expected_latency_ms,
        reliability=spec.reliability,
        execution_risk=0.10 if spec.local else 0.20,
    )


def populate_runtime_registry(
    registry: WorkerRegistry,
    cfg: Any,
    *,
    node_id: str | None = None,
) -> None:
    registry.register_many(
        tuple(
            descriptor_from_spec(spec, cfg=cfg, node_id=node_id)
            for spec in DEFAULT_WORKER_ADAPTERS
        )
    )


def refresh_runtime_availability(registry: WorkerRegistry) -> None:
    for worker in registry.snapshot():
        registry.set_availability(worker.worker_id, _provider_availability(worker.provider))

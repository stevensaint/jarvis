# ADR-0036: Julia owns provider-neutral worker routing

**Status:** Accepted  
**Date:** 2026-09-17  
**Tier:** T3 contract change

## Context

The accepted mission foundation had capable worker implementations, isolation,
critic review, and durable objectives, but selection accumulated inside a
provider-specific factory. Availability was partly process-local and a fallback
could be chosen without one reconstructable eligibility decision.

Sprint 1 requires Julia to manage workers as replaceable resources while
preserving the Sprint 0.5 authorization boundary.

## Decision

Julia introduces one registry and routing contract under `jarvis/julia/routing`.
The existing mission workers remain execution adapters.

For every delegation attempt:

1. the mission step supplies a compact structured task profile;
2. the objective's immutable authorization contract supplies the only allowed
   providers, tools, privacy classes, and execution modes;
3. authorization, availability, capability, tool, privacy, scope, quality, and
   context gates run before scoring;
4. only eligible workers receive a configurable utility score;
5. the decision, every rejection, and score components are persisted;
6. classified failure updates worker availability and the next attempt asks the
   registry again without adding authority;
7. outcomes update durable aggregate and per-worker historical metrics.

The routing database is metadata-only and separate from `missions.db`; the
mission database remains the authority for objective lifecycle state.

## Data and API

`julia_worker_routing.db` contains registry snapshots, routing decisions, and
outcomes. The Missions API exposes secret-free registry, decision, and aggregate
metric views under `/api/missions/routing/*`. Availability, failure, privacy,
and authorization vocabularies have Python, SQL, and TypeScript parity guards.

## Failure semantics

`QUOTA_EXHAUSTED`, authentication failure, provider unavailability, tool
failure, and timeout update the failed registry entry. Replanning reuses the
original task profile and authorization contract and excludes the failed worker.
If no authorized eligible worker remains, routing raises a fail-closed outcome.

## Consequences and trade-offs

- Selection is explainable and provider-neutral; provider knowledge is confined
  to declarative worker adapters and cheap health probes.
- SQLite writes add a small synchronous metadata operation at delegation
  boundaries, never on the voice audio critical path.
- Static expected quality/cost/latency values bootstrap scoring. Empirical
  outcomes are collected, but Sprint 1 does not rewrite policy weights.
- Cheap local health probes do not perform network calls. A provider can become
  unavailable between selection and spawn; that is handled as a classified
  failure and replan.
- The existing worker implementations retain some legacy internal fallback
  logic for compatibility. The Julia authorization binding remains authoritative
  at the mission factory seam; future work can progressively remove redundant
  adapter-internal fallback branches.

## Revisit when

- statistically meaningful outcome volume exists for calibrated quality and
  success priors;
- routing metadata volume warrants retention/compaction;
- a provider supplies a push health signal rather than a local probe; or
- operators need a dedicated routing dashboard beyond the diagnostics API.


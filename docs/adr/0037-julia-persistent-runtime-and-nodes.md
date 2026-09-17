# ADR-0037: Julia persistent runtime and replaceable execution nodes

**Status:** Accepted
**Date:** 2026-09-17
**Tier:** T3 contract change

## Context

Sprint 1 can select an eligible intelligence worker, but the orchestration
process is still tied to an application launch and models no durable execution
host. Restarting a process must not erase objectives, widen authority, or
blindly repeat an action whose external effects are uncertain.

## Decision

Julia Core is a persistent, headless service with five durable layers:

```text
Julia-wide state root
├── missions.db                  objective/event authority
├── julia_worker_routing.db      worker decisions and outcomes
└── julia_runtime.db             lifecycle, nodes, attempts, recovery

Machine-local node-state root
├── node_identity.json           stable random node identity
├── runtime.pid                  current service process
└── logs/                        local lifecycle output
```

The two roots may coincide on the current MacBook, but they are separate
contracts and migration tooling copies only Julia-wide state.

The node registry is authoritative for node descriptors and availability.
Workers that require a node name their hosting `node_id`. Routing rejects such
a worker before scoring when the node is unknown, offline, paused, draining, or
otherwise unauthorized for the task.

The execution ledger records an immutable authorization snapshot and an
idempotency key before work begins. On recovery, interrupted attempts receive a
disposition (`RESUME`, `RETRY`, `REPLAN`, `VERIFY`, `AWAIT_APPROVAL`,
`MANUAL_RECONCILIATION`, or `CANCEL`). An ambiguous side-effect boundary always
maps to manual reconciliation and cannot be started again under the same key.

On macOS, a per-user LaunchAgent runs the headless Julia runtime in the signed-in
session. `RunAtLoad` starts it after login; `KeepAlive.SuccessfulExit=false`
restarts crashes but respects an intentional clean stop. The GUI is not the
runtime owner. Other platforms expose the same contracts while service-manager
adapters remain capability-gated.

## Lifecycle

```text
STOPPED -> STARTING -> RECOVERING -> RUNNING
                          |            |
                          v            v
                       DEGRADED      PAUSED
                          |            |
                          +-----> STOPPING -> STOPPED

Any unrecoverable startup error -> FAILED
```

Lifecycle transitions and health heartbeats are persisted. Pause prevents new
execution while keeping inspection and durable state available.

## Trade-offs

- SQLite remains the single-host durability mechanism. This avoids introducing
  a broker or distributed database before multi-node synchronization exists,
  but it means only one primary runtime may mutate Julia-wide state at a time.
- Polling a durable desired-state field keeps the operator interface simple and
  restart-safe. It is less immediate than a control socket, but avoids another
  authenticated local transport in this sprint.
- A separate execution ledger duplicates a small amount of mission metadata.
  The duplication is intentional: mission lifecycle and replay safety answer
  different questions and are joined by objective/task identifiers.

## Growth triggers

Revisit this design when Julia needs concurrent primary nodes, remote ingress,
automatic node-to-node failover, high-volume scheduling, or a shared state store.
Those changes require an explicit distributed consistency and trust model; they
must not be inferred from this single-primary contract.

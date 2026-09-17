# Julia persistent runtime operations

Sprint 2 runs Julia Core as a headless process that is independent of the
graphical application. On macOS it is managed by the per-user LaunchAgent
`com.julia.core`.

## State boundaries

- Julia-wide durable state: the configured data root, including `missions.db`,
  `julia_worker_routing.db`, and `julia_runtime.db`.
- Node-local state: the sibling `<data-root>-node` directory by default,
  including `node_identity.json`, the current PID, and service logs.
- Overrides: `JULIA_STATE_ROOT` and `JULIA_NODE_STATE_ROOT`.

Never copy `node_identity.json` when moving Julia-wide state to another Mac. A
new physical machine must receive a new identity and can then be promoted to
primary through the same node registry contract.

## Operator commands

```text
julia-runtime status
julia-runtime health
julia-runtime nodes
julia-runtime install
julia-runtime start
julia-runtime stop
julia-runtime restart
julia-runtime pause
julia-runtime resume
julia-runtime export-state /path/to/disposable-or-new-state-root
julia-runtime uninstall
```

`pause` leaves the service and durable state available for inspection while
making the local node ineligible for new work. `stop` requests a clean exit;
the LaunchAgent does not restart a successful intentional exit. `start` or
`restart` returns it to service.

The local API mirrors read-only status, health, nodes, and recovery records at
`/api/julia/runtime/*`, plus pause/resume requests. Diagnostics contain node
capabilities and scopes but no credentials.

## macOS behavior

The generated LaunchAgent:

- uses `RunAtLoad=true` for login startup;
- runs `jarvis.julia.runtime.service` directly with no window;
- uses `KeepAlive.SuccessfulExit=false`, so unexpected failure restarts but a
  clean operator stop is respected;
- writes stdout/stderr only to the node-local log directory;
- runs as the signed-in user, not a privileged LaunchDaemon.

The current source-checkout installation points to that checkout's virtual
environment. Moving or deleting the checkout requires reinstalling the service
from the new installation. Packaged builds should point the same contract at
their bundled interpreter.

## Recovery safety

Every execution attempt has a unique idempotency key and stores the original
authorization snapshot. Startup classification never adds providers, nodes,
tools, filesystem, network, privacy, GUI, deployment, or spending authority.

An attempt at an uncertain external side-effect boundary receives
`MANUAL_RECONCILIATION`; reusing its idempotency key is rejected. Committed but
unverified work receives `VERIFY`. Only explicitly resumable or retry-safe work
can receive `RESUME` or `RETRY`.

## Portability

`export-state` uses SQLite's backup API to create consistent copies of the
Julia-wide databases and deliberately excludes node identity and logs. Full
multi-node synchronization and automatic failover are not part of Sprint 2.

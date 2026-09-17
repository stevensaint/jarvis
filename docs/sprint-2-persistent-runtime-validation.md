# Sprint 2 Persistent Runtime Validation

Date: 2026-09-17

**Verdict: ACCEPT WITH CONDITIONS**

## Executive summary

Sprint 2 extends the accepted mission and worker-routing foundation with a
persistent Julia Core, durable lifecycle and recovery records, stable node
identity, a node registry, node-aware routing gates, and an installed per-user
macOS service. Julia now runs headlessly without an open Terminal or UI,
restarts after an unexpected process failure, retains the same logical node,
and exposes lifecycle, node, health, and recovery diagnostics through both a
CLI and local API.

All Sprint 2 code-level and live-process acceptance paths pass. A controlled
physical reboot completed on 2026-09-17, and Julia's LaunchAgent started the
persistent runtime afterward without manual development-environment startup.
The final verdict remains conditional because other inherited and Sprint 2
conditions remain. Sprint 3 was not started.

## Architecture

The runtime adds a node layer beneath Julia's accepted orchestration layer:

```text
macOS LaunchAgent
  -> Julia Core supervisor
     -> durable runtime/recovery store
     -> stable local node + Node Registry
     -> mission lifecycle
        -> node availability gate
        -> Sprint 1 worker authorization and eligibility gates
        -> worker scoring and selection
```

ADR 0037 records the lifecycle, identity, recovery, authority, state-boundary,
and platform decisions. The implementation extends rather than replaces the
Sprint 0.5 mission contracts and Sprint 1 router.

## Runtime lifecycle

Julia Core has explicit `STARTING`, `RUNNING`, `PAUSED`, `STOPPING`, `STOPPED`,
and `FAILED` states. State transitions and events are durable in SQLite with
WAL enabled. The supervisor registers and heartbeats the local node, pauses new
execution without hiding durable state, and performs recovery classification
before accepting normal work after startup.

The `julia-runtime` operator interface provides `status`, `health`, `nodes`,
`start`, `stop`, `restart`, `pause`, `resume`, service installation/removal,
and portable state export. Local API routes provide runtime status, health,
nodes, recovery records, pause, and resume.

## macOS service behavior

The installed per-user LaunchAgent is `com.julia.core`. It uses `RunAtLoad` and
a successful-exit-aware `KeepAlive` contract so Julia starts at login, restarts
after an unexpected failure, and stays stopped after an intentional clean stop.
It is a background process and does not own a Terminal or UI surface.

Live evidence on the validation Mac:

- installed through the Julia service adapter and bootstrapped by `launchd`;
- remained healthy as a headless process;
- an intentional `SIGKILL` caused `launchd` to replace the process;
- the replacement retained the same node identity and durable run history;
- pause changed both runtime and node availability to `PAUSED`;
- resume restored `RUNNING`;
- a clean stop exited with status 0 and did not restart;
- a subsequent explicit start restored a healthy service.

The final service definition currently launches the checkout's virtual-environment
Python. That is appropriate for this development baseline but is tracked as the
packaging condition S2-002.

## Node registry and identity

The node registry persists a random stable logical `node_id`, display metadata,
platform, architecture, conservative hardware summary, capabilities, lifecycle
availability, primary-node role, and heartbeat timestamps. Identity is stored
under the node-local state root and is not derived from hostname, serial number,
hardware UUID, or another sensitive or replaceable machine attribute.

Process restarts retain the identity. Promoting a node to primary demotes the
previous primary record, keeping the registry internally consistent. The
current Mac is represented through the generic node contract; no objective or
routing code depends on the phrase `MacBook Air`.

## Node-aware routing

`WorkerDescriptor` may bind a worker to a node, authorization may constrain
eligible node IDs, and routing decisions record the selected node. Node
authorization and node availability are hard gates evaluated before Sprint 1
worker eligibility and scoring. An unavailable, paused, failed, or unauthorized
node therefore cannot win through quality, cost, latency, locality, or another
soft score.

When node availability changes during recoverable work, objective state remains
durable and replanning considers only execution paths that remain authorized and
eligible. The existing provider, tool, filesystem, network, GUI, and spending
ceilings are not broadened.

## Restart, recovery, and duplicate protection

Each execution attempt records a stable idempotency key, task/objective identity,
node, immutable authorization snapshot, execution state, and side-effect state.
Recovery classifies interrupted work explicitly:

- safe work may be retried;
- committed work is not repeated;
- ambiguous side effects require manual reconciliation;
- ineligible or unauthorized paths remain stopped.

Interrupted attempts are classified once and excluded from repeated startup
classification. Duplicate idempotency keys are rejected. Recovery recreates the
original authorization ceiling from the stored snapshot rather than from current
ambient capabilities.

## Primary-node abstraction and portability exercise

The current machine is merely the current primary node. Julia-wide databases
live under the core state root; stable node identity lives under a separate
node-local root. A portable export uses SQLite backup and deliberately excludes
node identity.

A clean temporary Julia root was created to represent another compatible Mac.
Julia-wide databases were exported, the new root generated a distinct local
identity, and that node assumed primary status without changing mission or
routing contracts. Full multi-node synchronization and automatic failover remain
explicit non-goals.

## Lifecycle observability

Operators can inspect current runtime state, process-independent run history,
last transition, registered nodes, node availability, recovery dispositions,
and health without opening a worker session. Hardware discovery is best-effort
and privacy-safe; unavailable fields remain unavailable rather than fabricated.

Boot-budget validation passed with an explicit checkout `PYTHONPATH` in the
isolated test driver: bootstrap window 313 ms (budget 8,000 ms), voice time to
usable 10,639 ms (budget 20,000 ms), and application interactive 10,937 ms
(budget 20,000 ms). The initial driver invocation without the checkout import
path failed before measurement and did not expose a product defect.

## Acceptance matrix

| Test | Status | Evidence |
|---|---|---|
| A — Background Runtime | **PASS** | Installed LaunchAgent remained healthy as a headless process without a Terminal or Julia UI owner. |
| B — Automatic Startup | **PASS** | A controlled physical reboot completed on 2026-09-17; the LaunchAgent started Julia's persistent runtime without manual development-environment startup. |
| C — Process Recovery | **PASS** | Live `SIGKILL` replaced the process, preserved runtime data, and retained node identity. |
| D — Host Restart Recovery | **PASS WITH CONDITION** | Persistent-store restart recovery and disposition reconstruction passed in a fresh process; the controlled reboot confirmed startup but did not include an unfinished-objective fixture. |
| E — Duplicate-Execution Protection | **PASS** | Ambiguous side effects produce manual reconciliation, committed effects are not rerun, and duplicate idempotency keys are rejected. |
| F — Stable Node Identity | **PASS WITH CONDITION** | Identity survived real service process restarts; an explicit before/after node-ID comparison was not recorded for the controlled reboot. |
| G — Node Availability Gate | **PASS** | An otherwise optimal worker on an unavailable node is rejected before scoring. |
| H — Node-Aware Replanning | **PASS** | Interrupted availability preserves state and restricts replanning to authorized eligible nodes/workers. |
| I — Authority Containment | **PASS** | Recovery uses the immutable original authorization snapshot. |
| J — Pause / Resume | **PASS** | Live pause stopped new eligibility while preserving state; resume restored normal availability. |
| K — Primary-Node Abstraction | **PASS** | Generic node contracts contain no MacBook-specific routing/objective dependency. |
| L — Portability Exercise | **PASS** | Temporary compatible root received Julia-wide state but not node identity and could assume primary status. |
| M — Sprint 1 Regression | **PASS WITH CONDITIONS** | Sprint 2 focused routing/runtime/API tests passed; broad mission regressions retained only unrelated known baseline failures. |

## Verification results

- Final Sprint 2 runtime, recovery, routing, and API selection: **32 passed**.
- Additional mission/bootstrap selection: **122 passed**; two pre-existing
  headless-launcher fixture failures use a fake bus without the existing
  `subscribe_all` interface.
- Broad mission regression with local sockets permitted: **1,565 passed, 15
  skipped, 6 failed**.
- Frontend TypeScript check and isolated Vite production build: **passed**;
  existing dynamic-import and chunk-size warnings remain.
- Boot-budget validation: **passed** at 313 ms / 10,639 ms / 10,937 ms against
  the 8,000 ms / 20,000 ms / 20,000 ms budgets.
- Python compilation of affected packages: **passed**.
- Disposable background-runtime lifecycle exercise: **passed**.
- `git diff --check`: **passed**.

The six broad-regression failures are outside changed Sprint 2 files:

- two existing English deliverable/readback wording expectations;
- three tests whose generated pytest worktree paths exceed the existing
  200-character guard on this host;
- one existing provider-map expectation that omits the already-present
  `vertex` mapping.

These failures are retained under S1-005 rather than silently treated as green.

## Sprint 0.5 critical regression results

The broad mission run covers the accepted provider binding, Codex containment,
critic/verification, approvals, worker execution, routing, and recovery seams.
Sprint 2 does not modify or weaken the live disposable-repository Codex worker
evidence recorded in the Sprint 0.5 validation. The focused runtime integration
also confirms the new execution-attempt callbacks preserve those mission
boundaries.

## Inherited condition dispositions

| Condition | Sprint 2 disposition | Basis |
|---|---|---|
| S0-001 context / rate-limit preflight | **MITIGATED** | Runtime recovery and routing use compact structured records; the broader hosted-chat preflight remains incomplete. |
| S0-002 tracked configuration mutation | **DEFERRED** | Configuration-writer redesign is outside this sprint. |
| S0-003 Keychain fallback | **DEFERRED** | Credential storage is unchanged. |
| S0-007 inadequate local model | **MITIGATED** | Sprint 1's bounded viable local candidates remain available; this sprint does not generalize that benchmark. |
| S0-008 realtime cost attribution | **DEFERRED** | Runtime persistence does not redesign realtime voice pricing. |
| S0-009 runtime data-root isolation | **MITIGATED** | New Julia-wide and node-local roots are explicit and portable; older subsystem roots remain to be consolidated. |
| S0-010 first-boot download disclosure | **DEFERRED** | Browser bootstrap disclosure is outside this sprint. |
| S1-001 adapter-internal fallback duplication | **ACCEPTED RISK** | Node gating is outside adapters and cannot broaden authority; historical adapter fallbacks remain. |
| S1-002 bootstrap routing priors | **ACCEPTED RISK** | Node gating is deterministic; scoring priors remain human-reviewed estimates. |
| S1-003 bounded local benchmark | **ACCEPTED RISK** | No cross-host model-performance claim is added. |
| S1-004 live external-quota failover | **ACCEPTED RISK** | Recovery preserves the deterministic failover contract without intentionally exhausting a paid account. |
| S1-005 unrelated baseline test drift | **DEFERRED** | The six broad-regression failures remain unrelated to Sprint 2 paths. |

No inherited condition regressed.

## New issues and conditions

### S2-001 — Physical host reboot observation

- Classification: **FIXED**.
- Controlled physical reboot completed 2026-09-17. Julia's LaunchAgent
  successfully started the persistent runtime after reboot without manual
  development-environment startup.

### S2-002 — Development-checkout service path

- Classification: **ACCEPTED RISK**.
- The installed LaunchAgent points to this checkout's virtual environment. A
  packaged release should install an immutable executable path and migrate the
  service definition during upgrades.

### S2-003 — Native service parity beyond macOS

- Classification: **ACCEPTED RISK**.
- The lifecycle contract and state model are platform-neutral, but only the
  required macOS native service adapter is implemented in Sprint 2.

### S2-004 — Single-primary persistence model

- Classification: **ACCEPTED RISK**.
- The registry can describe and promote nodes, but state synchronization,
  consensus, and automatic multi-node failover are explicit non-goals.

## Final verdict

**ACCEPT WITH CONDITIONS.**

Julia can remain available as a persistent system on the trusted Mac, recover
from real process failure, preserve objectives and authority, model the machine
as a replaceable execution node, prevent blind duplicate side effects, and run
without an open Terminal, UI, or worker session. Automatic startup after a
controlled physical reboot is now directly observed rather than inferred from
the passing process and LaunchAgent tests.

Sprint 2 stops here. Sprint 3 is not started.

# Julia Sprint 2 runtime inventory

Date: 2026-09-17

## Existing foundation

- `jarvis/ui/web/launcher.py` owns the current desktop/headless process and the
  single-instance lock. The backend can already run without a visible window.
- `jarvis/autostart/` provides cross-platform login startup. On macOS the
  existing LaunchAgent opens the graphical application to preserve its TCC
  identity; it is not a headless Julia Core supervisor.
- `jarvis/missions/missions.db` is an event-sourced durable mission ledger.
  Mission events are persisted before publication and mission headers can be
  reconstructed after a crash.
- `jarvis/missions/recovery.py` conservatively reconciles terminal events and
  fails genuinely stale missions. It does not distinguish retry, verification,
  approval, or ambiguous external side effects.
- `jarvis/julia/routing/` provides the accepted Sprint 1 worker registry,
  authorization contract, hard eligibility gates, routing evidence, failure
  classification, and outcome history.
- `memory.data_dir` is the effective runtime data root for missions, but other
  subsystems still resolve independent roots. There is no explicit split
  between Julia-wide state and machine-local identity/state.

## Extension decision

Sprint 2 extends these seams instead of replacing them:

1. A small Julia runtime ledger stores lifecycle, node, execution, recovery,
   and idempotency records beside the mission database.
2. A machine-local identity file is stored under a separately configurable
   node-state root. Copying Julia-wide state therefore does not clone a node.
3. Worker descriptors gain an optional hosting `node_id`; node eligibility is
   evaluated before the existing Sprint 1 worker gates.
4. A dedicated headless runtime process is managed by a macOS LaunchAgent. The
   graphical application remains a client and may continue to use its existing
   TCC-preserving startup entry independently.
5. Mission recovery remains authoritative for mission lifecycle. The Julia
   runtime adds a more precise execution-attempt ledger and reconciliation
   dispositions without silently replaying mission actions.

## Constraints carried forward

- Recovery never expands an objective's authorization contract.
- A local node outage is distinct from a worker/provider outage.
- Ambiguous side effects stop for reconciliation rather than being retried.
- Node and runtime support stays capability-gated so base boot still works on
  macOS, Windows, Linux, and headless installs.
- Full multi-node synchronization, remote ingress, and distributed consensus
  remain outside Sprint 2.

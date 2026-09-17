# Julia Sprint 1 worker routing validation

**Date:** 2026-09-17
**Branch:** `sprint-1-worker-routing`
**Foundation:** `jarvis-baseline-v0.1` / `181f2c6e5a99efd9706665430a20d7b135a8a6f4`
**Verdict:** **ACCEPT WITH CONDITIONS**

## Executive summary

Sprint 1 extends the accepted Personal Jarvis mission foundation with Julia's
first provider-neutral intelligence-management layer. Julia now creates a
compact structured task profile, filters a live worker registry through hard
authorization and eligibility gates, scores only eligible workers, persists the
complete decision, observes classified failures, and recomputes candidates
without expanding the objective's original authority.

The definition-of-done question is answered **yes** by the implemented contract
and acceptance evidence. Conditions remain around real-world calibration,
legacy adapter-internal fallback code, and a live external-quota failover run.
No Sprint 2 work is included.

## Architecture

```text
Objective / durable mission
          |
          v
Structured TaskProfile + immutable AuthorizationContract
          |
          v
Authoritative WorkerRegistry -- current AvailabilityRecord
          |
          v
Hard gates: authority, availability, capabilities, tools,
privacy, execution scope, minimum quality, context capacity
          |
          v
Configurable utility score over eligible workers only
          |
          v
Existing isolated mission worker -> Critic / verification
          |
          +--> outcome history and aggregate metrics
          |
          +--> classified failure -> availability update
                                  -> same task/authority -> replan or safe stop
```

The new code is under `jarvis/julia/routing/`; the accepted implementations in
`jarvis/missions/workers/` remain execution adapters. ADR-0036 records the T3
decision and trade-offs. Routing metadata is stored in
`julia_worker_routing.db`, while `missions.db` remains authoritative for the
objective lifecycle.

## Julia / Jules migration

The inventory is in `docs/julia-naming-inventory.md`. The baseline contains tens
of thousands of overlapping Jarvis/package occurrences. They were classified
before editing:

- upstream provenance, copyright, URLs, historical evidence, package imports,
  configuration keys, and app identifiers remain Personal Jarvis / `jarvis`;
- new intelligence components and Sprint 1 documentation use Julia;
- Jules is reserved for new conversational identity copy;
- no global rename, executable rename, data-root migration, or upstream
  provenance rewrite was performed.

## Worker registry

The authoritative descriptor includes worker/provider/model/class,
capabilities, tools, execution modes, authorization, availability and privacy,
context capacity, expected quality/cost/latency/reliability/risk, empirical
history, health time, last failure, and retry time.

Initial declarative adapters cover heterogeneous subscription, API, CLI, and
local workers. Provider details are confined to adapters and cheap health
probes; the registry, gates, policy, persistence, and API do not branch on a
provider family.

Availability supports all required states:
`AVAILABLE`, `DEGRADED`, `RATE_LIMITED`, `QUOTA_EXHAUSTED`, `AUTH_REQUIRED`,
`PROVIDER_UNAVAILABLE`, `TOOL_UNAVAILABLE`, `DISABLED`, and `UNKNOWN`.
Temporary states can re-enter after their retry window.

## Task profile, gates, and routing policy

Mission steps contribute structured repository need and declared tools; compact
prompt signals supply a bounded task category. Routing does not receive full
conversation history, memories, project history, or tool traces.

Every candidate is rejected before scoring if it fails any of:

1. worker and objective authorization;
2. current eligible availability;
3. required capabilities;
4. required tools;
5. privacy ceiling;
6. execution scope and scope authorization;
7. minimum task-specific quality;
8. context capacity.

Survivors receive a configurable weighted score across task quality, expected
success, cost, latency, reliability, context fit, and execution risk. Cost is
therefore unable to rescue a worker below the quality threshold. Weights live
under `[phase6.routing]`; the hard gates are not configurable.

## Availability and failover

Worker errors are classified using the required Sprint 1 vocabulary. Quota,
auth, provider, tool, and timeout failures update the registry before a later
delegation attempt. The selected worker id is associated with the durable task,
and the original provider/tool/privacy/scope contract is reused.

The required deterministic Codex scenario passed:

```text
Codex selected -> QUOTA_EXHAUSTED persisted -> Codex ineligible
-> task/objective preserved -> candidates recomputed
-> authorized alternative selected
```

The paired no-alternative test also passed: an otherwise optimal Claude worker
remained rejected as `not_authorized`, and routing stopped safely. No GUI or
computer-use capability was added after failure.

## Explainability and outcome telemetry

Each decision stores the task profile, every candidate, every gate rejection,
score components, selected worker/provider/model, and selection reason. The
Missions API exposes secret-free views at:

- `GET /api/missions/routing/workers`;
- `GET /api/missions/routing/decisions/{objective_id}`;
- `GET /api/missions/routing/metrics`.

Worker outcomes persist duration, estimated and actual cost, attempts, worker
and critic result, failure class, human correction, and final status. Outcomes
update registry history and aggregate success rate, critic acceptance, average
attempts/cost/latency, and human-correction rate by worker/task category. The
data is collected but policy weights do not self-modify.

## Local-model benchmark

Full method and case evidence are in `docs/julia-local-worker-benchmark.md`.
The physical host was an Apple M3 MacBook Air with 24 GB unified memory and
Ollama 0.34.1.

| Model | Score | Warm latency | Resident memory | Disposition |
|---|---:|---:|---:|---|
| `qwen3.5:9b` | 7/7 | 1.14 s | 5.5 GB | Viable preferred measured control-plane candidate |
| `qwen3:14b` | 7/7 | 1.60 s | 9.6 GB | Viable reserve candidate |
| `gemma3:12b` | 6/7 | 1.58 s | 8.9 GB | Rejected for insufficiency-recognition failure |

Ollama remains a replaceable registry adapter and its configured model is read
at runtime. Sprint 1 did not hardcode either viable model or silently change the
user's active OpenAI worker configuration.

## Acceptance matrix

| Test | Status | Evidence |
|---|---|---|
| A — Registry | **PASS** | Codex direct, Claude direct, and local/API workers share one descriptor/registry contract. |
| B — Capability Gate | **PASS** | Missing `coding` candidate rejected with no score. |
| C — Authorization Gate | **PASS** | Higher-quality unauthorized worker rejected before scoring. |
| D — Availability Gate | **PASS** | `QUOTA_EXHAUSTED` candidate excluded from new delegation. |
| E — Quality Threshold | **PASS** | Free low-quality worker rejected; qualified paid worker selected. |
| F — Cost Optimization | **PASS** | Equivalent qualified workers differentiated by cost utility. |
| G — Failover | **PASS** | Required Codex quota sequence persisted and selected an authorized alternative. |
| H — Fail Closed | **PASS** | No-authorized-alternative case raised a safe no-selection result. |
| I — Authority Containment | **PASS** | Failure could not add GUI/computer-use tools or execution scope. |
| J — Explainability | **PASS** | Decisions round-trip from SQLite and diagnostics API with gates and scores. |
| K — Outcome Learning Data | **PASS** | Success/failure updated durable aggregates and registry history. |
| L — Local Routing | **PASS** | Two local candidates passed simple routing plus deliberate escalation; one candidate failed insufficiency and was rejected. |
| M — Foundation Regression | **PASS WITH CONDITIONS** | Provider binding, Codex containment, critic, approvals, worker tools, hosted-provider routes, and voice selections passed. Six unchanged unrelated tests remain listed below. |

## Verification results

- Sprint 1 routing/API contract: **20 passed**.
- Critical Sprint 0.5 regression selection: **815 passed, 37 skipped, 6 failed**.
- Additional integration/config/bootstrap selection before the final sweep:
  **134 passed** and **92 passed** in two focused runs.
- Frontend TypeScript build and Vite production build to an isolated temporary
  output directory: **passed** (existing generated asset directory preserved).
- Python compilation for new/affected packages: **passed**.
- `git diff --check`: **passed**.

The six regression-selection failures do not touch changed Sprint 1 files:

- two existing English deliverable/readback wording expectations;
- two lean-workspace tests whose pytest temporary paths exceeded the existing
  200-character guard on this host;
- one provider health fixture that omits the existing `local_models` section;
- one provider response test whose blanket `auth.json` assertion also matches
  the existing public Grok credential-help path.

They are conditions, not evidence of a Sprint 1 routing regression.

## Sprint 0 condition disposition

| Condition | Sprint 1 disposition | Basis |
|---|---|---|
| S0-001 context / rate-limit preflight | **MITIGATED** | Routing uses compact structured context and bounded candidate evidence; the broader hosted-chat preflight is not fully repaired. |
| S0-002 tracked configuration mutation | **DEFERRED** | Sprint 1 adds typed policy config but does not redesign the existing config-writer/drift artifact. |
| S0-003 Keychain fallback | **DEFERRED** | Credential storage was not changed. |
| S0-007 inadequate local model | **MITIGATED** | Two stronger models passed the bounded controller suite and are installed/integrable; no silent live-model switch was made. |
| S0-008 realtime cost attribution | **DEFERRED** | Worker outcome costs are recorded; realtime voice pricing remains separate. |
| S0-009 runtime data-root isolation | **MITIGATED** | The new routing DB derives from the caller-provided missions data root; older independently resolved roots remain. |
| S0-010 first-boot download disclosure | **DEFERRED** | Browser bootstrap disclosure was outside Sprint 1. |

No condition regressed.

## New issues and conditions

### S1-001 — Adapter-internal fallback duplication

- Classification: **Accepted risk** for Sprint 1.
- The Julia factory seam is authoritative, but accepted worker adapters still
  contain historical fallback branches. Remove them only through a separately
  validated compatibility change; they must never broaden Julia's authorization
  contract.

### S1-002 — Routing priors are bootstrap estimates

- Classification: **Accepted risk**.
- Expected quality/cost/latency values are initial estimates. Durable empirical
  outcomes now exist, but Sprint 1 deliberately forbids learned/self-modifying
  policy. Recalibration requires human-reviewed evidence.

### S1-003 — Local benchmark coverage is bounded

- Classification: **Accepted risk**.
- The benchmark is one deterministic run on one M3/24 GB host. It establishes a
  viable control-plane candidate, not general model superiority or cross-host
  performance parity.

### S1-004 — Live external-quota failover not forced

- Classification: **Accepted risk**.
- The exact quota sequence is proven through deterministic persisted contracts
  and the live runtime uses the same registry/replan path. Sprint 1 did not
  intentionally exhaust a paid account to reproduce it against an external
  provider.

### S1-005 — Unrelated baseline test drift remains

- Classification: **Deferred**.
- The six failures listed in verification predate or are independent of Sprint
  1 paths. Fixing them would be additional implementation outside the sprint's
  routing scope.

## Final verdict

**ACCEPT WITH CONDITIONS.**

Julia can dynamically choose the best currently eligible worker, explain and
persist the decision, record outcomes, and safely continue or stop when a worker
becomes unavailable without widening provider, tool, privacy, filesystem,
network, GUI/computer-use, or spending authority.

Sprint 1 stops here. Sprint 2 is not started.

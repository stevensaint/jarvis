# Sprint 0 Foundation Validation

## Foundation Decision

**ACCEPT WITH CONDITIONS**

The initial Sprint 0 run was rejected for mission provider-boundary and Codex
containment failures. Sprint 0.5 corrected those defects and completed the three
previously blocked core paths: provider-bound mission execution, the critic
cycle, and the isolated Codex coding-worker test. The final acceptance matrix is
**8 PASS, 1 PARTIAL, 0 FAIL, 0 BLOCKED**.

The remaining findings concern context/rate-limit preflight, tracked-example
configuration writes, Keychain fallback, local-model capability, realtime cost
attribution, state-root isolation, and first-boot download disclosure. They are
material conditions, but none invalidates the now-proven provider boundary,
approval boundary, worktree containment, or coding-worker path.

This verdict authorizes the Sprint 0 baseline. It does not authorize Sprint 1;
the remaining preconditions below still require resolution or explicit
acceptance.

## Baseline

- Upstream repository: <https://github.com/PersonalJarvis/PersonalJarvis>
- Upstream commit: `9160a7b36c4f7b448b9f25e75f85aa4aabbe1da7`
- Fork repository: <https://github.com/stevensaint/jarvis>
- Remotes:
  - `origin`: `https://github.com/stevensaint/jarvis.git`
  - `upstream`: `https://github.com/PersonalJarvis/PersonalJarvis.git`
- Validation date: 2026-09-16
- Initial validation source changes: none
- Sprint 0.5 source changes: provider binding, Codex containment/binary resolution,
  read-only critic evidence handling, desktop relaunch reliability, UI/telemetry
  attribution, and regression coverage
- Validation artifact: this document only

## Environment

| Item | Observed |
| --- | --- |
| macOS | 26.6.2 (build 25G83) |
| Architecture | Apple Silicon (`arm64`) |
| Hardware | MacBook Air, Apple M3, 8 CPU cores, 10 GPU cores |
| Memory | 24 GB unified memory |
| Metal | Supported |
| Free disk before installation | Approximately 217 GiB |
| System Python | 3.9.6; below the project's supported range |
| Validation Python | CPython 3.13.15 in an isolated `.venv` |
| Git | 2.39.5 (Apple Git-154) |
| Node.js / npm | 22.17.1 / 10.9.2 |
| `uv` | 0.12.15 |
| Homebrew / pipx / Poetry | Not installed |
| Codex CLI | `codex-cli 0.154.0-alpha.6.2`, bundled with ChatGPT and authenticated |
| Claude Code | Not installed as a standalone CLI |
| Gemini CLI | Not installed |
| Ollama | 0.34.1, installed during approved Test H setup |
| Docker | Not installed |

No hardware serial number, hardware UUID, account email, token, credential, API key, or control key is recorded here.

## Installation

The current upstream development path was followed from the forked clone.

1. A self-contained Python 3.13 runtime and isolated `.venv` were provisioned.
2. The documented full editable profile, `.[full]`, installed successfully without source modification.
3. `import jarvis` resolved to this clone.
4. The backend booted on `127.0.0.1:47821` after localhost access was permitted by the execution environment.
5. The upstream desktop-integration command created and signed a stable per-user `Personal Jarvis.app` bundle with identity `com.personal-jarvis.desktop`.
6. The user granted Microphone, Screen Recording, Accessibility, Input Monitoring/Input Control, Automation, and Keychain permissions. The permissions API subsequently reported all required feature-readiness checks true.
7. The desktop app, text chat, realtime voice, mission API, agent chat, approval API, cost ledger, and local-model APIs were reachable.

### Installation observations

- First headless boot automatically downloaded a large Playwright/Chromium runtime (approximately 819 MB) into ignored local data.
- A validation data-directory override did not contain all runtime state; some stores still used the checkout's ignored `data/` tree or the normal per-user Jarvis directory.
- One early headless shutdown required a second interrupt and ended with a Python shutdown traceback. This was not reproduced after the desktop bundle was installed.
- The desktop onboarding screen could visually return after restart even though API configuration and permissions remained present.
- The working tree remained free of application-source changes.

## Configuration

- Main hosted brain: OpenAI `gpt-5-mini`.
  - `gpt-5.5` was initially selected but one request exceeded the account's 10,000-token-per-minute limit; switching to the smaller supported model resolved the baseline call.
- Realtime voice: OpenAI Realtime, model recorded as `gpt-realtime`.
- Mission worker setting: persisted as OpenAI, but live missions still planned and spawned `claude`.
- Codex:
  - Bundled executable configured through PersonalJarvis's supported `codex.binary_path` setting.
  - Authentication probe succeeded through ChatGPT.
  - The agent-chat runner ignored that path and required a reversible `~/.local/bin/codex` symlink before it detected the CLI.
- Local runtime: Ollama 0.34.1 with `qwen3.5:4b`.
- Secrets were entered only through PersonalJarvis's user-facing configuration flow.
- The operating-system credential store was reported unusable by the CLI, so PersonalJarvis used its local mode-0600 credential file. No credential contents were inspected or recorded.
- Upstream configuration commands also mutated tracked `scripts/config-soll.json`; each incidental tracked change was restored immediately. The effective ignored local configuration remained intact.

## Acceptance Tests

| Test | Status | Evidence | Observed behavior / issues |
| --- | --- | --- | --- |
| A — Basic Intelligence | **PASS** | OpenAI `gpt-5-mini` answered “Seventeen times forty-three equals seven hundred thirty-one.” Turn duration 10,454 ms; 21,615 input tokens; 596 output tokens; recorded cost `$0.0071997`. | Initial `gpt-5.5` attempt failed with HTTP 429 because the request exceeded the account TPM limit. Supported model reconfiguration fixed it. |
| B — Voice | **PASS** | Native app captured speech, produced an English transcript, sent it through OpenAI Realtime, and played an audible English reply. The user confirmed the experience. End-to-end latency was 10,145 ms; think 282 ms; speak 8,336 ms. | The test utterance differed from Test A but was a valid simple request. The voice record showed `voice_verified=true`; its cost field was `0.0`, so realtime cost attribution may be incomplete. |
| C — Safe Tool Execution | **PASS** | Jarvis's `Write` tool created `sprint-0-tool-test.txt` with exactly `Sprint 0 tool test successful.\n`. Tool duration 1 ms; turn duration 4,077 ms. | The file was created only in the dedicated Sprint 0 test workspace. |
| D — Mission Execution | **FAIL** | Two missions reached dispatch, planning, running/critic state, worker spawn, isolated worktree creation, and progress events. | Both mission plans selected `worker_cli: claude` despite an explicit OpenAI-only instruction and an active OpenAI worker setting. Both were cancelled before completion. No result or completed critic cycle was produced. |
| E — Codex Worker | **FAIL** | A disposable Git repository contained one intentionally failing standard-library test. Jarvis selected `openai-codex` and started Codex after the CLI symlink workaround. | The runner first ignored the configured binary path. After detection, Codex failed because `codex-code-mode-host` was missing, attempted GUI fallbacks into Terminal and Cursor, and reported no changes. The disposable main tree remained unchanged and its test still failed, so isolation was preserved only because no work completed. |
| F — Critic | **BLOCKED** | Static critic implementation and the transition into `CRITIQUING` were observed. | Test D's unauthorized worker selection required cancellation before any verdict. No accept, correction, or retry result can be claimed. |
| G — Approval System | **PASS** | An OpenAI agent in `ask` mode proposed `Write approval-test.txt`, emitted `approval_required`, and paused with no file present. After the user's explicit one-time approval, it emitted `approval_resolved`, created the exact requested content, and completed. | The disposable file was verified and then removed. No external or meaningful action occurred. |
| H — Local Model | **PARTIAL** | PersonalJarvis successfully invoked Ollama 0.34.1 with `qwen3.5:4b`; GGUF, 4.7B parameters, `Q4_K_M`. Loaded footprint was 3,144,910,109 bytes in unified GPU memory. Cold latency was 11,287 ms; warm latency was 383 ms. | Local inference was operational and responsive once warm, but it answered `741` instead of `731` on both attempts. The selected small model is not adequate for even this simple correctness check under the tested prompt/context. |
| I — Cost / Telemetry | **PASS** | A hosted OpenAI `gpt-5-mini` turn returned `telemetry-ok` in 3,405 ms. The session recorded provider, model, runner, duration, 1,235 input tokens, and 12 output tokens. The cost ledger recorded 1,247 total tokens and derived cost `$0.000385`. | Cost was derived from the built-in rate table rather than returned by the provider. Agent-chat event payload omitted cost, but the unified cost ledger supplied it by session reference. |

Original-run summary: **5 PASS, 1 PARTIAL, 2 FAIL, 1 BLOCKED**. See the Sprint
0.5 completion section for the canonical final matrix.

## Architecture Gap Analysis

| Subsystem | Status | Evidence | Recommended Action |
| --- | --- | --- | --- |
| Gateway | KEEP | FastAPI REST/WebSocket API, desktop webview, and CLI operated locally. | Preserve the loopback gateway and schema-driven CLI. |
| Event system | KEEP | Durable typed events captured chat, tools, missions, workers, approvals, and costs. | Add privacy classification and retention controls for high-context tool output. |
| Local supervisor interface | EXTEND | BrainManager and mission supervisor exist, but provider neutrality was not enforced. | Introduce one binding authority for provider choice before any new routing work. |
| Context resolver | KEEP | Sessions, awareness, wiki, and turn context were active. | Measure context size; Test A's small question carried 21,615 input tokens. |
| Provider abstraction | EXTEND | Hosted and local API providers worked, but mission configuration and execution diverged. | Make resolved provider immutable and auditable from request through worker spawn. |
| Worker registry | REPLACE | The displayed active OpenAI worker did not control the mission planner's Claude selection. | Replace duplicated selection paths with one registry/resolver contract. |
| Mission/task system | EXTEND | Persistence, worktrees, cancellation, and progress events worked; completion did not. | Fix provider binding, then rerun mission/recovery/critic tests. |
| Codex integration | REPLACE | Authentication worked, but binary-path handling and the packaged execution host failed. | Unify binary resolution, package/verify the host, and prohibit GUI fallback outside task scope. |
| Claude integration | CONFIGURE | Mission path attempted Claude despite no approved Claude configuration. | Fail closed when unconfigured or unauthorized; never select by silent fallback. |
| Gemini integration | CONFIGURE | Provider/plugin exists but was intentionally left unconfigured. | Test only after the core provider boundary is fixed. |
| xAI integration | CONFIGURE | Provider paths exist but were not configured. | Leave optional. |
| Local-model integration | KEEP | Ollama discovery, catalog, API runner, metadata, and memory reporting worked. | Select a more capable model and define correctness/latency gates in a later validation. |
| Critic | BLOCKED | Implementation exists; no live verdict completed. | Rerun after mission provider enforcement is fixed. |
| Risk engine | KEEP | `ask` mode classified the write as approval-required. | Add denial/cancellation coverage next. |
| Approval system | KEEP | Exact proposal, pause, one-time decision, continuation, and audit events worked. | Preserve this boundary unchanged. |
| MCP | KEEP | Mission-scoped broker and MCP architecture are present. | Validate authority scoping and injection resistance separately. |
| Computer use | REPLACE | Codex used broad GUI fallback after a missing shell host and enumerated unrelated app/browser context. | Deny GUI escalation unless explicitly part of the task and separately authorized. |
| Memory | KEEP | Wiki and persistent stores initialized. | Add provenance and prompt-injection tests. |
| Cost tracking | KEEP | Unified ledger attributed provider/model/tokens/cost/session. | Surface price-source and missing-cost warnings consistently. |
| Telemetry | KEEP | Duration, tokens, cache use, events, and costs were observable. | Align per-turn and ledger cost fields, especially realtime voice. |
| Voice input | KEEP | Native permissions, speech capture, and transcript path worked. | Add repeatability and wake-word tests later. |
| Voice output | KEEP | Audible OpenAI Realtime output worked. | Verify fallback and offline paths later. |
| Headless/API operation | KEEP | Local service and CLI worked, subject to control-key middleware. | Test authenticated remote mode before any exposure. |
| iPhone/mobile ingress | EXTEND | No dedicated mobile ingress was validated. | Choose secure browser, Shortcut, or native ingress in a future sprint. |
| Remote authentication | CONFIGURE | Loopback control key exists; browser lock is off by default on loopback. | Require authentication before non-loopback binding or forwarding. |
| Notifications | CONFIGURE | Desktop app identity exists; notification delivery was not exercised. | Validate only after foundation blockers are resolved. |
| Persistent sessions | KEEP | Text, voice, agent, mission, approval, and cost sessions persisted. | Add restart/resume and retention tests. |
| Capability-based routing | EXTEND | Capability metadata exists, but live worker routing contradicted configuration. | Make capability and authorization constraints hard gates. |
| Cost-aware routing | EXTEND | Cost data exists; no accepted runtime policy optimized by cost. | Design only after attribution is consistently complete. |
| Adaptive/empirical routing | MISSING | No validated learning loop selects workers from historical task outcomes. | New work, but not until the foundation passes revalidation. |

## Issues

### S0-001 — Large default context exceeded hosted account TPM

- Severity: Medium
- Reproduction: Run Test A with the initially selected OpenAI `gpt-5.5` model and the default Jarvis context.
- Observed: HTTP 429; requested input exceeded the account's 10,000 TPM limit.
- Likely cause: Large default context plus a model/account rate-limit mismatch.
- Classification: Configuration and context-size issue.
- Recommendation: Add preflight estimation and a smaller-context/model fallback before sending.

### S0-002 — Configuration commands mutate a tracked example file

- Severity: High
- Reproduction: Persist a main-brain or mission-worker provider switch.
- Observed: `scripts/config-soll.json` changed alongside ignored local configuration.
- Likely cause: The configuration writer treats a tracked example/drift file as an active persistence target.
- Classification: Upstream defect.
- Recommendation: Never write runtime credentials/provider choices to tracked files; separate generated drift output from repository fixtures.

### S0-003 — Credential store fell back from Keychain

- Severity: Medium
- Reproduction: Run provider status from the installed checkout.
- Observed: CLI reported the OS credential store unusable and used a local mode-0600 credential file.
- Likely cause: Keyring integration failed under this installation/runtime identity.
- Classification: Upstream/environment integration issue.
- Recommendation: Fix Keychain integration or make the fallback prominent in the UI with migration guidance.

### S0-004 — Mission provider boundary is not enforced

- Severity: Critical
- Reproduction: Configure the mission worker to OpenAI; verify the status endpoint resolves `openai/gpt-5-mini`; dispatch an OpenAI-only repository investigation.
- Observed: The plan and worker events still named `claude`. This occurred twice, including after a persisted OpenAI switch. Both missions were cancelled.
- Likely cause: The mission decomposer/worker factory has a separate default or fallback path that ignores the configured active provider and prompt constraint.
- Classification: Upstream security and correctness defect.
- Recommendation: Resolve and persist one provider binding before planning; include it in every event; fail closed on mismatch; add a regression test proving no unapproved fallback.

### S0-005 — Codex binary-path setting is ignored by agent chat

- Severity: High
- Reproduction: Set `codex.binary_path` to the authenticated Codex executable and create an `openai-codex` agent session.
- Observed: Authentication probe passed, but the agent runner tried bare `codex` and failed until a `~/.local/bin/codex` symlink was added.
- Likely cause: Authentication and agent-chat runners use different binary resolvers.
- Classification: Upstream defect.
- Recommendation: Use one binary-resolution service across probes, catalog, agent chat, missions, and app-server clients.

### S0-006 — Codex execution host is missing and fallback escapes task scope

- Severity: Critical
- Reproduction: Run the disposable failing-test task through the detected Codex agent.
- Observed: The repository shell failed because `codex-code-mode-host` was missing. Codex then attempted Terminal and Cursor GUI fallbacks and read broad ambient app/browser metadata before giving up.
- Likely cause: Incomplete packaging plus an overly permissive fallback policy.
- Classification: Upstream packaging, privacy, and containment defect.
- Recommendation: Package and preflight the host; terminate the task on host failure; forbid UI fallback unless the user explicitly selected computer use for that task.

### S0-007 — Small local model failed elementary arithmetic

- Severity: High for supervisor use; Low for integration plumbing
- Reproduction: Ask `qwen3.5:4b` “What is 17 multiplied by 43? Reply with only the number.” twice through the Jarvis Ollama agent.
- Observed: Both cold and warm runs returned `741`; correct result is `731`.
- Likely cause: Model capability/quality under the large cached agent context, not an Ollama transport failure.
- Classification: Model-selection limitation.
- Recommendation: Do not use this model as a supervisor. Test a stronger approved model with a bounded context and correctness suite in a future validation.

### S0-008 — Realtime voice cost recorded as zero

- Severity: Medium
- Reproduction: Complete a live OpenAI Realtime voice turn and inspect session telemetry.
- Observed: Provider/model/tokens/latency were present, but `cost_usd` was `0.0`.
- Likely cause: Missing realtime price mapping or delayed cost ingestion.
- Classification: Upstream telemetry gap.
- Recommendation: Attribute audio/text token pricing and label unavailable cost as unavailable rather than zero.

### S0-009 — Runtime data roots are not fully isolated

- Severity: Medium
- Reproduction: Launch with a validation-specific data directory.
- Observed: Some databases/assets still landed in the checkout's ignored data tree or the normal per-user Jarvis directory.
- Likely cause: Subsystems resolve state roots independently.
- Classification: Upstream isolation issue.
- Recommendation: Centralize all data-root resolution and expose it in diagnostics.

### S0-010 — First headless boot performs an unannounced large download

- Severity: Medium
- Reproduction: First full-profile headless boot.
- Observed: Playwright/Chromium assets added approximately 819 MB.
- Likely cause: Deferred browser bootstrap.
- Classification: Upstream product behavior.
- Recommendation: Preflight the size and require an explicit installation step or document the download clearly.

## Security Findings

- No secret value was printed into this document, source, Git, or the tracked configuration.
- The main security failure is the mission provider mismatch: source inspection intended only for OpenAI was delegated to a Claude worker without authorization. Cancellation stopped both runs, but each worker had already begun listing/reading repository files.
- The Codex fallback read and recorded unrelated ambient application/browser metadata after its repository shell failed. Task failure must not expand authority into computer use.
- Approval Test G behaved correctly: no write occurred before the explicit decision, the proposed arguments were visible, and one-time approval resumed only that call.
- PersonalJarvis's local mutation APIs require a control key. Direct unauthenticated POSTs received HTTP 403.
- The local web service remained loopback-only. Non-loopback exposure was not attempted.
- macOS permissions are bound to the stable signed app identity rather than a transient Python process.
- Credential fallback uses a mode-0600 file because Keychain integration failed; this is materially weaker than a functioning OS credential store.
- Voice telemetry recorded zero cost despite nonzero usage. Unknown cost should never be represented as confirmed zero.
- Retrieved content, MCP, screen context, computer use, and persistent memory remain prompt-injection surfaces that were not fully exercised in Sprint 0.

## Sprint 1 Preconditions

Sprint 1 is not authorized and the repository is not ready for it. Before any custom supervisor/model-routing implementation:

1. Fix S0-004 and prove that provider authorization is immutable from request through worker spawn, including a fail-closed regression test.
2. Fix S0-005 and S0-006; package and preflight the Codex execution host and remove unauthorized GUI fallback.
3. Rerun Tests D, E, and F end to end with completed results and critic verdicts.
4. Add a denial-path test for the approval system.
5. Restore a functioning macOS Keychain path or explicitly accept the local-file secret-storage risk.
6. Bound default context size and add rate-limit-aware preflight/fallback behavior.
7. Correct realtime cost attribution and distinguish unavailable cost from zero.
8. Select and validate a stronger local model; `qwen3.5:4b` is not acceptable as a supervisor based on this test.
9. Add a privacy regression test proving that failed repository tools cannot enumerate or operate unrelated desktop/browser state.
10. Rerun the complete Sprint 0 matrix and issue a new foundation decision.

## Original Baseline Status

- Baseline commit: **not created**
- Push: **not performed**
- Tag `jarvis-baseline-v0.1`: **not created**
- Reason: Foundation verdict is `REJECT`; Phase 9 permits baseline publication only for `ACCEPT` or `ACCEPT WITH CONDITIONS`.

## Remediation Run — 2026-09-17

This section records implementation and revalidation performed after the
original report. It does not rewrite the original observations above.

### Interim Result

At this point the foundation verdict remained **REJECT pending one external-capacity-blocked
test**. Tests D and F now pass end to end. The implementation paths for S0-005
and S0-006 are repaired and their containment preflight passed, but Test E
could not complete because the authenticated ChatGPT Codex account reached its
usage limit before it could edit and retest the disposable repository. No
baseline commit, push, or tag was created.

| Test | Remediation status | Evidence |
| --- | --- | --- |
| D — Mission Execution | **PASS** | Mission `01a0af09-3d68-73b1-94ba-4199b4008979` reached `APPROVED`. `MissionPlanReady` persisted `worker_cli: configured` and `provider_binding: openai`; `WorkerSpawned` also recorded `provider: openai`. The worker read `README.md` and returned the correct first heading without a file change. |
| E — Codex Worker | **BLOCKED** | The configured native Codex binary was resolved, the packaged `codex-code-mode-host` was available to the child process, and no Terminal, Cursor, or computer-use fallback occurred. The authenticated Codex turn then stopped at the account usage limit before making the requested fix. The disposable repository remains unmodified and its test still fails (`60 != 731`). |
| F — Critic | **PASS** | The same mission produced `CriticVerdictReady(verdict=approve, confidence=1.0)` on iteration 0 and transitioned from `CRITIQUING` to `APPROVED`. A verified read-only answer is now treated as the deliverable instead of being incorrectly retried as an empty file diff. |

### Implemented Remediation

- S0-004: provider choice is resolved once at mission planning, stored as an
  immutable step binding, passed into the worker factory, emitted on worker
  events, shown in the UI, and preferred by cost attribution. Legacy planner
  hints such as `claude` normalize to `configured`; they cannot override the
  bound provider. Worker task-group failures now terminate the durable mission
  rather than leaving it stranded in `CRITIQUING`.
- S0-005: agent chat and direct Codex workers now use the configured Codex
  binary resolver rather than requiring a PATH symlink.
- S0-006: the packaged execution-host directory is added only to the Codex
  child environment, and agent chat starts Codex with user configuration
  disabled so ambient plugins cannot introduce unauthorized GUI fallback.
- Critic revalidation: read-only requests with named input files are accepted
  when the worker supplies real tool evidence and a substantive answer; mutation
  requests retain the empty-diff veto.
- Desktop relaunch: the signed native launcher now explicitly adds the managed
  checkout to `sys.path` before importing Jarvis. The repaired desktop app was
  relaunched successfully and served on `127.0.0.1:47821`.

### Verification

- Focused mission/critic evidence tests: **79 passed**.
- macOS bundle/launcher tests: **38 passed**.
- Expanded affected-area selection: **1,372 passed, 15 skipped, 7 failed**.
  The seven failures were outside the changed paths: three loopback OAuth tests
  could not bind sockets in the sandbox, while four existing contract tests
  reported unrelated society-route, restart-database, fixture-shape, and error-
  message mismatches.
- Frontend production build: **passed**. The build retained its existing
  chunk-size warnings; dependency audit reported six existing vulnerabilities
  (one low, three moderate, two high).
- `git diff --check`: **passed**.

### Remaining Gate

Completed in Sprint 0.5 below.

## Sprint 0.5 Completion — 2026-09-17

### Acceptance Test E — PASS

The original disposable Git repository was restored to its clean baseline. Its
single standard-library test first failed as intended because
`multiply(17, 43)` returned `60` instead of `731`.

Jarvis then ran `CodexDirectWorker` with backend fallback disabled and the
configured authenticated Codex executable. The worker:

1. reported backend `codex-cli` and the disposable repository as its working
   directory;
2. inspected only the disposable repository;
3. changed only `calculator.py`, replacing `a + b` with `a * b`;
4. ran `/usr/bin/python3 -m unittest -q` inside that repository;
5. reported `1 test passed (OK)`; and
6. completed without Terminal, Cursor, computer-use, or other GUI fallback.

An independent post-run test also passed. The Jarvis main checkout received no
unintended modification from the worker. The first Sprint 0.5 attempt used the
unavailable command `python`, made the correct code change, and honestly
reported the test as unverified; the disposable baseline was restored and the
acceptance run was repeated with the available system interpreter. This was a
test-environment command correction and required no production implementation.

### Final Acceptance Matrix

| Test | Final status |
| --- | --- |
| A — Basic Intelligence | **PASS** |
| B — Voice | **PASS** |
| C — Safe Tool Execution | **PASS** |
| D — Mission Execution | **PASS** |
| E — Codex Worker | **PASS** |
| F — Critic | **PASS** |
| G — Approval System | **PASS** |
| H — Local Model | **PARTIAL** |
| I — Cost / Telemetry | **PASS** |

Final summary: **8 PASS, 1 PARTIAL, 0 FAIL, 0 BLOCKED**.

### Final Verification

- Affected-area Python regression suite: **602 passed**.
- Frontend production build: **passed**; existing chunk-size warnings remain.
- Disposable Codex repository test: **passed** independently after the worker
  run.
- `git diff --check`: **passed**.
- No secrets or credential values are included in the tracked changes.

### Final Foundation Decision

**ACCEPT WITH CONDITIONS**

Resolved blockers: S0-004, S0-005, and S0-006. Tests D, E, and F now have live
passing evidence. Open conditions remain S0-001, S0-002, S0-003, S0-007,
S0-008, S0-009, and S0-010, plus the still-listed Sprint 1 preconditions. These
conditions are non-blocking for the baseline but must not be silently treated as
completed.

### Baseline Publication

- Baseline commit: the commit carrying the Sprint 0.5 remediation and this
  final validation record.
- Push target: `origin/main` on <https://github.com/stevensaint/jarvis>.
- Baseline tag: `jarvis-baseline-v0.1`.
- Sprint 1: **not started and not authorized by this validation**.

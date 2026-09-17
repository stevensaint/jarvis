# Julia naming inventory

Sprint 1 introduces **Julia** as the name of Steven's orchestration system and
**Jules** as its conversational identity. The accepted foundation remains the
upstream **Personal Jarvis** project and the Python/package namespace remains
`jarvis`.

## Inventory method

The inventory used tracked text files at baseline `jarvis-baseline-v0.1`
(`181f2c6e5a99efd9706665430a20d7b135a8a6f4`). Generated web assets were
excluded from the occurrence totals. The baseline contains approximately:

| Token | Tracked occurrences |
|---|---:|
| `PersonalJarvis` | 520 |
| `Personal Jarvis` | 1,056 |
| `Jarvis` | 9,699 |
| `jarvis` | 32,577 |

The large majority are in tests and the `jarvis/` source tree. Counts overlap:
for example, `Jarvis` is part of `PersonalJarvis`.

## Classification and disposition

| Surface | Examples | Classification | Sprint 1 disposition |
|---|---|---|---|
| Upstream provenance | repository URLs, copyright, NOTICE, contributor docs | Upstream identity | Preserve `PersonalJarvis` / `Personal Jarvis`. |
| Package and wire compatibility | `jarvis.*` imports, entry points, config keys, environment variables, database paths | Accepted technical contract | Preserve. Renaming would create broad upstream divergence and migration risk. |
| Historical evidence | bug reports, ADRs, Sprint 0/0.5 reports, screenshots, release notes | Historical record | Preserve verbatim. |
| Existing product UI and installers | window titles, app bundle/AUMID, shortcuts, command names | Accepted foundation | Defer any broad rename; it requires a separately specified compatibility migration. |
| New Sprint 1 intelligence components | worker registry, task profile, eligibility, routing, availability, outcome telemetry | Julia-owned | Name the subsystem and documentation Julia. Keep it under the compatible `jarvis` package root. |
| New conversational copy | references to the assistant speaking to Steven | Julia-owned identity | Use **Jules** when new copy is introduced. Sprint 1 adds no broad UI redesign. |

## Minimum safe migration

Sprint 1 therefore adds Julia-owned code beneath `jarvis/julia/` and uses
Julia/Jules in new documentation and diagnostics. It deliberately does not
rename imports, executable names, configuration keys, data roots, database
files, app identifiers, upstream URLs, or historical documents.

This boundary satisfies the naming requirement without a blind global rename
and keeps the accepted Personal Jarvis foundation mergeable with upstream.

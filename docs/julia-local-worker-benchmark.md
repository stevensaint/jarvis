# Julia Sprint 1 local worker benchmark

Date: 2026-09-17
Host: MacBook Air, Apple M3 (8 cores), 24 GB unified memory
Runtime: Ollama 0.34.1

## Purpose

This benchmark evaluates local models as replaceable **control-plane workers**:
task classification, hard-gated worker routing, insufficiency recognition, and
escalation. It does not evaluate them as general replacements for frontier
workers.

The pre-existing `qwen3.5:4b` was excluded as supervisor evidence by the Sprint
1 contract. Three stronger candidates appropriate to this host were installed
and measured. The model sizes and context families were checked against the
official [Qwen 3.5](https://ollama.com/library/qwen3.5),
[Qwen 3](https://ollama.com/library/qwen3), and
[Gemma 3](https://ollama.com/library/gemma3) Ollama catalogs.

## Method

The reproducible runner is `scripts/benchmark_julia_local_workers.py`. Each
model received the same seven temperature-zero, JSON-constrained cases:

1. arithmetic correctness;
2. exact instruction following;
3. structured output;
4. task classification;
5. routing from a worker matrix with hard gates before cost;
6. recognizing that no worker has a required capability;
7. escalating when the local controller lacks vision and computer-use.

The routing and escalation prompts include the governing hard-gate rule. This
matches the intended control-plane use: a local model receives a compact task
profile plus policy, rather than being expected to invent Julia's policy.

## Results

| Model | Correct | Cold first case | Average warm case | Output speed | Resident memory | Result |
|---|---:|---:|---:|---:|---:|---|
| `qwen3.5:9b` | 7/7 | 5.19 s | 1.14 s | 16.6–18.5 tok/s | 5.5 GB | Viable; preferred measured candidate |
| `qwen3:14b` | 7/7 | 6.10 s | 1.60 s | 10.7–12.1 tok/s | 9.6 GB | Viable; slower/larger reserve candidate |
| `gemma3:12b` | 6/7 | 7.00 s | 1.58 s | 12.4–14.1 tok/s | 8.9 GB | Not accepted; failed insufficiency gate |

`qwen3.5:9b` and `qwen3:14b` both correctly selected the only eligible worker,
returned `NONE` when capability was insufficient, and escalated the deliberately
unsuitable screenshot/computer-use task. `qwen3.5:9b` used roughly 4.1 GB less
resident memory and was about 29% faster on warm cases than `qwen3:14b`, so it is
the best measured control-plane candidate for this 24 GB host.

## Integration decision

Julia's registry already exposes local Ollama as an ordinary replaceable
`api_agent` worker. No model name is hardcoded into the routing architecture.
The configured Ollama model becomes the registry entry's model, so
`qwen3.5:9b` can be selected for a local control-plane role without changing
router code, and can later be replaced through configuration.

Sprint 1 does not silently change the user's active worker provider or model.
The benchmark establishes viability and installs the tested models; changing
the live worker configuration remains an explicit operator decision.

## Limits

- One bounded run per model, not a statistically powered model evaluation.
- JSON-constrained control-plane prompts only; no claim about broad coding or
  research superiority.
- Measurements apply to this M3/24 GB host and current Ollama/model builds.
- Memory is Ollama's resident-size report while loaded, not total system energy
  or long-duration memory pressure.

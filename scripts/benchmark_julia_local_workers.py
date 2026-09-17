#!/usr/bin/env python3
"""Bounded Sprint 1 benchmark for replaceable local control-plane workers."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from typing import Any


CASES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    (
        "arithmetic",
        "Return JSON only. Compute (37 * 12) - 16. Schema: {\"answer\": integer}.",
        {"answer": 428},
    ),
    (
        "instruction_following",
        "Return exactly this JSON object and nothing else: "
        '{"status":"ready","items":["alpha","beta"]}',
        {"status": "ready", "items": ["alpha", "beta"]},
    ),
    (
        "structured_output",
        "Return JSON only with keys route and confidence. Set route to local and "
        "confidence to 0.8.",
        {"route": "local", "confidence": 0.8},
    ),
    (
        "task_classification",
        "Return JSON only. Classify 'Implement and test a Python parser in the "
        "repository' as exactly one of coding, research, vision, summarization. "
        'Schema: {"category": string}.',
        {"category": "coding"},
    ),
    (
        "worker_routing",
        "Return JSON only. Eligibility rule: every required capability must be "
        "present in the worker capability list and quality must meet the minimum; "
        "do not infer unlisted capabilities. Task requires capabilities "
        "[coding,shell] and minimum quality 0.80. "
        "Workers: A capabilities=[coding], quality=.95, cost=.1; B "
        "capabilities=[coding,shell], quality=.85, cost=.4; C "
        "capabilities=[coding,shell], quality=.60, cost=.01. Exclude ineligible "
        'workers before considering cost. Schema: {"selected": "A"|"B"|"C"|"NONE"}.',
        {"selected": "B"},
    ),
    (
        "insufficient_capability",
        "Return JSON only. Task requires vision. Workers: A=[coding], "
        'B=[research]. Schema: {"selected":"A"|"B"|"NONE"}.',
        {"selected": "NONE"},
    ),
    (
        "escalation",
        "Return JSON only. Rule: if any required capability is absent, escalation "
        "is mandatory and capabilities must not be inferred. A local controller "
        "has capabilities [reasoning,structured_output]. The task requires "
        "[vision,computer_use] to inspect a screenshot and click a button. "
        'Schema: {"escalate": boolean}.',
        {"escalate": True},
    ),
)


def _chat(model: str, prompt: str) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "think": False,
            "format": "json",
            "keep_alive": "5m",
            "options": {"temperature": 0, "num_ctx": 4096},
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        return json.loads(response.read())


def _unload(model: str) -> None:
    body = json.dumps({"model": model, "keep_alive": 0}).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60):  # noqa: S310
        pass


def _resident_size(model: str) -> str | None:
    result = subprocess.run(  # noqa: S603
        ["ollama", "ps"],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines()[1:]:
        if line.split(maxsplit=1)[0] == model:
            columns = line.split()
            return " ".join(columns[2:4]) if len(columns) >= 4 else line
    return None


def benchmark(model: str) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for name, prompt, expected in CASES:
        started = time.monotonic()
        response = _chat(model, prompt)
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        raw = str(response.get("message", {}).get("content", ""))
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        cases.append(
            {
                "case": name,
                "passed": parsed == expected,
                "expected": expected,
                "actual": parsed if parsed is not None else raw[:500],
                "wall_ms": elapsed_ms,
                "load_ms": round(float(response.get("load_duration", 0)) / 1_000_000, 1),
                "prompt_tokens": int(response.get("prompt_eval_count", 0)),
                "output_tokens": int(response.get("eval_count", 0)),
                "tokens_per_second": round(
                    int(response.get("eval_count", 0))
                    / max(float(response.get("eval_duration", 1)) / 1_000_000_000, 1e-9),
                    2,
                ),
            }
        )
    resident = _resident_size(model)
    _unload(model)
    return {
        "model": model,
        "passed": sum(int(case["passed"]) for case in cases),
        "total": len(cases),
        "average_warm_wall_ms": round(
            sum(float(case["wall_ms"]) for case in cases[1:]) / max(len(cases) - 1, 1),
            1,
        ),
        "resident_size": resident,
        "cases": cases,
    }


def main() -> int:
    models = tuple(sys.argv[1:])
    if not models:
        raise SystemExit("usage: benchmark_julia_local_workers.py MODEL [MODEL ...]")
    print(json.dumps({"results": [benchmark(model) for model in models]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

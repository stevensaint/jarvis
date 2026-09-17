"""Last-resort advisory approve for an informational request answered as a prose
document — without weakening the Critic on earlier rounds.

A research / advisory request ("recherchiere AI-News", "research laptops", "plan
a trip") has a TEXT deliverable. When the worker writes that answer into a
Markdown / text REPORT, the diff is NON-empty and the adversarial CODE-critic
graded a German news essay with a code rubric (correctness/security/side_effects)
and demanded reachable web citations a web-less worker cannot produce — and even
called real 2026 model releases "hallucinated future claims" (a CRITIC-epistemics
gap that web_search on the worker cannot close) -> 3x revise ->
``critic_loop_exhausted`` (live mission 019ecb56, 2026-06-15).

The fix keeps the Critic in FULL control on every round (a web_search-sourced
report is approved on merit there), and only adds a LAST-RESORT net: when the
Critic would TERMINALLY fail a substantive prose research document — a one-shot
``reject``, or a ``revise`` on the final iteration — deliver the document instead
of a scary "three attempts failed" ERROR.

Anti-hallucination contract intact: ``informational_file_answer`` gates on the
REQUEST being informational AND a real, substantive, prose-only document on disk.
A code diff, a named-file/side-effect do-task, or a stub never qualifies.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from jarvis.missions.critic.runner import MAX_CRITIC_LOOPS, CriticRunner
from jarvis.missions.critic.verdict import (
    REQUIRED_AXES,
    CriticAxis,
    CriticVerdict,
    is_approval_valid,
)

_LAST_ITER = MAX_CRITIC_LOOPS - 1

# An English research request wrapped in spawn-meta (the German live prompt's
# classification is covered in test_stream_evidence.py).
_RESEARCH_PROMPT = (
    "Start a sub-agent to research the recent AI news of the last few years."
)
_CODE_PROMPT = "Implement a JSON config parser in config.py with tests."

_REPORT_BODY = (
    "# Recent AI news of the last few years\n\n"
    "AI development over the last few years shows a clear acceleration on "
    "several fronts: larger language models, multimodal systems, and the jump "
    "from chatbots to agentic workflows have dominated the headlines. This "
    "report summarises the most important breakthroughs, trends, and their "
    "context in a structured form, from the foundation models to the most "
    "recent regulatory debates."
)


def _prose_diff(body: str, path: str = "AI-news-report.md") -> str:
    plus = "\n".join("+" + ln for ln in body.splitlines())
    return (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\nindex 0000000..4957e1f\n"
        f"--- /dev/null\n+++ b/{path}\n"
        f"@@ -0,0 +1,{len(body.splitlines())} @@\n{plus}\n"
    )


def _critic_verdict(kind: str) -> CriticVerdict:
    """A non-approve critic verdict (the failure this net must rescue)."""
    fail = CriticAxis(
        status="fail", evidence=["correctness: unverifiable 2026 model claims"]
    )
    return CriticVerdict(
        verdict=kind,
        axes={ax: fail for ax in REQUIRED_AXES},
        issues=[],
        correction_instruction="add reachable sources for every dated claim",
        summary="report cites unverifiable future-model releases",
        summary_de="bericht nicht verifizierbar",  # i18n-allow: test fixture
        confidence=0.9,
        suggested_next_action="retry",
    )


class _FakeCritic(CriticRunner):
    """CriticRunner whose LLM round is replaced by a canned verdict (no spawn)."""

    def __init__(self, verdict: CriticVerdict) -> None:
        super().__init__()
        self._fake = verdict

    async def _invoke_once(self, **_kwargs: object) -> CriticVerdict:  # type: ignore[override]
        return self._fake


async def _run(
    runner: CriticRunner, *, prompt: str, diff: str, iteration: int, tmp: Path
) -> CriticVerdict:
    return await runner.run(
        mission_prompt=prompt,
        worker_diff=diff,
        worker_log='{"type":"result","result":"Report written."}',
        prior_reflections="",
        iteration=iteration,
        worktree=tmp,
        env={},
        _capability_check=False,
    )


@pytest.mark.asyncio
async def test_verified_readonly_file_answer_approves_without_llm_retry(
    tmp_path: Path,
) -> None:
    """A named input file is not an output artefact when the task only reads it."""
    stream = "\n".join(
        [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Read", "input": {}}
                        ]
                    },
                }
            ),
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "result": "First heading: Your personal AI ecosystem.",
                }
            ),
        ]
    )
    verdict = await _FakeCritic(_critic_verdict("revise")).run(
        mission_prompt=(
            "Using only the configured OpenAI provider, read README.md and "
            "report its first heading. Do not modify files."
        ),
        worker_diff="",
        worker_log=stream,
        prior_reflections="",
        iteration=0,
        worktree=tmp_path,
        env={},
        _capability_check=False,
    )
    assert verdict.verdict == "approve"
    assert verdict.summary.startswith("Informational request answered")


@pytest.mark.asyncio
async def test_readonly_request_does_not_approve_mutating_tool_evidence(
    tmp_path: Path,
) -> None:
    stream = "\n".join(
        [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Write", "input": {}}
                        ]
                    },
                }
            ),
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "result": "First heading: unverified after a write call.",
                }
            ),
        ]
    )
    verdict = await _FakeCritic(_critic_verdict("revise")).run(
        mission_prompt="Read README.md and report its first heading.",
        worker_diff="",
        worker_log=stream,
        prior_reflections="",
        iteration=0,
        worktree=tmp_path,
        env={},
        _capability_check=False,
    )
    assert verdict.verdict == "revise"


@pytest.mark.asyncio
async def test_last_resort_approves_research_report_on_final_revise(
    tmp_path: Path,
) -> None:
    # Critic revises on the FINAL iteration -> would become critic_loop_exhausted.
    # The net delivers the substantive prose report instead.
    verdict = await _run(
        _FakeCritic(_critic_verdict("revise")),
        prompt=_RESEARCH_PROMPT,
        diff=_prose_diff(_REPORT_BODY),
        iteration=_LAST_ITER,
        tmp=tmp_path,
    )
    assert verdict.verdict == "approve"
    assert verdict.suggested_next_action != "retry"
    assert is_approval_valid(verdict)


@pytest.mark.asyncio
async def test_last_resort_approves_research_report_on_reject(tmp_path: Path) -> None:
    # A one-shot terminal `reject` of a prose research document is also rescued,
    # even on iteration 0 (reject ends the mission immediately).
    verdict = await _run(
        _FakeCritic(_critic_verdict("reject")),
        prompt=_RESEARCH_PROMPT,
        diff=_prose_diff(_REPORT_BODY),
        iteration=0,
        tmp=tmp_path,
    )
    assert verdict.verdict == "approve"


@pytest.mark.asyncio
async def test_critic_keeps_authority_on_early_revise(tmp_path: Path) -> None:
    # On a NON-final iteration a `revise` passes through untouched — the worker
    # gets another round and a web_search-sourced report can be approved on merit
    # next time. The net must NOT short-circuit the critic's chances.
    verdict = await _run(
        _FakeCritic(_critic_verdict("revise")),
        prompt=_RESEARCH_PROMPT,
        diff=_prose_diff(_REPORT_BODY),
        iteration=0,
        tmp=tmp_path,
    )
    assert verdict.verdict == "revise"


@pytest.mark.asyncio
async def test_last_resort_does_not_rescue_code_diff(tmp_path: Path) -> None:
    # A real code change keeps the critic's terminal verdict — the net is only
    # for prose research documents, never code.
    verdict = await _run(
        _FakeCritic(_critic_verdict("revise")),
        prompt=_CODE_PROMPT,
        diff=_prose_diff("def parse():\n    return {}\n", path="config.py"),
        iteration=_LAST_ITER,
        tmp=tmp_path,
    )
    assert verdict.verdict == "revise"


@pytest.mark.asyncio
async def test_last_resort_does_not_rescue_stub_document(tmp_path: Path) -> None:
    # A stub/skeleton document is not a real answer — the critic's verdict stands.
    verdict = await _run(
        _FakeCritic(_critic_verdict("revise")),
        prompt=_RESEARCH_PROMPT,
        diff=_prose_diff("# Report\n\nInhalt folgt.\n"),  # i18n-allow: stub fixture
        iteration=_LAST_ITER,
        tmp=tmp_path,
    )
    assert verdict.verdict == "revise"

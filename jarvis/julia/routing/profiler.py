"""Compact deterministic task profiling for delegated mission steps."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .contracts import AuthorizationContract, PrivacyClass, TaskProfile


_CATEGORY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("coding", re.compile(r"\b(code|coding|implement|refactor|bug|test|repository|repo)\b", re.I)),
    ("research", re.compile(r"\b(research|compare|sources?|investigate|web)\b", re.I)),
    ("vision", re.compile(r"\b(image|screenshot|vision|photo|diagram)\b", re.I)),
    ("summarization", re.compile(r"\b(summarize|summary|condense)\b", re.I)),
)


def profile_task(
    *,
    objective_id: str,
    task_id: str,
    objective: str,
    authorization: AuthorizationContract,
    needs_repository: bool,
    declared_tools: Iterable[str] = (),
    minimum_quality: float = 0.7,
    privacy: PrivacyClass = PrivacyClass.PRIVATE_CLOUD,
) -> TaskProfile:
    """Derive a profile from structured step fields plus bounded prompt signals.

    Repository need and declared tools come from the mission plan rather than
    free-form interpretation. Prompt matching supplies only the task category
    and its semantic capability.
    """
    category = "reasoning"
    for candidate, pattern in _CATEGORY_RULES:
        if pattern.search(objective):
            category = candidate
            break
    capabilities = {category if category != "reasoning" else "reasoning"}
    tools = {str(tool).strip().lower() for tool in declared_tools if str(tool).strip()}
    modes: set[str] = set()
    if needs_repository:
        capabilities.add("coding")
        tools.update({"filesystem", "shell"})
        modes.add("repository")
    return TaskProfile(
        objective_id=objective_id,
        task_id=task_id,
        task_category=category,
        objective=objective,
        required_capabilities=frozenset(capabilities),
        required_tools=frozenset(tools),
        required_execution_modes=frozenset(modes),
        privacy=privacy,
        minimum_quality=minimum_quality,
        estimated_context_tokens=max(256, len(objective) // 3),
        authorization=authorization,
    )

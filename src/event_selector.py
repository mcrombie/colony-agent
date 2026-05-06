"""Select colony decisions with OpenAI."""

from __future__ import annotations

from typing import Any

from src.config import load_local_env
from src.constants import CHAOS_GODS_EVENT_TYPE, PRESERVE_RESOURCES_ACTION_TYPE
from src.openai_selector import (
    OpenAIAPICallError,
    choose_leadership_action_with_openai,
    choose_world_event_with_openai,
)


def choose_world_event(
    state: dict[str, Any],
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Choose a world event with OpenAI, failing loudly when config is missing."""
    load_local_env()
    try:
        return choose_world_event_with_openai(state, environment=environment)
    except OpenAIAPICallError as exc:
        print(
            "::warning title=OpenAI deity selector failed::"
            f"{_escape_github_annotation(str(exc))}"
        )
        return {
            "world_event": CHAOS_GODS_EVENT_TYPE,
            "severity": 3,
            "reasoning": "The oracle failed, so the chaos gods answered instead.",
        }


def choose_leadership_action(
    state: dict[str, Any],
    world_event: str | dict[str, Any],
) -> str:
    """Choose the colony president's response with OpenAI."""
    load_local_env()
    try:
        return choose_leadership_action_with_openai(state, world_event)
    except OpenAIAPICallError as exc:
        print(
            "::warning title=OpenAI president selector failed::"
            f"{_escape_github_annotation(str(exc))}"
        )
        return PRESERVE_RESOURCES_ACTION_TYPE


def choose_event(state: dict[str, Any]) -> str:
    """Backward-compatible wrapper for older callers."""
    return choose_world_event(state)["world_event"]


def _escape_github_annotation(message: str) -> str:
    return (
        message.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
        .replace(",", "%2C")
    )

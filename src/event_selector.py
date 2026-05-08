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

WOLF_ATTACK_COOLDOWN_DAYS = 7
WOLF_ATTACK_COOLDOWN_BYPASS_SEVERITY = 5


def choose_world_event(
    state: dict[str, Any],
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Choose a world event with OpenAI, failing loudly when config is missing."""
    load_local_env()
    try:
        return _apply_wolf_attack_cooldown(
            choose_world_event_with_openai(state, environment=environment),
            state,
        )
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


def _apply_wolf_attack_cooldown(
    decision: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    if decision.get("world_event") != "wolf_attack":
        return decision

    if int(decision.get("severity") or 3) >= WOLF_ATTACK_COOLDOWN_BYPASS_SEVERITY:
        return decision

    recent_wolf_day = _most_recent_wolf_attack_day(state)
    current_day = state.get("day", 1)
    if recent_wolf_day is None or current_day - recent_wolf_day > WOLF_ATTACK_COOLDOWN_DAYS:
        return decision

    return {
        "world_event": "quiet_day",
        "reasoning": (
            "Wolves attacked recently, so the pack does not strike again today. "
            f"Original selection was wolf_attack: {decision.get('reasoning', '')}"
        ),
    }


def _most_recent_wolf_attack_day(state: dict[str, Any]) -> int | None:
    for record in reversed(state.get("event_log", [])):
        if (record.get("world_event") or record.get("event_type")) == "wolf_attack":
            return record.get("day")

    return None

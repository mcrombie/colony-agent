"""Mechanical effects for colony events."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.constants import ALLOWED_EVENT_TYPES, FAILED_CONSTRUCTION_EVENT_TYPE

LIMITED_STATS = ("morale", "security", "health")
NON_NEGATIVE_STATS = ("population", "food", "wood")


def clamp_state(state: dict[str, Any]) -> dict[str, Any]:
    """Clamp state values to their allowed ranges."""
    clamped = deepcopy(state)

    for stat in LIMITED_STATS:
        clamped[stat] = max(0, min(10, clamped[stat]))

    for stat in NON_NEGATIVE_STATS:
        clamped[stat] = max(0, clamped[stat])

    return clamped


def apply_event(state: dict[str, Any], event_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one event and return the next state plus an event record."""
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"Unknown event type: {event_type}")

    before = deepcopy(state)
    after = deepcopy(state)
    event_type = _resolve_event_type(before, event_type)
    effects = _effects_for_event(before, event_type)

    for stat, amount in effects.items():
        after[stat] += amount

    after = clamp_state(after)
    after["day"] = before["day"] + 1

    event_record = {
        "day": before["day"],
        "event_type": event_type,
        "effects": _actual_effects(before, after, effects),
        "summary": summarize_event(before, event_type),
    }
    after.setdefault("event_log", []).append(event_record)

    return after, event_record


def summarize_event(state: dict[str, Any], event_type: str) -> str:
    """Create a short factual summary for the event log."""
    summaries = {
        "good_harvest": "A strong harvest added food to the stores.",
        "poor_harvest": "A poor harvest reduced food and dampened morale.",
        "construction": "Colonists spent wood to strengthen the settlement.",
        "illness": "Illness spread through several homes.",
        "dispute": "A dispute unsettled the colony.",
        "quiet_day": "The day passed quietly while food stores were used.",
        "chaos_gods": "The chaos gods struck the colony when the oracle went silent.",
        "failed_construction": "Construction failed because the colony lacked enough wood.",
    }

    if event_type == "discovery":
        details = [
            "fresh water north of camp",
            "useful clay near the riverbank",
            "old trail markers beyond the fields",
        ]
        detail = details[state["day"] % len(details)]
        return f"Scouts discovered {detail}."

    return summaries[event_type]


def _effects_for_event(state: dict[str, Any], event_type: str) -> dict[str, int]:
    if event_type == "good_harvest":
        return {"food": 15, "morale": 1}

    if event_type == "poor_harvest":
        return {"food": -10, "morale": -1}

    if event_type == "construction":
        return {"wood": -10, "security": 1, "morale": 1}

    if event_type == "failed_construction":
        return {}

    if event_type == "illness":
        effects = {"health": -1, "morale": -1}
        if state["health"] <= 3:
            effects["population"] = -1
        return effects

    if event_type == "dispute":
        return {"morale": -2, "security": -1}

    if event_type == "discovery":
        return {"morale": 1}

    if event_type == "quiet_day":
        return {"food": -5}

    if event_type == "chaos_gods":
        return {"health": -1, "security": -1, "morale": -1}

    raise ValueError(f"Unknown event type: {event_type}")


def _resolve_event_type(state: dict[str, Any], event_type: str) -> str:
    if event_type == "construction" and state["wood"] < 10:
        return FAILED_CONSTRUCTION_EVENT_TYPE

    return event_type


def _actual_effects(
    before: dict[str, Any],
    after: dict[str, Any],
    intended_effects: dict[str, int],
) -> dict[str, int]:
    """Report effects after clamping so the event log matches the saved state."""
    return {
        stat: after[stat] - before[stat]
        for stat in intended_effects
        if after[stat] - before[stat] != 0
    }

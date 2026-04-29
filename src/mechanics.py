"""Mechanical effects for colony events and leadership actions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.constants import (
    ALLOWED_LEADERSHIP_ACTION_TYPES,
    ALLOWED_WORLD_EVENT_TYPES,
    FAILED_STRENGTHEN_DEFENSES_ACTION_TYPE,
)

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


def apply_day(
    state: dict[str, Any],
    world_event: str,
    leadership_action: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one day and return the next state plus an event record."""
    if world_event not in ALLOWED_WORLD_EVENT_TYPES:
        raise ValueError(f"Unknown world event: {world_event}")

    if leadership_action not in ALLOWED_LEADERSHIP_ACTION_TYPES:
        raise ValueError(f"Unknown leadership action: {leadership_action}")

    before = deepcopy(state)
    after = deepcopy(state)
    leadership_action = _resolve_leadership_action(before, leadership_action)

    for stat, amount in _effects_for_world_event(before, world_event).items():
        after[stat] += amount

    for stat, amount in _effects_for_leadership_action(before, leadership_action).items():
        after[stat] += amount

    after = clamp_state(after)
    survival_effects = _apply_daily_food_consumption(after, leadership_action)
    after = clamp_state(after)
    after["day"] = before["day"] + 1

    event_record = {
        "day": before["day"],
        "event_type": world_event,
        "world_event": world_event,
        "leadership_action": leadership_action,
        "effects": _actual_effects(before, after),
        "survival_effects": survival_effects,
        "summary": summarize_day(before, world_event, leadership_action),
    }
    after.setdefault("event_log", []).append(event_record)

    return after, event_record


def apply_event(state: dict[str, Any], event_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Backward-compatible wrapper for older single-event callers."""
    if event_type == "construction":
        return apply_day(state, "quiet_day", "strengthen_defenses")

    return apply_day(state, event_type, "preserve_resources")


def summarize_day(
    state: dict[str, Any],
    world_event: str,
    leadership_action: str,
) -> str:
    """Create a short factual summary for the event log."""
    event_summaries = {
        "good_harvest": "A strong harvest favored Blergen.",
        "poor_harvest": "A poor harvest strained Blergen's stores.",
        "illness": "Illness spread through several homes.",
        "dispute": "A dispute unsettled the colony.",
        "quiet_day": "No significant outside event disturbed the colony.",
        "chaos_gods": "The chaos gods struck the colony when the oracle went silent.",
    }
    action_summaries = {
        "preserve_resources": "The president ordered the colony to preserve resources.",
        "ration_food": "The president ordered tighter food rationing.",
        "gather_wood": "The president sent work crews to gather wood.",
        "expand_fields": "The president directed labor toward the fields.",
        "strengthen_defenses": "The president spent wood to strengthen the settlement.",
        "failed_strengthen_defenses": (
            "The president tried to strengthen the settlement, but there was not enough wood."
        ),
        "tend_the_sick": "The president organized care for the sick.",
        "mediate_dispute": "The president worked to mediate local tensions.",
        "send_scouts": "The president sent scouts beyond the settlement.",
        "hold_festival": "The president called a festival to steady morale.",
    }

    if world_event == "discovery":
        event_summary = f"Scouts discovered {_discovery_detail(state)}."
    else:
        event_summary = event_summaries[world_event]

    return f"{event_summary} {action_summaries[leadership_action]}"


def daily_food_needed(population: int, leadership_action: str = "preserve_resources") -> int:
    """Return how much food the colony needs to eat today."""
    if population <= 0:
        return 0

    base_need = max(1, population // 20)
    if leadership_action == "ration_food":
        return max(1, base_need - 2)

    return base_need


def _effects_for_world_event(state: dict[str, Any], world_event: str) -> dict[str, int]:
    if world_event == "good_harvest":
        return {"food": 15, "morale": 1}

    if world_event == "poor_harvest":
        return {"food": -10, "morale": -1}

    if world_event == "illness":
        effects = {"health": -1, "morale": -1}
        if state["health"] <= 3:
            effects["population"] = -1
        return effects

    if world_event == "dispute":
        return {"morale": -2, "security": -1}

    if world_event == "discovery":
        return {"morale": 1}

    if world_event == "quiet_day":
        return {}

    if world_event == "chaos_gods":
        return {"health": -1, "security": -1, "morale": -1}

    raise ValueError(f"Unknown world event: {world_event}")


def _effects_for_leadership_action(
    state: dict[str, Any],
    leadership_action: str,
) -> dict[str, int]:
    if leadership_action == "preserve_resources":
        return {}

    if leadership_action == "ration_food":
        return {"morale": -1}

    if leadership_action == "gather_wood":
        return {"wood": 10}

    if leadership_action == "expand_fields":
        return {"food": 8}

    if leadership_action == "strengthen_defenses":
        return {"wood": -10, "security": 1, "morale": 1}

    if leadership_action == "failed_strengthen_defenses":
        return {}

    if leadership_action == "tend_the_sick":
        return {"food": -3, "health": 1, "morale": 1}

    if leadership_action == "mediate_dispute":
        return {"morale": 1, "security": 1}

    if leadership_action == "send_scouts":
        return {"wood": 5, "morale": 1}

    if leadership_action == "hold_festival":
        return {"food": -8, "morale": 2}

    raise ValueError(f"Unknown leadership action: {leadership_action}")


def _apply_daily_food_consumption(
    state: dict[str, Any],
    leadership_action: str,
) -> dict[str, int]:
    food_before = state["food"]
    population_before = state["population"]
    food_needed = daily_food_needed(population_before, leadership_action)

    if food_needed == 0:
        return {}

    if food_before >= food_needed:
        state["food"] -= food_needed
    else:
        shortage = food_needed - food_before
        state["food"] = 0
        state["population"] -= max(1, shortage)

    return {
        stat: state[stat] - before
        for stat, before in {
            "food": food_before,
            "population": population_before,
        }.items()
        if state[stat] - before != 0
    }


def _resolve_leadership_action(
    state: dict[str, Any],
    leadership_action: str,
) -> str:
    if leadership_action == "strengthen_defenses" and state["wood"] < 10:
        return FAILED_STRENGTHEN_DEFENSES_ACTION_TYPE

    return leadership_action


def _discovery_detail(state: dict[str, Any]) -> str:
    details = [
        "fresh water north of camp",
        "useful clay near the riverbank",
        "old trail markers beyond the fields",
    ]
    return details[state["day"] % len(details)]


def _actual_effects(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, int]:
    """Report effects after clamping so the event log matches the saved state."""
    return {
        stat: after[stat] - before[stat]
        for stat in ("population", "food", "wood", "morale", "security", "health")
        if after[stat] - before[stat] != 0
    }

"""Narrative text for daily colony history."""

from __future__ import annotations

from typing import Any

EVENT_OPENINGS = {
    "good_harvest": "A good harvest lifted the colony's spirits",
    "poor_harvest": "A poor harvest strained the colony's stores",
    "construction": "A construction effort reinforced the settlement",
    "illness": "Illness moved through the colony",
    "dispute": "A dispute unsettled the day's work",
    "discovery": "A discovery gave the colony something new to discuss",
    "quiet_day": "The colony passed a quiet day",
    "chaos_gods": "The chaos gods struck the colony",
    "failed_construction": "The planned construction work failed",
}


def write_daily_entry(
    state_before: dict[str, Any],
    event_record: dict[str, Any],
    state_after: dict[str, Any],
) -> str:
    """Return one restrained paragraph for history.md."""
    colony_name = state_before["colony_name"]
    day = event_record["day"]
    event_type = event_record["event_type"]
    effects_text = _describe_effects(event_record["effects"])

    if effects_text:
        body = f"{EVENT_OPENINGS[event_type]}, {effects_text}."
    else:
        body = f"{EVENT_OPENINGS[event_type]}."

    closing = _closing_sentence(state_after)
    return f"Day {day} - {colony_name}:\n{body} {closing}\n"


def _describe_effects(effects: dict[str, int]) -> str:
    if not effects:
        return ""

    pieces = []
    for stat, amount in effects.items():
        direction = "increased" if amount > 0 else "reduced"
        pieces.append(f"{direction} {stat} by {abs(amount)}")

    if len(pieces) == 1:
        return pieces[0]

    return ", ".join(pieces[:-1]) + f", and {pieces[-1]}"


def _closing_sentence(state: dict[str, Any]) -> str:
    if state["food"] < 30:
        return "Hunger is becoming the settlement's most urgent worry."

    if state["health"] < 4:
        return "The settlement survives, but sickness is wearing people down."

    if state["morale"] < 4:
        return "The settlement survives, though confidence is thinning."

    return "The settlement endures into another morning."

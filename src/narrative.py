"""Narrative text for daily colony history."""

from __future__ import annotations

from typing import Any

EVENT_OPENINGS = {
    "good_harvest": "A good harvest lifted the colony's spirits",
    "poor_harvest": "A poor harvest strained the colony's stores",
    "illness": "Illness moved through the colony",
    "dispute": "A dispute unsettled the day's work",
    "discovery": "A discovery gave the colony something new to discuss",
    "quiet_day": "No great outside event disturbed Blergen",
    "chaos_gods": "The chaos gods struck the colony",
}

ACTION_PHRASES = {
    "preserve_resources": "the president told the colonists to preserve resources",
    "ration_food": "the president ordered tighter food rationing",
    "gather_wood": "the president sent crews out to gather wood",
    "expand_fields": "the president directed labor toward the fields",
    "strengthen_defenses": "the president spent wood to strengthen the settlement",
    "failed_strengthen_defenses": (
        "the president tried to strengthen the settlement, but there was not enough wood"
    ),
    "tend_the_sick": "the president organized care for the sick",
    "mediate_dispute": "the president worked to mediate the tension",
    "send_scouts": "the president sent scouts beyond the settlement",
    "hold_festival": "the president called a festival to steady morale",
}


def write_daily_entry(
    state_before: dict[str, Any],
    event_record: dict[str, Any],
    state_after: dict[str, Any],
) -> str:
    """Return one restrained paragraph for history.md."""
    colony_name = state_before["colony_name"]
    day = event_record["day"]
    world_event = event_record["world_event"]
    leadership_action = event_record["leadership_action"]
    effects_text = _describe_effects(event_record["effects"])

    body = (
        f"{EVENT_OPENINGS[world_event]}, and "
        f"{ACTION_PHRASES[leadership_action]}"
    )
    if effects_text:
        body = f"{body}; the day's changes {effects_text}."
    else:
        body = f"{body}."

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
    if state["population"] < 80:
        return "The loss of people is beginning to define the settlement's future."

    if state["food"] <= 0:
        return "With the stores empty, hunger is now the colony's ruling fact."

    if state["food"] < 30:
        return "Hunger is becoming the settlement's most urgent worry."

    if state["health"] < 4:
        return "The settlement survives, but sickness is wearing people down."

    if state["morale"] < 4:
        return "The settlement survives, though confidence is thinning."

    return "The settlement endures into another morning."

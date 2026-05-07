"""Mechanical effects for colony events and leadership actions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.constants import (
    ALLOWED_LEADERSHIP_ACTION_TYPES,
    ALLOWED_WORLD_EVENT_TYPES,
    EMPTY_COLONY_EVENT_TYPE,
    FAILED_STRENGTHEN_DEFENSES_ACTION_TYPE,
    NO_ACTION_ACTION_TYPE,
)
from src.environment import environment_for_day, sync_calendar_state
from src.people import (
    apply_daily_food_status,
    apply_daily_people_events,
    apply_population_loss_to_people,
    ensure_people_exist,
    sync_derived_colony_stats,
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
    world_event: str | dict[str, Any],
    leadership_action: str,
    environment: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one day and return the next state plus an event record."""
    event_decision = _normalize_world_event(world_event)
    world_event_type = event_decision["world_event"]
    event_details = _event_details(event_decision)
    if world_event_type not in ALLOWED_WORLD_EVENT_TYPES:
        raise ValueError(f"Unknown world event: {world_event_type}")

    if leadership_action not in ALLOWED_LEADERSHIP_ACTION_TYPES:
        raise ValueError(f"Unknown leadership action: {leadership_action}")

    before = sync_calendar_state(ensure_people_exist(state))
    after = deepcopy(before)
    environment = environment or environment_for_day(before["day"])
    weather = environment["weather"]
    leadership_action = _resolve_leadership_action(before, leadership_action)

    weather_effects = _effects_for_weather(weather)
    for stat, amount in weather_effects.items():
        after[stat] += amount

    world_effects = _effects_for_world_event(
        before,
        world_event_type,
        event_details=event_details,
        leadership_action=leadership_action,
    )
    for stat, amount in world_effects.items():
        after[stat] += amount

    leadership_effects = _effects_for_leadership_action(before, leadership_action)
    for stat, amount in leadership_effects.items():
        after[stat] += amount

    after = clamp_state(after)
    status_targets = _changed_status_targets(before, after)
    population_before_survival = after["population"]
    survival_effects = _apply_daily_food_consumption(after, leadership_action)
    after = clamp_state(after)
    people_events = _apply_people_effects(
        before=before,
        after=after,
        world_event=world_event_type,
        event_details=event_details,
        leadership_action=leadership_action,
        population_before_survival=population_before_survival,
        survival_effects=survival_effects,
    )
    _sync_people_status_to_colony_targets(
        after,
        status_targets=status_targets,
        protected_ids=_people_event_person_ids(people_events),
    )
    sync_derived_colony_stats(after)
    after["day"] = before["day"] + 1
    sync_calendar_state(after)

    event_record = {
        "day": before["day"],
        "year": before["year"],
        "date": environment["date"],
        "weather": weather,
        "weather_effects": weather_effects,
        "event_type": world_event_type,
        "world_event": world_event_type,
        "event_details": event_details,
        "leadership_action": leadership_action,
        "president": deepcopy(before.get("president")),
        "effects": _actual_effects(before, after),
        "survival_effects": survival_effects,
        "people_events": people_events,
        "summary": summarize_day(
            before,
            world_event_type,
            leadership_action,
            event_details=event_details,
            weather=weather,
        ),
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
    *,
    event_details: dict[str, Any] | None = None,
    weather: dict[str, Any] | None = None,
) -> str:
    """Create a short factual summary for the event log."""
    event_details = event_details or {}
    event_summaries = {
        "good_harvest": "A strong harvest favored Blergen.",
        "poor_harvest": "A poor harvest strained Blergen's stores.",
        "illness": "Illness spread through several homes.",
        "dispute": "A dispute unsettled the colony.",
        "quiet_day": "No major world event overtook the colony.",
        "storm": f"A severity {event_details.get('severity', 3)} storm struck Blergen.",
        "wolf_attack": (
            f"A severity {event_details.get('severity', 3)} wolf attack hit the settlement."
        ),
        "chaos_gods": "The chaos gods struck the colony when the oracle went silent.",
        "empty_colony": "No colonists remained in Blergen.",
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
        "no_action": "No one remained to give orders or carry them out.",
    }

    if world_event == "discovery":
        event_summary = f"Scouts discovered {_discovery_detail(state)}."
    else:
        event_summary = event_summaries[world_event]

    weather_summary = ""
    if weather:
        weather_summary = f" Weather: {weather['summary']}"

    return f"{event_summary}{weather_summary} {action_summaries[leadership_action]}"


def daily_food_needed(population: int, leadership_action: str = "preserve_resources") -> int:
    """Return how much food the colony needs to eat today."""
    return max(0, population)


def _food_for_population_days(
    state: dict[str, Any],
    days: int,
    *,
    minimum: int,
) -> int:
    return max(minimum, daily_food_needed(state["population"]) * days)


def _normalize_world_event(world_event: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(world_event, str):
        return {"world_event": world_event}

    return deepcopy(world_event)


def _event_details(event_decision: dict[str, Any]) -> dict[str, Any]:
    details = {
        key: value
        for key, value in event_decision.items()
        if key not in {"world_event", "reasoning"} and value is not None
    }
    if event_decision["world_event"] in {"storm", "wolf_attack"}:
        details["severity"] = max(1, min(5, int(details.get("severity", 3))))

    return details


def _effects_for_weather(weather: dict[str, Any]) -> dict[str, int]:
    condition = weather["condition"]
    severity = weather.get("severity", 1)
    if condition in {"clear", "clear_cold", "overcast", "mild"}:
        return {}

    if condition == "snow":
        return {"wood": -1}

    if condition == "hard_freeze":
        return {"health": -1}

    if condition == "sleet":
        return {"wood": -1, "morale": -1}

    if condition == "winter_storm":
        return {"wood": -max(1, severity - 2), "morale": -1}

    if condition in {"rain", "mud"}:
        return {"morale": -1}

    if condition in {"wind", "thunderstorm"}:
        return {"security": -1}

    if condition == "dry_heat":
        return {"food": -2, "health": -1}

    if condition in {"hot", "cold_rain", "early_frost"}:
        return {"health": -1}

    return {}


def _effects_for_world_event(
    state: dict[str, Any],
    world_event: str,
    *,
    event_details: dict[str, Any],
    leadership_action: str,
) -> dict[str, int]:
    if world_event == "good_harvest":
        return {"food": _food_for_population_days(state, 5, minimum=35), "morale": 1}

    if world_event == "poor_harvest":
        return {"food": -_food_for_population_days(state, 1, minimum=10), "morale": -1}

    if world_event == "illness":
        effects = {"health": -1, "morale": -1}
        if state["health"] <= 3:
            effects["population"] = -1
        return effects

    if world_event == "dispute":
        return {"morale": -2, "security": -1}

    if world_event == "discovery":
        return {"morale": 1}

    if world_event == "storm":
        return _effects_for_storm(event_details.get("severity", 3), state)

    if world_event == "wolf_attack":
        return _effects_for_wolf_attack(
            event_details.get("severity", 3),
            state,
            leadership_action,
        )

    if world_event == "quiet_day":
        return {}

    if world_event == "chaos_gods":
        return {"health": -1, "security": -1, "morale": -1}

    if world_event == EMPTY_COLONY_EVENT_TYPE:
        return {}

    raise ValueError(f"Unknown world event: {world_event}")


def _effects_for_storm(severity: int, state: dict[str, Any]) -> dict[str, int]:
    severity = max(1, min(5, severity))
    effects_by_severity = {
        1: {"morale": -1},
        2: {"food": -2, "morale": -1},
        3: {"food": -4, "wood": -2, "health": -1},
        4: {"food": -6, "wood": -4, "health": -1, "morale": -1},
        5: {"food": -8, "wood": -6, "health": -2, "morale": -2},
    }
    effects = deepcopy(effects_by_severity[severity])
    if severity == 5 and state["health"] <= 3:
        effects["population"] = -1

    return effects


def _effects_for_wolf_attack(
    severity: int,
    state: dict[str, Any],
    leadership_action: str,
) -> dict[str, int]:
    severity = max(1, min(5, severity))
    if leadership_action == "strengthen_defenses":
        severity = max(1, severity - 1)

    effects_by_severity = {
        1: {"security": -1, "morale": -1},
        2: {"security": -1, "morale": -1, "food": -2},
        3: {"security": -2, "morale": -2, "health": -1},
        4: {"security": -2, "morale": -2, "health": -1, "population": -1},
        5: {"security": -3, "morale": -3, "health": -2, "population": -2},
    }
    effects = deepcopy(effects_by_severity[severity])
    if severity == 3 and state["security"] <= 4:
        effects["population"] = -1

    return effects


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
        return {"food": _food_for_population_days(state, 3, minimum=21)}

    if leadership_action == "strengthen_defenses":
        return {"wood": -10, "security": 1, "morale": 1}

    if leadership_action == "failed_strengthen_defenses":
        return {}

    if leadership_action == "tend_the_sick":
        care_food = max(3, daily_food_needed(state["population"]) // 2)
        return {"food": -care_food, "health": 1, "morale": 1}

    if leadership_action == "mediate_dispute":
        return {"morale": 1, "security": 1}

    if leadership_action == "send_scouts":
        return {"wood": 5, "morale": 1}

    if leadership_action == "hold_festival":
        return {"food": -_food_for_population_days(state, 1, minimum=8), "morale": 2}

    if leadership_action == NO_ACTION_ACTION_TYPE:
        return {}

    raise ValueError(f"Unknown leadership action: {leadership_action}")


def _apply_daily_food_consumption(
    state: dict[str, Any],
    leadership_action: str,
) -> dict[str, int]:
    food_before = state["food"]
    food_needed = daily_food_needed(state["population"], leadership_action)

    if food_needed == 0:
        return {}

    food_consumed = min(food_before, food_needed)
    missed_rations = food_needed - food_consumed
    state["food"] = food_before - food_consumed

    effects = {}
    if food_consumed:
        effects["food"] = -food_consumed
    if missed_rations:
        effects["missed_rations"] = missed_rations

    return effects


def _changed_status_targets(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, int]:
    return {
        stat: after[stat]
        for stat in ("health", "morale")
        if after[stat] - before[stat] != 0
    }


def _sync_people_status_to_colony_targets(
    state: dict[str, Any],
    *,
    status_targets: dict[str, int],
    protected_ids: set[str],
) -> None:
    """Adjust non-featured colonists so derived stats keep aggregate effects."""
    if not status_targets or "people" not in state:
        return

    living_people = []
    for person in state["people"]:
        status = person.get("status", {})
        if not status.get("alive", True):
            continue
        living_people.append(person)

    if not living_people:
        return

    unprotected_people = sorted(
        [person for person in living_people if person["id"] not in protected_ids],
        key=lambda person: person["id"],
    )
    protected_people = sorted(
        [person for person in living_people if person["id"] in protected_ids],
        key=lambda person: person["id"],
    )
    for stat, target_value in status_targets.items():
        target = _status_target_for_living_people(stat, target_value)
        current_total = _living_status_total(living_people, stat)
        current_average = current_total // len(living_people)

        if current_average < target:
            desired_total = target * len(living_people)
            remaining = _distribute_status_adjustment(
                unprotected_people,
                stat=stat,
                amount=desired_total - current_total,
                direction=1,
            )
            _distribute_status_adjustment(
                protected_people,
                stat=stat,
                amount=remaining,
                direction=1,
            )
        elif current_average > target:
            desired_total = (target * len(living_people)) + len(living_people) - 1
            remaining = _distribute_status_adjustment(
                unprotected_people,
                stat=stat,
                amount=current_total - desired_total,
                direction=-1,
            )
            _distribute_status_adjustment(
                protected_people,
                stat=stat,
                amount=remaining,
                direction=-1,
            )


def _people_event_person_ids(people_events: dict[str, list[dict[str, Any]]]) -> set[str]:
    person_ids = set()
    for events in people_events.values():
        for event in events:
            for person_ref in event.get("people", []):
                if person_ref.get("id"):
                    person_ids.add(person_ref["id"])
            if event.get("id"):
                person_ids.add(event["id"])

    return person_ids


def _status_target_for_living_people(stat: str, target: int) -> int:
    if stat == "health":
        return max(1, min(10, target))

    return max(0, min(10, target))


def _living_status_total(people: list[dict[str, Any]], stat: str) -> int:
    return sum(person.get("status", {}).get(stat, 0) for person in people)


def _distribute_status_adjustment(
    people: list[dict[str, Any]],
    *,
    stat: str,
    amount: int,
    direction: int,
) -> int:
    if amount <= 0:
        return 0

    minimum = 1 if stat == "health" else 0
    remaining = amount
    while remaining > 0:
        changed_this_pass = False
        for person in people:
            status = person.get("status", {})
            value = status.get(stat)
            if value is None:
                continue

            if direction > 0 and value < 10:
                status[stat] = value + 1
            elif direction < 0 and value > minimum:
                status[stat] = value - 1
            else:
                continue

            remaining -= 1
            changed_this_pass = True
            if remaining == 0:
                return 0

        if not changed_this_pass:
            return remaining

    return remaining


def _apply_people_effects(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    world_event: str,
    event_details: dict[str, Any],
    leadership_action: str,
    population_before_survival: int,
    survival_effects: dict[str, int],
) -> dict[str, list[dict[str, Any]]]:
    people_events = apply_daily_people_events(
        after,
        world_event=world_event,
        leadership_action=leadership_action,
        day=before["day"],
        event_details=event_details,
        discovery_detail=(
            _discovery_detail(before) if world_event == "discovery" else None
        ),
    )
    deaths = []
    direct_loss = max(0, before["population"] - population_before_survival)

    if direct_loss:
        deaths.extend(
            apply_population_loss_to_people(
                after,
                loss_count=direct_loss,
                day=before["day"],
                cause=_population_loss_cause(world_event),
            )
        )

    food_events = apply_daily_food_status(
        after,
        missed_rations=survival_effects.get("missed_rations", 0),
        day=before["day"],
    )
    for event_type, events in food_events.items():
        if event_type == "deaths":
            deaths.extend(events)
        else:
            people_events.setdefault(event_type, []).extend(events)

    people_events["deaths"] = deaths
    return people_events


def _population_loss_cause(world_event: str) -> str:
    if world_event == "illness":
        return "illness"

    if world_event == "wolf_attack":
        return "wolf_attack"

    if world_event == "storm":
        return "storm"

    return "hardship"


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

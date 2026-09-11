"""Choose local colony decisions, with tightly bounded optional AI visits."""

from __future__ import annotations

import os
from typing import Any

from src.config import load_local_env
from src.constants import EMPTY_COLONY_EVENT_TYPE, NO_ACTION_ACTION_TYPE
from src.environment import environment_for_day
from src.openai_selector import (
    OpenAISelectorError,
    choose_leadership_action_with_openai,
    choose_world_event_with_openai,
)

WOLF_ATTACK_COOLDOWN_DAYS = 7
WOLF_ATTACK_COOLDOWN_BYPASS_SEVERITY = 5
STORM_SEVERITY_BYPASS = 5
STORM_RULES_BY_SEASON = {
    "winter": {"cooldown_days": 3, "window_days": 14, "max_storms": 3},
    "spring": {"cooldown_days": 6, "window_days": 30, "max_storms": 2},
    "summer": {"cooldown_days": 6, "window_days": 30, "max_storms": 2},
    "autumn": {"cooldown_days": 7, "window_days": 30, "max_storms": 2},
}


def choose_world_event(
    state: dict[str, Any],
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Choose fate locally unless the user enabled an eligible AI day."""
    load_local_env()
    local = choose_local_world_event(state, environment=environment)
    if not should_use_ai(state):
        return local
    try:
        decision = choose_world_event_with_openai(state, environment=environment)
        decision = _apply_storm_limits(decision, state, environment=environment)
        decision = _apply_wolf_attack_cooldown(decision, state)
        return {**decision, "selector": "openai"}
    except OpenAISelectorError as exc:
        print(
            "::warning title=OpenAI deity selector failed::"
            f"{_escape_github_annotation(str(exc))}"
        )
        return {**local, "selector": "local_fallback"}


def choose_leadership_action(
    state: dict[str, Any],
    world_event: str | dict[str, Any],
) -> str:
    """Keep the president practical even when the optional API is unavailable."""
    load_local_env()
    if not should_use_ai(state):
        return choose_local_leadership_action(state, world_event)
    try:
        return choose_leadership_action_with_openai(state, world_event)
    except OpenAISelectorError as exc:
        print(
            "::warning title=OpenAI president selector failed::"
            f"{_escape_github_annotation(str(exc))}"
        )
        return choose_local_leadership_action(state, world_event)


def should_use_ai(state: dict[str, Any]) -> bool:
    """Unknown modes fail closed: a stored API key alone never incurs cost."""
    if state.get("population", 0) <= 0 or not os.getenv("OPENAI_API_KEY", "").strip():
        return False
    mode = os.getenv("COLONY_AI_MODE", "off").strip().lower()
    return mode == "daily" or (mode == "weekly" and int(state.get("day", 1)) % 7 == 0)


def choose_local_world_event(
    state: dict[str, Any], environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A repeatable seasonal event schedule with a safety margin for recovery."""
    population = int(state.get("population", 0))
    day = int(state.get("day", 1))
    environment = environment or environment_for_day(day)
    season = environment.get("date", {}).get("season", "spring")
    event, reason, severity = "quiet_day", "Households and frontier crews continue their daily work.", None
    if population <= 0:
        event, reason = EMPTY_COLONY_EVENT_TYPE, "The settlement is awaiting new settlers."
    elif state.get("food", 0) < population * 3:
        event, severity, reason = "foraging", 5, "Low reserves send experienced foragers to secure the next meals."
    elif state.get("health", 0) <= 3 or state.get("security", 0) <= 2:
        reason = "The frontier has a respite while the colony restores care and defenses."
    elif state.get("undead_threat", {}).get("active"):
        event, severity, reason = "undead_rising", 1, "The watch acts on the remaining undead threat."
    elif season in {"summer", "autumn"} and state.get("agriculture", {}).get("crop_fields", 0) >= population and day % 7 == 0:
        event, reason = "good_harvest", "Prepared fields are ready for the seasonal harvest."
    elif day % 47 == 0 and "wolves" in state.get("known_threats", []):
        event, severity, reason = "wolf_attack", 2, "A small pack tests the colony's watch posts."
    elif day % 29 == 0:
        event, severity, reason = "storm", 2, "A passing storm tests the colony's stores and shelters."
    elif day % 23 == 0:
        event, reason = "dispute", "Work assignments bring a disagreement before the council."
    elif day % 17 == 0 and state.get("health", 0) >= 5:
        event, reason = "illness", "A seasonal illness calls for the healers' attention."
    elif day % 11 == 0:
        event, reason = "discovery", "Scouts examine a useful lead from the frontier routes."
    elif day % 13 == 0:
        event, severity, reason = "foraging", 4, "Foragers revisit a promising seasonal food source."
    decision = {"world_event": event, "reasoning": reason, "selector": "local"}
    if severity is not None:
        decision["severity"] = severity
    decision = _apply_storm_limits(decision, state, environment=environment)
    return _apply_wolf_attack_cooldown(decision, state)


def choose_local_leadership_action(
    state: dict[str, Any], world_event: str | dict[str, Any],
) -> str:
    """Balance survival, lasting construction, and journeys without an API."""
    population = int(state.get("population", 0))
    if population <= 0:
        return NO_ACTION_ACTION_TYPE
    event = world_event if isinstance(world_event, str) else world_event["world_event"]
    day = int(state.get("day", 1))
    season = environment_for_day(day)["date"]["season"]
    food, wood = int(state.get("food", 0)), int(state.get("wood", 0))
    resources = state.get("resources", {})
    stocks = resources.get("stockpiles", {})
    crops = state.get("agriculture", {}).get("crop_fields", 0)
    if event == "undead_rising":
        return "fight_undead"
    if food < population and event != "foraging":
        return "harvest_crops" if crops and season in {"summer", "autumn"} else "ration_food"
    if state.get("health", 0) <= 5 or event == "illness":
        return "tend_the_sick"
    if wood < 15:
        return "gather_wood"
    if state.get("security", 0) < 4 or event == "wolf_attack":
        return "strengthen_defenses"
    if state.get("morale", 0) < 4 or event == "dispute":
        return "mediate_dispute"
    if crops >= population * 2 and season in {"summer", "autumn"} and food < population * 12:
        return "harvest_crops"
    frontier = state.get("frontier", {})
    project = next((p for p in frontier.get("projects", []) if p.get("completed_day") is None), {})
    if day % 3 != 0:
        return "send_scouts"
    project_id = project.get("id")
    if project_id == "kitchen_gardens" and season != "winter":
        return "expand_fields"
    if project_id == "rain_cistern":
        if stocks.get("clay", 0) >= 8:
            return "make_pottery"
        if resources.get("deposits", {}).get("clay", {}).get("abundance", 0) > 0:
            return "gather_clay"
    if project_id == "watchtower":
        return "strengthen_defenses" if state.get("security", 0) < 7 else "gather_wood"
    if project_id == "clinic" and state.get("health", 0) < 8:
        return "tend_the_sick"
    if project_id == "river_dock":
        return "gather_wood"
    if stocks.get("bricks", 0) >= 10 and resources.get("improvements", {}).get("brick_shelters", 0) < 3:
        return "build_with_brick"
    if stocks.get("clay", 0) >= 20 and wood >= 30 and resources.get("improvements", {}).get("brick_shelters", 0) < 3:
        return "fire_bricks"
    return "send_scouts"


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


def _apply_storm_limits(
    decision: dict[str, Any],
    state: dict[str, Any],
    *,
    environment: dict[str, Any] | None,
) -> dict[str, Any]:
    if decision.get("world_event") != "storm":
        return decision

    season = _season_for_storm_limits(state, environment)
    rules = STORM_RULES_BY_SEASON.get(season, STORM_RULES_BY_SEASON["spring"])
    current_day = state.get("day", 1)
    recent_storm_days = _recent_storm_days(
        state,
        current_day=current_day,
        window_days=rules["window_days"],
    )
    severity = int(decision.get("severity") or 3)
    original_reasoning = decision.get("reasoning", "")

    if len(recent_storm_days) >= rules["max_storms"]:
        return {
            "world_event": "quiet_day",
            "reasoning": (
                f"Storms are seasonally limited in {season}; "
                f"{len(recent_storm_days)} storm events already occurred in the "
                f"last {rules['window_days']} days. "
                f"Original selection was storm: {original_reasoning}"
            ),
        }

    recent_storm_day = recent_storm_days[-1] if recent_storm_days else None
    if (
        recent_storm_day is not None
        and current_day - recent_storm_day <= rules["cooldown_days"]
        and severity < STORM_SEVERITY_BYPASS
    ):
        return {
            "world_event": "quiet_day",
            "reasoning": (
                f"A storm struck recently, so {season} weather does not produce "
                "another major storm today. "
                f"Original selection was storm: {original_reasoning}"
            ),
        }

    return decision


def _season_for_storm_limits(
    state: dict[str, Any],
    environment: dict[str, Any] | None,
) -> str:
    if environment:
        date = environment.get("date", {})
        weather = environment.get("weather", {})
        return date.get("season") or weather.get("season") or "spring"

    return state.get("date", {}).get("season", "spring")


def _recent_storm_days(
    state: dict[str, Any],
    *,
    current_day: int,
    window_days: int,
) -> list[int]:
    lower_bound = current_day - window_days
    return [
        int(record["day"])
        for record in state.get("event_log", [])
        if (record.get("world_event") or record.get("event_type")) == "storm"
        and int(record.get("day", 0)) > lower_bound
        and int(record.get("day", 0)) < current_day
    ]


def _most_recent_wolf_attack_day(state: dict[str, Any]) -> int | None:
    for record in reversed(state.get("event_log", [])):
        if (record.get("world_event") or record.get("event_type")) == "wolf_attack":
            return record.get("day")

    return None

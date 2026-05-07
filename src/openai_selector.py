"""OpenAI-powered decision selection for the colony simulation."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Literal

from src.constants import LEADERSHIP_ACTION_TYPES, WORLD_EVENT_TYPES
from src.environment import year_for_day
from src.people import character_context_for_prompt, president_context_for_prompt

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
OPENAI_MAX_ATTEMPTS = 3


class OpenAISelectorError(RuntimeError):
    """Raised when the OpenAI selector cannot choose a valid decision."""


class MissingOpenAIConfigError(OpenAISelectorError):
    """Raised when required OpenAI configuration is missing."""


class OpenAIAPICallError(OpenAISelectorError):
    """Raised when the OpenAI API call fails."""


def choose_world_event_with_openai(
    state: dict[str, Any],
    *,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask OpenAI to choose one allowed world event for the current state."""
    client, model, base_model = _openai_client()

    class WorldEventSelection(base_model):
        world_event: Literal[
            "good_harvest",
            "poor_harvest",
            "illness",
            "dispute",
            "discovery",
            "storm",
            "wolf_attack",
            "quiet_day",
        ]
        severity: int | None = None
        reasoning: str

    input_payload = [
        {
            "role": "system",
            "content": (
                "You are a deity watching the fictional colony of Blergen. "
                "Choose exactly one allowed world event that should befall "
                "the colony today. You control fate and circumstance, not "
                "the colony's leadership decisions. Favor impactful events, "
                "good and bad. Choose quiet_day only about 15 to 25 percent "
                "of the time, and less often when severe weather or known "
                "threats suggest danger. Wolves are an active threat and may "
                "produce wolf_attack. Winter is a season, not an event, but "
                "winter weather can produce storm. For wolf_attack and storm, "
                "set severity from 1 to 5. Do not apply mechanics and do not "
                "invent new event types. Named colonists are context for fate "
                "and story pressure, but your structured response must still "
                "choose only one allowed world event."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                _state_for_world_prompt(state, environment=environment),
                indent=2,
            ),
        },
    ]

    response = _parse_with_retries(
        client=client,
        model=model,
        input_payload=input_payload,
        text_format=WorldEventSelection,
    )

    world_event = response.output_parsed.world_event
    if world_event not in WORLD_EVENT_TYPES:
        raise OpenAIAPICallError(f"OpenAI returned an invalid world event: {world_event}")

    return _normalize_world_event_decision(
        {
            "world_event": world_event,
            "severity": response.output_parsed.severity,
            "reasoning": response.output_parsed.reasoning,
        },
        environment=environment,
    )


def choose_leadership_action_with_openai(
    state: dict[str, Any],
    world_event: str | dict[str, Any],
) -> str:
    """Ask OpenAI to choose the president's response to the day's event."""
    client, model, base_model = _openai_client()

    class LeadershipActionSelection(base_model):
        leadership_action: Literal[
            "preserve_resources",
            "ration_food",
            "gather_wood",
            "expand_fields",
            "strengthen_defenses",
            "tend_the_sick",
            "mediate_dispute",
            "send_scouts",
            "hold_festival",
        ]
        reasoning: str

    input_payload = [
        {
            "role": "system",
            "content": (
                "You are the current president of the Blergen colony. The "
                "user payload identifies the specific colonist holding that "
                "office. A report has arrived describing today's circumstance, "
                "which may be a major event or a quiet day. Choose exactly "
                "one allowed leadership action for the colony. Respond "
                "practically in light of the event and the current state. Do "
                "not apply mechanics and do not invent new action types. "
                "Named colonists are context for priorities, not extra output "
                "fields. Storms and wolf attacks can be severe; consider "
                "defense, sickness, food, and morale accordingly."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                _state_for_leadership_prompt(state, world_event),
                indent=2,
            ),
        },
    ]

    response = _parse_with_retries(
        client=client,
        model=model,
        input_payload=input_payload,
        text_format=LeadershipActionSelection,
    )

    leadership_action = response.output_parsed.leadership_action
    if leadership_action not in LEADERSHIP_ACTION_TYPES:
        raise OpenAIAPICallError(
            f"OpenAI returned an invalid leadership action: {leadership_action}"
        )

    return leadership_action


def choose_event_with_openai(state: dict[str, Any]) -> str:
    """Backward-compatible wrapper for older callers."""
    return choose_world_event_with_openai(state)["world_event"]


def _openai_client() -> tuple[Any, str, type[Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise MissingOpenAIConfigError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
        from pydantic import BaseModel
    except ImportError as exc:
        raise OpenAISelectorError(
            "The OpenAI selectors require the openai package. "
            "Install dependencies with: python -m pip install -r requirements.txt"
        ) from exc

    model = os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    return OpenAI(api_key=api_key, timeout=30.0, max_retries=2), model, BaseModel


def _parse_with_retries(
    client: Any,
    model: str,
    input_payload: list[dict[str, str]],
    text_format: type[Any],
) -> Any:
    last_error = None
    for attempt in range(1, OPENAI_MAX_ATTEMPTS + 1):
        try:
            return client.responses.parse(
                model=model,
                input=input_payload,
                text_format=text_format,
            )
        except Exception as exc:
            last_error = exc
            if attempt < OPENAI_MAX_ATTEMPTS:
                time.sleep(attempt * 2)

    raise OpenAIAPICallError(
        "OpenAI API call failed after "
        f"{OPENAI_MAX_ATTEMPTS} attempts: {_safe_error_message(last_error)}"
    ) from last_error


def _safe_error_message(error: Exception) -> str:
    api_key = os.getenv("OPENAI_API_KEY") or ""
    message = str(error)
    cause = getattr(error, "__cause__", None)
    if cause:
        message = f"{message} Cause: {type(cause).__name__}: {cause}"
    if api_key:
        message = message.replace(api_key, "[redacted]")

    message = " ".join(message.split())
    if len(message) > 500:
        message = message[:497] + "..."

    if message:
        return f"{type(error).__name__}: {message}"

    return type(error).__name__


def _normalize_world_event_decision(
    decision: str | dict[str, Any],
    *,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(decision, str):
        decision = {"world_event": decision}

    world_event = decision.get("world_event")
    if world_event not in WORLD_EVENT_TYPES:
        raise OpenAIAPICallError(f"OpenAI returned an invalid world event: {world_event}")

    normalized = {
        "world_event": world_event,
        "reasoning": decision.get("reasoning", ""),
    }
    if world_event in {"storm", "wolf_attack"}:
        default_severity = 3
        if world_event == "storm" and environment:
            default_severity = environment.get("weather", {}).get("severity", 3)
        normalized["severity"] = max(1, min(5, int(decision.get("severity") or default_severity)))

    return normalized


def _world_event_type(world_event: str | dict[str, Any]) -> str:
    if isinstance(world_event, str):
        return world_event

    return world_event["world_event"]


def _state_for_world_prompt(
    state: dict[str, Any],
    *,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "role": "deity",
        "allowed_world_events": list(WORLD_EVENT_TYPES),
        "current_state": {
            "day": state["day"],
            "year": state.get("year", year_for_day(state["day"])),
            "colony_name": state["colony_name"],
            "population": state["population"],
            "food": state["food"],
            "wood": state["wood"],
            "morale": state["morale"],
            "security": state["security"],
            "health": state["health"],
            "known_threats": state["known_threats"],
        },
        "environment": environment or {},
        "threat_rules": [
            "known_threats containing wolves means wolf_attack is available.",
            "known_threats containing winter means winter weather should increase storm danger.",
            "Winter is a season and period, not a world_event label.",
            "For wolf_attack and storm, severity must be an integer from 1 to 5.",
        ],
        "character_context": character_context_for_prompt(state),
        "recent_events": state.get("event_log", [])[-5:],
    }


def _state_for_leadership_prompt(
    state: dict[str, Any],
    world_event: str | dict[str, Any],
) -> dict[str, Any]:
    world_event_type = _world_event_type(world_event)
    return {
        "role": "president",
        "today_world_event": world_event_type,
        "today_event_details": world_event if isinstance(world_event, dict) else {},
        "allowed_leadership_actions": list(LEADERSHIP_ACTION_TYPES),
        "president": president_context_for_prompt(state),
        "current_state": {
            "day": state["day"],
            "year": state.get("year", year_for_day(state["day"])),
            "colony_name": state["colony_name"],
            "population": state["population"],
            "food": state["food"],
            "wood": state["wood"],
            "morale": state["morale"],
            "security": state["security"],
            "health": state["health"],
            "known_threats": state["known_threats"],
        },
        "character_context": character_context_for_prompt(
            state,
            world_event=world_event_type,
        ),
        "recent_events": state.get("event_log", [])[-5:],
        "important_rules": [
            "Food is consumed every day regardless of your action.",
            "Each living colonist needs 1 food per day.",
            "Missed rations increase personal hunger; severe hunger can kill colonists.",
            "Food gains and major food costs scale with living population.",
            "strengthen_defenses requires at least 10 wood.",
            "hold_festival costs extra food.",
            "strengthen_defenses can reduce damage from wolf attacks.",
            "send_scouts can help track threats but still costs the day's action.",
            "Named colonists can inform priorities, but choose only one allowed action label.",
        ],
    }


def _state_for_prompt(state: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible prompt helper for older tests and callers."""
    return _state_for_world_prompt(state)

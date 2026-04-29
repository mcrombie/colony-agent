"""OpenAI-powered event selection for the colony simulation."""

from __future__ import annotations

import json
import os
from typing import Any, Literal

from src.constants import OPENAI_EVENT_TYPES

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


class OpenAISelectorError(RuntimeError):
    """Raised when the OpenAI selector cannot choose a valid event."""


class MissingOpenAIConfigError(OpenAISelectorError):
    """Raised when required OpenAI configuration is missing."""


class OpenAIAPICallError(OpenAISelectorError):
    """Raised when the OpenAI API call fails."""


def choose_event_with_openai(state: dict[str, Any]) -> str:
    """Ask OpenAI to choose one allowed event type for the current state."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise MissingOpenAIConfigError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
        from pydantic import BaseModel
    except ImportError as exc:
        raise OpenAISelectorError(
            "The OpenAI selector requires the openai package. "
            "Install dependencies with: python -m pip install -r requirements.txt"
        ) from exc

    class EventSelection(BaseModel):
        event_type: Literal[
            "good_harvest",
            "poor_harvest",
            "construction",
            "illness",
            "dispute",
            "discovery",
            "quiet_day",
        ]
        reasoning: str

    model = os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.parse(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an event selector for a small fictional colony "
                        "simulation. Choose exactly one allowed event type. "
                        "Consider the current state, known threats, and recent "
                        "events, but do not apply mechanics and do not invent new "
                        "event types."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(_state_for_prompt(state), indent=2),
                },
            ],
            text_format=EventSelection,
        )
    except Exception as exc:
        raise OpenAIAPICallError(
            f"OpenAI API call failed: {_safe_error_message(exc)}"
        ) from exc

    event_type = response.output_parsed.event_type
    if event_type not in OPENAI_EVENT_TYPES:
        raise OpenAIAPICallError(f"OpenAI returned an invalid event type: {event_type}")

    return event_type


def _safe_error_message(error: Exception) -> str:
    api_key = os.getenv("OPENAI_API_KEY") or ""
    message = str(error)
    if api_key:
        message = message.replace(api_key, "[redacted]")

    message = " ".join(message.split())
    if len(message) > 500:
        message = message[:497] + "..."

    if message:
        return f"{type(error).__name__}: {message}"

    return type(error).__name__


def _state_for_prompt(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "allowed_event_types": list(OPENAI_EVENT_TYPES),
        "current_state": {
            "day": state["day"],
            "colony_name": state["colony_name"],
            "population": state["population"],
            "food": state["food"],
            "wood": state["wood"],
            "morale": state["morale"],
            "security": state["security"],
            "health": state["health"],
            "known_threats": state["known_threats"],
        },
        "recent_events": state.get("event_log", [])[-5:],
    }

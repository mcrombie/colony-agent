"""Select colony events with OpenAI."""

from __future__ import annotations

from typing import Any

from src.config import load_local_env
from src.constants import CHAOS_GODS_EVENT_TYPE
from src.openai_selector import OpenAIAPICallError, choose_event_with_openai


def choose_event(state: dict[str, Any]) -> str:
    """Choose an event with OpenAI, failing loudly when config is missing."""
    load_local_env()
    try:
        return choose_event_with_openai(state)
    except OpenAIAPICallError as exc:
        print(
            "::warning title=OpenAI selector failed::"
            f"{_escape_github_annotation(str(exc))}"
        )
        return CHAOS_GODS_EVENT_TYPE


def _escape_github_annotation(message: str) -> str:
    return (
        message.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
        .replace(",", "%2C")
    )

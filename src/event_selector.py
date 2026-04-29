"""Select colony events using either OpenAI or local rules."""

from __future__ import annotations

import os
from typing import Any

from src.config import load_local_env
from src.events import choose_event as choose_rule_based_event
from src.openai_selector import choose_event_with_openai


def choose_event(state: dict[str, Any], mode: str | None = None) -> str:
    """Choose an event with OpenAI when configured, otherwise local rules."""
    load_local_env()

    selector_mode = (mode or os.getenv("COLONY_EVENT_SELECTOR") or "").lower()
    if not selector_mode:
        selector_mode = "openai" if os.getenv("OPENAI_API_KEY") else "rules"

    if selector_mode == "openai":
        return choose_event_with_openai(state)

    if selector_mode in {"rules", "rule_based", "local"}:
        return choose_rule_based_event(state)

    raise ValueError(
        "Unknown COLONY_EVENT_SELECTOR value. Use 'openai' or 'rules'."
    )

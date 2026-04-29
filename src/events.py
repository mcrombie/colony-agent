"""Rule-based event selection for the colony simulation."""

from __future__ import annotations

import random
from typing import Any

ALLOWED_EVENT_TYPES = (
    "good_harvest",
    "poor_harvest",
    "construction",
    "illness",
    "dispute",
    "discovery",
    "quiet_day",
)


def choose_event(state: dict[str, Any]) -> str:
    """Choose one event using simple state-weighted rules.

    The implementation uses Python's random module on purpose, but the function
    boundary is small so an AI selector can replace it later.
    """
    weights = {
        "good_harvest": 3,
        "discovery": 2,
        "quiet_day": 3,
        "construction": 1,
        "dispute": 1,
    }

    if state["food"] < 50:
        weights["poor_harvest"] = 4
        weights["dispute"] = weights.get("dispute", 0) + 2

    if state["wood"] >= 20 and state["security"] < 7:
        weights["construction"] = weights.get("construction", 0) + 4

    if state["health"] < 5:
        weights["illness"] = 4

    event_types = list(weights.keys())
    event_weights = list(weights.values())
    return random.choices(event_types, weights=event_weights, k=1)[0]


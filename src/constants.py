"""Shared event constants for the colony simulation."""

OPENAI_EVENT_TYPES = (
    "good_harvest",
    "poor_harvest",
    "construction",
    "illness",
    "dispute",
    "discovery",
    "quiet_day",
)

CHAOS_GODS_EVENT_TYPE = "chaos_gods"
ALLOWED_EVENT_TYPES = OPENAI_EVENT_TYPES + (CHAOS_GODS_EVENT_TYPE,)

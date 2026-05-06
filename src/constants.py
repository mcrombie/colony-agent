"""Shared choice constants for the colony simulation."""

WORLD_EVENT_TYPES = (
    "good_harvest",
    "poor_harvest",
    "illness",
    "dispute",
    "discovery",
    "storm",
    "wolf_attack",
    "quiet_day",
)

LEADERSHIP_ACTION_TYPES = (
    "preserve_resources",
    "ration_food",
    "gather_wood",
    "expand_fields",
    "strengthen_defenses",
    "tend_the_sick",
    "mediate_dispute",
    "send_scouts",
    "hold_festival",
)

CHAOS_GODS_EVENT_TYPE = "chaos_gods"
PRESERVE_RESOURCES_ACTION_TYPE = "preserve_resources"
FAILED_STRENGTHEN_DEFENSES_ACTION_TYPE = "failed_strengthen_defenses"

ALLOWED_WORLD_EVENT_TYPES = WORLD_EVENT_TYPES + (
    CHAOS_GODS_EVENT_TYPE,
)
ALLOWED_LEADERSHIP_ACTION_TYPES = LEADERSHIP_ACTION_TYPES + (
    FAILED_STRENGTHEN_DEFENSES_ACTION_TYPE,
)

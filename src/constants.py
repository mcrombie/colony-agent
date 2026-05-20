"""Shared choice constants for the colony simulation."""

WORLD_EVENT_TYPES = (
    "good_harvest",
    "poor_harvest",
    "illness",
    "dispute",
    "discovery",
    "foraging",
    "storm",
    "wolf_attack",
    "undead_rising",
    "quiet_day",
)

LEADERSHIP_ACTION_TYPES = (
    "preserve_resources",
    "ration_food",
    "gather_wood",
    "gather_clay",
    "make_pottery",
    "fire_bricks",
    "build_with_brick",
    "expand_fields",
    "harvest_crops",
    "strengthen_defenses",
    "tend_the_sick",
    "mediate_dispute",
    "send_scouts",
    "hold_festival",
    "fight_undead",
    "contain_undead",
)

CHAOS_GODS_EVENT_TYPE = "chaos_gods"
EMPTY_COLONY_EVENT_TYPE = "empty_colony"
PRESERVE_RESOURCES_ACTION_TYPE = "preserve_resources"
FAILED_STRENGTHEN_DEFENSES_ACTION_TYPE = "failed_strengthen_defenses"
FAILED_HARVEST_CROPS_ACTION_TYPE = "failed_harvest_crops"
FAILED_GATHER_CLAY_ACTION_TYPE = "failed_gather_clay"
FAILED_MAKE_POTTERY_ACTION_TYPE = "failed_make_pottery"
FAILED_FIRE_BRICKS_ACTION_TYPE = "failed_fire_bricks"
FAILED_BUILD_WITH_BRICK_ACTION_TYPE = "failed_build_with_brick"
NO_ACTION_ACTION_TYPE = "no_action"

ALLOWED_WORLD_EVENT_TYPES = WORLD_EVENT_TYPES + (
    CHAOS_GODS_EVENT_TYPE,
    EMPTY_COLONY_EVENT_TYPE,
)
ALLOWED_LEADERSHIP_ACTION_TYPES = LEADERSHIP_ACTION_TYPES + (
    FAILED_STRENGTHEN_DEFENSES_ACTION_TYPE,
    FAILED_HARVEST_CROPS_ACTION_TYPE,
    FAILED_GATHER_CLAY_ACTION_TYPE,
    FAILED_MAKE_POTTERY_ACTION_TYPE,
    FAILED_FIRE_BRICKS_ACTION_TYPE,
    FAILED_BUILD_WITH_BRICK_ACTION_TYPE,
    NO_ACTION_ACTION_TYPE,
)

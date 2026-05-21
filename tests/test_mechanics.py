from copy import deepcopy

from src.mechanics import apply_day, apply_event, clamp_state, daily_food_needed
from src.people import derived_colony_stats, generate_people

BASE_STATE = {
    "day": 1,
    "colony_name": "Blergen",
    "population": 100,
    "food": 120,
    "wood": 60,
    "morale": 7,
    "security": 5,
    "health": 6,
    "known_threats": ["wolves", "winter"],
    "event_log": [],
}


def state_with(**overrides):
    state = deepcopy(BASE_STATE)
    state.update(overrides)
    return state


def environment_for_season(season):
    day_by_season = {
        "spring": 100,
        "summer": 170,
        "autumn": 275,
        "winter": 15,
    }
    month_by_season = {
        "spring": "April",
        "summer": "June",
        "autumn": "October",
        "winter": "January",
    }
    day = day_by_season[season]
    return {
        "date": {
            "year": 1,
            "day_of_year": day,
            "month": month_by_season[season],
            "month_number": 1,
            "day_of_month": 1,
            "season": season,
        },
        "weather": {
            "season": season,
            "condition": "clear",
            "severity": 1,
            "summary": "Clear skies left the day's work mostly to the colony.",
        },
    }


def test_stat_clamping():
    state = state_with(morale=12, security=-3, health=15)

    clamped = clamp_state(state)

    assert clamped["morale"] == 10
    assert clamped["security"] == 0
    assert clamped["health"] == 10


def test_clamp_state_initializes_resource_state():
    clamped = clamp_state(state_with())

    assert clamped["resources"] == {
        "deposits": {},
        "stockpiles": {"clay": 0, "bricks": 0, "pottery": 0},
        "improvements": {"kiln": 0, "clay_storehouses": 0, "brick_shelters": 0},
    }


def test_resource_state_infers_old_clay_discoveries_from_log():
    state = state_with(
        event_log=[
            {
                "day": 25,
                "world_event": "discovery",
                "people_events": {
                    "discoveries": [
                        {"detail": "useful clay near the riverbank"},
                    ],
                },
            },
            {
                "day": 34,
                "world_event": "discovery",
                "summary": "Scouts discovered useful clay near the riverbank.",
            },
        ]
    )

    clamped = clamp_state(state)
    clay = clamped["resources"]["deposits"]["clay"]

    assert clay["known"] is True
    assert clay["abundance"] == 80
    assert clay["access"] == 2


def test_food_never_below_zero():
    state = state_with(food=3)

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert after["food"] == 0
    assert event_record["effects"]["food"] == -3


def test_food_shortage_increases_hunger_before_starvation_deaths():
    state = state_with(food=0, population=100)

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert after["food"] == 0
    assert after["population"] == 100
    assert event_record["survival_effects"]["missed_rations"] == 100
    assert event_record["people_events"]["actions"][0]["type"] == "missed_rations"
    assert all(person["status"]["hunger"] == 1 for person in after["people"])


def test_starvation_reduces_population_when_hunger_is_severe():
    people = generate_people(100, colony_health=6, colony_morale=7)
    for person in people:
        person["status"]["hunger"] = 2
    state = state_with(food=99, population=100, people=people)

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert after["food"] == 0
    assert after["population"] == 99
    assert event_record["effects"]["population"] == -1
    assert event_record["people_events"]["deaths"][0]["cause"] == "starvation"


def test_day_increments():
    state = state_with(day=9)

    after, _ = apply_day(state, "good_harvest", "preserve_resources")

    assert after["day"] == 10
    assert after["year"] == 1


def test_empty_colony_takes_no_action_and_consumes_no_food():
    state = state_with(population=0, food=12, people=[])

    after, event_record = apply_day(state, "empty_colony", "no_action")

    assert after["population"] == 0
    assert after["food"] == 12
    assert after["day"] == 2
    assert event_record["world_event"] == "empty_colony"
    assert event_record["leadership_action"] == "no_action"
    assert event_record["survival_effects"] == {}
    assert event_record["people_events"] == {"deaths": []}


def test_good_harvest_turns_prepared_summer_crops_into_food():
    state = state_with(
        food=7,
        population=7,
        people=generate_people(7),
        agriculture={"crop_fields": 35},
    )

    after, event_record = apply_day(
        state,
        "good_harvest",
        "preserve_resources",
        environment=environment_for_season("summer"),
    )

    assert after["food"] == 43
    assert after["agriculture"]["crop_fields"] == 0
    assert event_record["effects"]["food"] == 36
    assert event_record["effects"]["crop_fields"] == -35
    assert event_record["survival_effects"] == {"food": -7}


def test_expand_fields_prepares_food_without_feeding_the_colony_today():
    state = state_with(food=7, population=7, people=generate_people(7))

    after, event_record = apply_day(
        state,
        "quiet_day",
        "expand_fields",
        environment=environment_for_season("spring"),
    )

    assert after["food"] == 0
    assert after["population"] == 7
    assert after["agriculture"]["crop_fields"] == 21
    assert event_record["effects"] == {"food": -7, "crop_fields": 21}
    assert all(person["status"]["hunger"] == 0 for person in after["people"])


def test_harvest_crops_action_converts_autumn_crop_fields_to_food():
    state = state_with(
        food=7,
        population=7,
        people=generate_people(7),
        agriculture={"crop_fields": 35},
    )

    after, event_record = apply_day(
        state,
        "quiet_day",
        "harvest_crops",
        environment=environment_for_season("autumn"),
    )

    assert after["food"] == 35
    assert after["agriculture"]["crop_fields"] == 0
    assert event_record["effects"] == {"food": 28, "crop_fields": -35}
    assert event_record["survival_effects"] == {"food": -7}


def test_harvest_crops_does_not_work_in_winter():
    state = state_with(
        food=7,
        population=7,
        people=generate_people(7),
        agriculture={"crop_fields": 35},
    )

    after, event_record = apply_day(
        state,
        "quiet_day",
        "harvest_crops",
        environment=environment_for_season("winter"),
    )

    assert after["food"] == 0
    assert after["agriculture"]["crop_fields"] == 35
    assert event_record["leadership_action"] == "failed_harvest_crops"
    assert event_record["effects"] == {"food": -7}


def test_year_updates_when_day_rolls_into_next_year():
    state = state_with(day=365)

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert event_record["day"] == 365
    assert event_record["year"] == 1
    assert after["day"] == 366
    assert after["year"] == 2


def test_daily_food_is_consumed_regardless_of_event():
    state = state_with(food=120, population=100)

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert daily_food_needed(100) == 100
    assert after["food"] == 20
    assert event_record["survival_effects"] == {"food": -100}
    assert event_record["date"]["month"] == "January"
    assert event_record["weather"]["condition"] == "overcast"


def test_rationing_reduces_food_need_and_costs_morale():
    state = state_with(food=120, population=100, morale=7)

    after, event_record = apply_day(state, "quiet_day", "ration_food")

    assert daily_food_needed(100, "ration_food") == 75
    assert after["food"] == 45
    assert after["morale"] == 6
    assert event_record["effects"]["food"] == -75
    assert event_record["effects"]["morale"] == -1


def test_rationing_rounds_up_for_small_colonies():
    assert daily_food_needed(3, "ration_food") == 3
    assert daily_food_needed(4, "ration_food") == 3


def test_fed_colony_recovers_health_on_calm_days():
    state = state_with(food=120, population=100, health=4)

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert after["health"] == 5
    assert event_record["effects"]["health"] == 1


def test_colony_does_not_recover_health_without_full_rations():
    state = state_with(food=50, population=100, health=4)

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert after["health"] == 4
    assert "health" not in event_record["effects"]
    assert event_record["survival_effects"]["missed_rations"] == 50


def test_colony_does_not_passively_recover_while_rationing():
    state = state_with(food=120, population=100, health=4)

    after, event_record = apply_day(state, "quiet_day", "ration_food")

    assert after["health"] == 4
    assert "health" not in event_record["effects"]


def test_foraging_adds_variable_food_before_daily_consumption():
    environment = {
        "date": {
            "year": 1,
            "day_of_year": 170,
            "month": "June",
            "month_number": 6,
            "day_of_month": 19,
            "season": "summer",
        },
        "weather": {
            "season": "summer",
            "condition": "clear",
            "severity": 1,
            "summary": "Clear skies left the day's work mostly to the colony.",
        },
    }
    state = state_with(food=0, population=100)

    after, event_record = apply_day(
        state,
        {"world_event": "foraging", "severity": 4},
        "preserve_resources",
        environment=environment,
    )

    assert after["food"] == 50
    assert event_record["effects"]["food"] == 50
    assert event_record["survival_effects"] == {"food": -100}


def test_foraging_yields_less_food_in_winter():
    winter = {
        "date": {
            "year": 1,
            "day_of_year": 15,
            "month": "January",
            "month_number": 1,
            "day_of_month": 15,
            "season": "winter",
        },
        "weather": {
            "season": "winter",
            "condition": "snow",
            "severity": 2,
            "summary": "Snow made paths and work crews slower.",
        },
    }
    summer = {
        "date": {
            "year": 1,
            "day_of_year": 170,
            "month": "June",
            "month_number": 6,
            "day_of_month": 19,
            "season": "summer",
        },
        "weather": {
            "season": "summer",
            "condition": "clear",
            "severity": 1,
            "summary": "Clear skies left the day's work mostly to the colony.",
        },
    }

    winter_after, _ = apply_day(
        state_with(food=0, population=100),
        {"world_event": "foraging", "severity": 4},
        "preserve_resources",
        environment=winter,
    )
    summer_after, _ = apply_day(
        state_with(food=0, population=100),
        {"world_event": "foraging", "severity": 4},
        "preserve_resources",
        environment=summer,
    )

    assert winter_after["food"] == 0
    assert summer_after["food"] == 50


def test_discovery_adds_durable_clay_deposit():
    state = state_with(day=1, food=10, population=5, people=generate_people(5))

    after, event_record = apply_day(state, "discovery", "preserve_resources")

    clay = after["resources"]["deposits"]["clay"]
    assert event_record["event_details"]["resource"] == "clay"
    assert clay["abundance"] == 40
    assert clay["access"] == 1
    assert event_record["effects"]["clay_deposit"] == 40
    assert event_record["effects"]["morale"] == 1


def test_gather_clay_turns_deposit_abundance_into_stockpile():
    state = state_with(
        food=20,
        population=10,
        people=generate_people(10),
        resources={
            "deposits": {
                "clay": {
                    "known": True,
                    "quality": 2,
                    "abundance": 50,
                    "access": 1,
                    "discovered_day": 1,
                }
            },
            "stockpiles": {"clay": 0, "bricks": 0, "pottery": 0},
            "improvements": {"kiln": 0, "clay_storehouses": 0, "brick_shelters": 0},
        },
    )

    after, event_record = apply_day(state, "quiet_day", "gather_clay")

    assert after["resources"]["stockpiles"]["clay"] == 12
    assert after["resources"]["deposits"]["clay"]["abundance"] == 38
    assert event_record["effects"]["clay"] == 12
    assert event_record["effects"]["clay_deposit"] == -12
    assert event_record["people_events"]["actions"][0]["type"] == "gathered_clay"


def test_gather_clay_without_deposit_logs_failure():
    state = state_with(food=20, population=10, people=generate_people(10))

    after, event_record = apply_day(state, "quiet_day", "gather_clay")

    assert event_record["leadership_action"] == "failed_gather_clay"
    assert after["resources"]["stockpiles"]["clay"] == 0
    assert event_record["effects"] == {"food": -10}


def test_clay_can_be_turned_into_pottery_bricks_and_shelter():
    state = state_with(
        food=60,
        population=5,
        people=generate_people(5),
        wood=20,
        security=4,
        resources={
            "deposits": {},
            "stockpiles": {"clay": 30, "bricks": 0, "pottery": 0},
            "improvements": {"kiln": 0, "clay_storehouses": 0, "brick_shelters": 0},
        },
    )

    clear = environment_for_season("spring")
    after_pottery, pottery_record = apply_day(
        state,
        "quiet_day",
        "make_pottery",
        environment=clear,
    )
    after_bricks, bricks_record = apply_day(
        after_pottery,
        "quiet_day",
        "fire_bricks",
        environment=clear,
    )
    after_shelter, shelter_record = apply_day(
        after_bricks,
        "quiet_day",
        "build_with_brick",
        environment=clear,
    )

    assert after_pottery["resources"]["stockpiles"]["pottery"] == 1
    assert pottery_record["effects"]["clay"] == -8
    assert pottery_record["effects"]["pottery"] == 1
    assert after_bricks["resources"]["stockpiles"]["bricks"] == 10
    assert bricks_record["effects"]["wood"] == -5
    assert bricks_record["effects"]["bricks"] == 10
    assert after_shelter["resources"]["improvements"]["brick_shelters"] == 1
    assert after_shelter["security"] == 5
    assert shelter_record["effects"]["brick_shelters"] == 1


def test_pottery_and_brick_shelters_reduce_storm_damage():
    state = state_with(
        day=50,
        food=120,
        wood=60,
        health=6,
        morale=7,
        resources={
            "deposits": {},
            "stockpiles": {"clay": 0, "bricks": 0, "pottery": 2},
            "improvements": {"kiln": 0, "clay_storehouses": 0, "brick_shelters": 1},
        },
    )
    environment = {
        "date": {
            "year": 1,
            "day_of_year": 50,
            "month": "February",
            "month_number": 2,
            "day_of_month": 19,
            "season": "winter",
        },
        "weather": {
            "season": "winter",
            "condition": "clear",
            "severity": 1,
            "summary": "Cold clear air settled over the camp.",
        },
    }

    after, event_record = apply_day(
        state,
        {"world_event": "storm", "severity": 4},
        "preserve_resources",
        environment=environment,
    )

    assert after["food"] == 16
    assert after["wood"] == 57
    assert after["health"] == 6
    assert event_record["effects"]["food"] == -104
    assert event_record["effects"]["wood"] == -3
    assert "health" not in event_record["effects"]


def test_morale_effects_are_preserved_when_people_drive_stats():
    state = state_with(
        morale=5,
        agriculture={"crop_fields": 500},
        people=generate_people(100, colony_health=6, colony_morale=5),
    )

    after, event_record = apply_day(
        state,
        "good_harvest",
        "preserve_resources",
        environment=environment_for_season("summer"),
    )

    assert after["morale"] == 6
    assert after["morale"] == derived_colony_stats(after)["morale"]
    assert event_record["effects"]["morale"] == 1


def test_leadership_morale_effects_are_preserved_with_named_people():
    state = state_with(
        morale=5,
        people=generate_people(100, colony_health=6, colony_morale=5),
    )

    after, event_record = apply_day(state, "quiet_day", "hold_festival")

    assert after["morale"] == 7
    assert after["morale"] == derived_colony_stats(after)["morale"]
    assert event_record["effects"]["morale"] == 2


def test_festival_cost_scales_with_population():
    state = state_with(
        food=250,
        population=100,
        people=generate_people(100, colony_health=6, colony_morale=5),
    )

    after, event_record = apply_day(state, "quiet_day", "hold_festival")

    assert after["food"] == 50
    assert event_record["effects"]["food"] == -200


def test_strengthen_defenses_consumes_wood_and_improves_security():
    state = state_with(wood=20, security=4)

    after, event_record = apply_day(state, "quiet_day", "strengthen_defenses")

    assert after["wood"] == 10
    assert after["security"] == 5
    assert event_record["effects"]["wood"] == -10
    assert event_record["effects"]["security"] == 1


def test_strengthen_defenses_without_enough_wood_logs_failure():
    state = state_with(wood=5, security=4, morale=7)

    after, event_record = apply_day(state, "quiet_day", "strengthen_defenses")

    assert after["wood"] == 5
    assert after["security"] == 4
    assert after["morale"] == 7
    assert event_record["leadership_action"] == "failed_strengthen_defenses"
    assert "not enough wood" in event_record["summary"]


def test_illness_can_reduce_health():
    state = state_with(health=6)

    after, event_record = apply_day(state, "illness", "preserve_resources")

    assert after["health"] == 5
    assert event_record["effects"]["health"] == -1


def test_tending_sick_can_offset_illness_health_loss():
    state = state_with(health=6)

    after, event_record = apply_day(state, "illness", "tend_the_sick")

    assert after["health"] == 7
    assert event_record["leadership_action"] == "tend_the_sick"
    assert event_record["effects"]["health"] == 1


def test_chaos_gods_reduce_health_security_and_morale():
    state = state_with(health=6, security=5, morale=7)

    after, event_record = apply_day(state, "chaos_gods", "preserve_resources")

    assert after["health"] == 5
    assert after["security"] == 4
    assert after["morale"] == 6
    assert event_record["effects"]["health"] == -1
    assert event_record["effects"]["security"] == -1
    assert event_record["effects"]["morale"] == -1


def test_wolf_attack_uses_severity_and_records_details():
    state = state_with(security=4, morale=7, health=6)

    after, event_record = apply_day(
        state,
        {"world_event": "wolf_attack", "severity": 3},
        "preserve_resources",
    )

    assert after["security"] == 2
    assert after["health"] == 4
    assert after["population"] == 99
    assert event_record["event_details"] == {"severity": 3}
    assert event_record["people_events"]["deaths"][0]["cause"] == "wolf_attack"


def test_strengthen_defenses_reduces_wolf_attack_damage():
    state = state_with(security=4, wood=20, morale=7, health=6)

    after, event_record = apply_day(
        state,
        {"world_event": "wolf_attack", "severity": 3},
        "strengthen_defenses",
    )

    assert after["wood"] == 10
    assert after["security"] == 4
    assert after["health"] == 5
    assert after["population"] == 100
    assert "population" not in event_record["effects"]


def test_fighting_undead_can_destroy_risen_dead_without_spread():
    people = generate_people(5, colony_health=6, colony_morale=7)
    people[0]["status"]["alive"] = False
    people[0]["status"]["health"] = 0
    state = state_with(population=4, people=people, security=6, food=20)

    after, event_record = apply_day(
        state,
        {"world_event": "undead_rising", "severity": 3},
        "fight_undead",
    )

    assert after["population"] == 4
    assert after["undead_threat"]["active"] is False
    assert after["undead_threat"]["zombies"] == 0
    assert "undead" in after["known_threats"]
    assert event_record["undead_outcome"]["newly_risen"] == 1
    assert event_record["undead_outcome"]["killed_zombies"] == 1
    assert event_record["people_events"]["actions"][0]["type"] == "undead_rose"
    assert event_record["people_events"]["actions"][1]["type"] == "undead_destroyed"


def test_uncontained_undead_spread_creates_new_zombies():
    people = generate_people(5, colony_health=6, colony_morale=7)
    people[0]["status"]["alive"] = False
    people[0]["status"]["health"] = 0
    state = state_with(population=4, people=people, security=6, food=20)

    after, event_record = apply_day(
        state,
        {"world_event": "undead_rising", "severity": 3},
        "preserve_resources",
    )

    assert after["population"] == 3
    assert after["undead_threat"]["active"] is True
    assert after["undead_threat"]["zombies"] == 2
    assert event_record["undead_outcome"]["new_infections"] == 1
    assert event_record["people_events"]["deaths"][0]["cause"] == "undead_rising"


def test_containing_undead_stops_spread_and_costs_wood():
    people = generate_people(5, colony_health=6, colony_morale=7)
    people[0]["status"]["alive"] = False
    people[0]["status"]["health"] = 0
    state = state_with(population=4, people=people, security=6, wood=20, food=20)

    after, event_record = apply_day(
        state,
        {"world_event": "undead_rising", "severity": 3},
        "contain_undead",
    )

    assert after["population"] == 4
    assert after["wood"] == 15
    assert after["undead_threat"]["active"] is False
    assert after["undead_threat"]["contained_zombies"] == 1
    assert event_record["undead_outcome"]["contained_zombies"] == 1
    assert event_record["people_events"]["actions"][1]["type"] == "undead_contained"


def test_storm_uses_severity_and_weather_context():
    environment = {
        "date": {
            "year": 1,
            "day_of_year": 50,
            "month": "February",
            "month_number": 2,
            "day_of_month": 19,
            "season": "winter",
        },
        "weather": {
            "season": "winter",
            "condition": "winter_storm",
            "severity": 4,
            "summary": "A winter storm threatened the colony's shelters and stores.",
        },
    }
    state = state_with(day=50, food=120, wood=60, health=6, morale=7)

    after, event_record = apply_day(
        state,
        {"world_event": "storm", "severity": 4},
        "preserve_resources",
        environment=environment,
    )

    assert after["food"] == 14
    assert after["wood"] == 54
    assert after["health"] == 5
    assert after["morale"] == 5
    assert event_record["date"]["month"] == "February"
    assert event_record["event_details"] == {"severity": 4}
    assert event_record["weather_effects"] == {"wood": -2, "morale": -1}


def test_old_apply_event_wrapper_still_advances_a_day():
    state = state_with(day=4)

    after, event_record = apply_event(state, "good_harvest")

    assert after["day"] == 5
    assert event_record["world_event"] == "good_harvest"
    assert event_record["leadership_action"] == "preserve_resources"

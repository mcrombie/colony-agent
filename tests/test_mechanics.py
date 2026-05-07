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


def test_stat_clamping():
    state = state_with(morale=12, security=-3, health=15)

    clamped = clamp_state(state)

    assert clamped["morale"] == 10
    assert clamped["security"] == 0
    assert clamped["health"] == 10


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


def test_good_harvest_creates_population_scaled_food_buffer():
    state = state_with(food=0, population=7, people=generate_people(7))

    after, event_record = apply_day(state, "good_harvest", "preserve_resources")

    assert after["food"] == 28
    assert event_record["effects"]["food"] == 28
    assert event_record["survival_effects"] == {"food": -7}


def test_expand_fields_can_rescue_a_small_starving_colony():
    people = generate_people(7, colony_health=2, colony_morale=0)
    for person in people:
        person["status"]["hunger"] = 2
    state = state_with(food=0, population=7, people=people)

    after, event_record = apply_day(state, "quiet_day", "expand_fields")

    assert after["food"] == 14
    assert after["population"] == 7
    assert event_record["effects"]["food"] == 14
    assert all(person["status"]["hunger"] == 1 for person in after["people"])


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


def test_rationing_does_not_reduce_minimum_food_need_and_costs_morale():
    state = state_with(food=120, population=100, morale=7)

    after, event_record = apply_day(state, "quiet_day", "ration_food")

    assert daily_food_needed(100, "ration_food") == 100
    assert after["food"] == 20
    assert after["morale"] == 6
    assert event_record["effects"]["food"] == -100
    assert event_record["effects"]["morale"] == -1


def test_morale_effects_are_preserved_when_people_drive_stats():
    state = state_with(
        morale=5,
        people=generate_people(100, colony_health=6, colony_morale=5),
    )

    after, event_record = apply_day(state, "good_harvest", "preserve_resources")

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

    assert after["health"] == 6
    assert event_record["leadership_action"] == "tend_the_sick"
    assert "health" not in event_record["effects"]


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
    assert after["population"] == 100
    assert "population" not in event_record["effects"]


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

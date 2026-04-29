from copy import deepcopy

from src.mechanics import apply_day, apply_event, clamp_state, daily_food_needed

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


def test_starvation_reduces_population_when_food_runs_out():
    state = state_with(food=0, population=100)

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert after["food"] == 0
    assert after["population"] == 95
    assert event_record["effects"]["population"] == -5


def test_day_increments():
    state = state_with(day=9)

    after, _ = apply_day(state, "good_harvest", "preserve_resources")

    assert after["day"] == 10


def test_daily_food_is_consumed_regardless_of_event():
    state = state_with(food=120, population=100)

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert after["food"] == 115
    assert event_record["survival_effects"] == {"food": -5}


def test_rationing_reduces_daily_food_need_but_costs_morale():
    state = state_with(food=120, population=100, morale=7)

    after, event_record = apply_day(state, "quiet_day", "ration_food")

    assert daily_food_needed(100, "ration_food") == 3
    assert after["food"] == 117
    assert after["morale"] == 6
    assert event_record["effects"]["food"] == -3
    assert event_record["effects"]["morale"] == -1


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


def test_old_apply_event_wrapper_still_advances_a_day():
    state = state_with(day=4)

    after, event_record = apply_event(state, "good_harvest")

    assert after["day"] == 5
    assert event_record["world_event"] == "good_harvest"
    assert event_record["leadership_action"] == "preserve_resources"

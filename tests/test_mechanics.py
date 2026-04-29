from copy import deepcopy

from src.mechanics import apply_event, clamp_state

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

    after, event_record = apply_event(state, "quiet_day")

    assert after["food"] == 0
    assert event_record["effects"]["food"] == -3


def test_day_increments():
    state = state_with(day=9)

    after, _ = apply_event(state, "good_harvest")

    assert after["day"] == 10


def test_construction_consumes_wood_and_improves_security():
    state = state_with(wood=20, security=4)

    after, event_record = apply_event(state, "construction")

    assert after["wood"] == 10
    assert after["security"] == 5
    assert event_record["effects"]["wood"] == -10
    assert event_record["effects"]["security"] == 1


def test_illness_can_reduce_health():
    state = state_with(health=6)

    after, event_record = apply_event(state, "illness")

    assert after["health"] == 5
    assert event_record["effects"]["health"] == -1


def test_chaos_gods_reduce_health_security_and_morale():
    state = state_with(health=6, security=5, morale=7)

    after, event_record = apply_event(state, "chaos_gods")

    assert after["health"] == 5
    assert after["security"] == 4
    assert after["morale"] == 6
    assert event_record["effects"] == {
        "health": -1,
        "security": -1,
        "morale": -1,
    }

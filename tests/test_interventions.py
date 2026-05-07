from copy import deepcopy

import pytest

from src.interventions import apply_company_interventions
from src.people import ensure_people_exist, generate_people

BASE_STATE = {
    "day": 1,
    "colony_name": "Blergen",
    "population": 0,
    "food": 0,
    "wood": 0,
    "morale": 0,
    "security": 0,
    "health": 0,
    "known_threats": ["wolves", "winter"],
    "event_log": [],
    "people": [],
}


def state_with(**overrides):
    state = deepcopy(BASE_STATE)
    state.update(overrides)
    return state


def test_send_settlers_revives_empty_colony_with_new_people():
    state, records = apply_company_interventions(
        state_with(company_interventions=[{"type": "send_settlers"}])
    )

    assert state["population"] == 100
    assert state["health"] == 6
    assert state["morale"] == 6
    assert len(state["people"]) == 100
    assert state["people"][0]["id"] == "person_001"
    assert records[0]["effects"] == {"population": 100}
    assert "Blergen Company sent 100 new settlers" in records[0]["summary"]
    assert "company_interventions" not in state


def test_send_settlers_does_not_reuse_dead_colonist_ids():
    people = generate_people(3)
    for person in people:
        person["status"]["alive"] = False
        person["status"]["health"] = 0
    old_state = ensure_people_exist(state_with(people=people, population=0))

    state, _ = apply_company_interventions(
        {
            **old_state,
            "company_interventions": [{"type": "send_settlers", "count": 2}],
        }
    )

    assert state["population"] == 2
    assert [person["id"] for person in state["people"][-2:]] == [
        "person_004",
        "person_005",
    ]


def test_send_food_adds_configured_food_amount():
    state, records = apply_company_interventions(
        state_with(food=4, company_interventions=[{"type": "send_food", "amount": 37}])
    )

    assert state["food"] == 41
    assert records[0]["effects"] == {"food": 37}


def test_additional_interventions_are_applied_after_state_queue():
    state, records = apply_company_interventions(
        state_with(company_interventions=[{"type": "send_food", "amount": 10}]),
        additional_interventions=[{"type": "send_food", "amount": 5}],
    )

    assert state["food"] == 15
    assert [record["effects"] for record in records] == [
        {"food": 10},
        {"food": 5},
    ]


def test_send_supplies_adds_wood_and_caps_security():
    state, records = apply_company_interventions(
        state_with(
            wood=2,
            security=9,
            company_interventions=[{"type": "send_supplies", "wood": 40, "security": 4}],
        )
    )

    assert state["wood"] == 42
    assert state["security"] == 10
    assert records[0]["effects"] == {"wood": 40, "security": 1}


def test_unknown_company_intervention_fails_loudly():
    with pytest.raises(ValueError, match="Unknown Blergen Company intervention"):
        apply_company_interventions(
            state_with(company_interventions=[{"type": "summon_dragon"}])
        )

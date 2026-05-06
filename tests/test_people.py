from copy import deepcopy

from src.mechanics import apply_day
from src.narrative import write_daily_entry, write_personal_history_entry
from src.people import (
    character_context_for_prompt,
    derived_colony_stats,
    ensure_people_exist,
    generate_people,
    living_population,
    sync_derived_colony_stats,
)

BASE_STATE = {
    "day": 1,
    "colony_name": "Blergen",
    "population": 12,
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


def test_ensure_people_exist_creates_named_individuals():
    state = ensure_people_exist(state_with(population=12, health=3, morale=4))

    assert state["population"] == 12
    assert len(state["people"]) == 12
    assert len({person["id"] for person in state["people"]}) == 12
    assert len({person["name"] for person in state["people"]}) == 12

    first_person = state["people"][0]
    assert first_person["name"] == "Ada Aster"
    assert first_person["status"]["alive"] is True
    assert first_person["status"]["health"] == 3
    assert first_person["status"]["morale"] == 4
    assert first_person["personality"]["traits"]
    assert first_person["personality"]["temperament"]
    assert first_person["relationships"] == {
        "friends": [],
        "family": [],
        "rivals": [],
    }


def test_people_drive_aggregate_population_health_and_morale():
    state = state_with(
        population=99,
        health=9,
        morale=9,
        people=generate_people(4, colony_health=6, colony_morale=7),
    )
    state["people"][0]["status"]["alive"] = False
    state["people"][0]["status"]["health"] = 0
    state["people"][1]["status"]["health"] = 2
    state["people"][2]["status"]["morale"] = 3

    sync_derived_colony_stats(state)

    assert state["population"] == 3
    assert state["health"] == 4
    assert state["morale"] == 5
    assert derived_colony_stats(state) == {
        "population": 3,
        "health": 4,
        "morale": 5,
    }


def test_character_context_for_prompt_is_bounded_and_compact():
    state = state_with(
        people=generate_people(12, colony_health=6, colony_morale=7),
    )
    state["people"][0]["story"]["notable_events"] = [
        "Ada Aster stood watch on day 1.",
        "Ada Aster repaired a gate on day 2.",
        "Ada Aster checked the fields on day 3.",
    ]

    context = character_context_for_prompt(state, max_people=3)

    assert len(context["featured_colonists"]) == 3
    assert context["living_population"] == 12
    assert context["status_summary"]["average_health"] == 6
    assert context["featured_colonists"][0]["recent_story"] == [
        "Ada Aster repaired a gate on day 2.",
        "Ada Aster checked the fields on day 3.",
    ]
    assert "relationships" not in context["featured_colonists"][0]


def test_population_loss_marks_named_people_dead():
    state = state_with(
        population=12,
        food=0,
        people=generate_people(12, colony_health=5, colony_morale=6),
    )

    after, event_record = apply_day(state, "quiet_day", "preserve_resources")

    assert after["population"] == 11
    assert living_population(after) == 11
    assert len(event_record["people_events"]["deaths"]) == 1

    death = event_record["people_events"]["deaths"][0]
    dead_person = next(person for person in after["people"] if person["id"] == death["id"])
    assert death["name"] == dead_person["name"]
    assert death["cause"] == "starvation"
    assert dead_person["status"]["alive"] is False
    assert dead_person["status"]["health"] == 0
    assert dead_person["story"]["notable_events"] == [
        f"{dead_person['name']} died of starvation on day 1."
    ]


def test_illness_population_loss_records_illness_death():
    state = state_with(
        population=12,
        health=2,
        people=generate_people(12, colony_health=2, colony_morale=6),
    )

    after, event_record = apply_day(state, "illness", "preserve_resources")

    assert after["population"] == 11
    assert event_record["people_events"]["deaths"][0]["cause"] == "illness"


def test_illness_targets_named_people_before_any_death():
    state = state_with(
        population=12,
        health=6,
        people=generate_people(12, colony_health=6, colony_morale=6),
    )

    after, event_record = apply_day(state, "illness", "preserve_resources")

    illness = event_record["people_events"]["illnesses"][0]
    sick_person_id = illness["people"][0]["id"]
    sick_person = next(person for person in after["people"] if person["id"] == sick_person_id)
    assert sick_person["status"]["health"] == 4
    assert sick_person["status"]["morale"] == 5
    assert after["health"] == derived_colony_stats(after)["health"]
    assert after["morale"] == derived_colony_stats(after)["morale"]
    assert sick_person["story"]["notable_events"] == [
        f"{sick_person['name']} fell ill on day 1."
    ]


def test_dispute_creates_named_rivals():
    state = state_with(people=generate_people(12, colony_health=6, colony_morale=6))

    after, event_record = apply_day(state, "dispute", "preserve_resources")

    conflict = event_record["people_events"]["conflicts"][0]
    first_id = conflict["people"][0]["id"]
    second_id = conflict["people"][1]["id"]
    first = next(person for person in after["people"] if person["id"] == first_id)
    second = next(person for person in after["people"] if person["id"] == second_id)
    assert second_id in first["relationships"]["rivals"]
    assert first_id in second["relationships"]["rivals"]
    assert first["status"]["morale"] == 5
    assert second["status"]["morale"] == 5


def test_mediation_can_resolve_same_day_dispute():
    state = state_with(people=generate_people(12, colony_health=6, colony_morale=6))

    after, event_record = apply_day(state, "dispute", "mediate_dispute")

    conflict = event_record["people_events"]["conflicts"][0]
    first_id = conflict["people"][0]["id"]
    second_id = conflict["people"][1]["id"]
    first = next(person for person in after["people"] if person["id"] == first_id)
    second = next(person for person in after["people"] if person["id"] == second_id)
    assert second_id not in first["relationships"]["rivals"]
    assert first_id not in second["relationships"]["rivals"]
    assert event_record["people_events"]["actions"][0]["type"] == "mediated_dispute"


def test_discovery_credits_a_named_scout():
    state = state_with(people=generate_people(12, colony_health=6, colony_morale=6))

    after, event_record = apply_day(state, "discovery", "preserve_resources")

    discovery = event_record["people_events"]["discoveries"][0]
    scout_id = discovery["people"][0]["id"]
    scout = next(person for person in after["people"] if person["id"] == scout_id)
    assert scout["role"] == "scout"
    assert scout["status"]["morale"] == 7
    assert "discovered useful clay near the riverbank on day 1" in (
        scout["story"]["notable_events"][0]
    )


def test_leadership_action_targets_relevant_named_people():
    state = state_with(people=generate_people(12, colony_health=6, colony_morale=6))

    after, event_record = apply_day(state, "quiet_day", "gather_wood")

    action = event_record["people_events"]["actions"][0]
    worker_ids = [person["id"] for person in action["people"]]
    workers = [person for person in after["people"] if person["id"] in worker_ids]
    assert action["type"] == "gathered_wood"
    assert {person["role"] for person in workers} == {"woodcutter", "carpenter"}
    assert all(person["story"]["notable_events"] for person in workers)


def test_history_entry_names_people_who_died():
    state_before = ensure_people_exist(state_with(population=12, food=0))
    state_after, event_record = apply_day(state_before, "quiet_day", "preserve_resources")

    entry = write_daily_entry(state_before, event_record, state_after)

    dead_name = event_record["people_events"]["deaths"][0]["name"]
    assert f"{dead_name} died." in entry


def test_history_entry_includes_person_level_story_beat():
    state_before = ensure_people_exist(state_with(population=12))
    state_after, event_record = apply_day(state_before, "discovery", "preserve_resources")

    entry = write_daily_entry(state_before, event_record, state_after)

    discovery_summary = event_record["people_events"]["discoveries"][0]["summary"]
    assert discovery_summary in entry


def test_personal_history_entry_records_individual_status_changes():
    state_before = ensure_people_exist(state_with(population=12))
    state_after, event_record = apply_day(state_before, "illness", "preserve_resources")

    entry = write_personal_history_entry(state_before, event_record, state_after)

    sick_person = event_record["people_events"]["illnesses"][0]["people"][0]
    assert entry.startswith("Day 1 - Blergen Personal Stories:")
    assert f"- {sick_person['name']} (" in entry
    assert "fell ill" in entry
    assert "health 6->4" in entry
    assert "morale 7->6" in entry


def test_personal_history_entry_is_empty_without_people_events():
    state = ensure_people_exist(state_with(population=12))
    event_record = {
        "day": 1,
        "world_event": "quiet_day",
        "leadership_action": "preserve_resources",
        "effects": {},
        "people_events": {},
    }

    entry = write_personal_history_entry(state, event_record, state)

    assert entry == ""

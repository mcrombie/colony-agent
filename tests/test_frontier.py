"""Frontier migration, survival, and progression across real simulated days."""

from copy import deepcopy

from src.environment import environment_for_day
from src.event_selector import choose_leadership_action, choose_world_event
from src.frontier import daily_frontier_effects, ensure_frontier, prepare_frontier
from src.mechanics import apply_day
from src.narrative import write_daily_entry, write_personal_history_entry
from src.people import generate_people


def colony(**overrides):
    state = {
        "day": 1, "colony_name": "Blergen", "population": 12,
        "food": 120, "wood": 60, "morale": 7, "security": 5,
        "health": 7, "known_threats": [], "event_log": [],
    }
    state.update(overrides)
    return state


def test_migration_is_idempotent_and_does_not_advance_or_mutate_the_save():
    original = colony(frontier={"knowledge": 8, "projects": [
        {"id": "kitchen_gardens", "progress": 10, "completed_day": 8},
    ]})
    saved = deepcopy(original)

    migrated = ensure_frontier(original)

    assert original == saved
    assert migrated["day"] == original["day"]
    assert len(migrated["frontier"]["projects"]) == 6
    assert migrated["frontier"]["projects"][0]["completed_day"] == 8
    assert migrated["frontier"]["knowledge"] == 8
    assert ensure_frontier(migrated) == migrated
    assert "people" not in migrated


def test_abandoned_colony_gets_new_settlers_without_resurrecting_or_erasing_history():
    dead = generate_people(3)
    for person in dead:
        person["status"].update(alive=False, health=0)
    history = [{"day": 9, "summary": "The last old colonists were lost."}]
    state = colony(day=50, population=0, people=dead, event_log=history, food=0, wood=0)

    rebuilt, records = prepare_frontier(state)
    repeated, repeated_records = prepare_frontier(rebuilt)

    assert len(records) == 1
    assert records[0]["type"] == "frontier_relief"
    assert rebuilt["population"] == 12
    assert rebuilt["people"][:3] == dead
    assert rebuilt["event_log"] == history
    assert len({p["id"] for p in rebuilt["people"]}) == 15
    assert rebuilt["food"] == 120
    assert rebuilt["wood"] == 40
    assert repeated["population"] == 12
    assert repeated_records == []
    assert state["population"] == 0


def test_later_extinction_waits_thirty_days_for_relief():
    state, _ = prepare_frontier(colony(population=0, people=[]))
    for person in state["people"]:
        person["status"].update(alive=False, health=0)
    state["day"] = 5

    waiting, records = prepare_frontier(state)
    assert waiting["population"] == 0
    assert records == []
    waiting["day"] = 34
    waiting, records = prepare_frontier(waiting)
    assert records == []
    waiting["day"] = 35
    rebuilt, records = prepare_frontier(waiting)

    assert rebuilt["population"] == 12
    assert len(rebuilt["people"]) == 24
    assert len(records) == 1
    assert rebuilt["frontier"]["relief_convoys"] == 2


def test_a_previously_inhabited_frontier_does_not_replace_its_dead_the_next_day():
    state, _ = prepare_frontier(colony())
    for person in state["people"]:
        person["status"].update(alive=False, health=0)
    state["day"] = 20
    waiting, records = prepare_frontier(state)
    assert records == []
    assert waiting["population"] == 0
    waiting["day"] = 50
    rebuilt, records = prepare_frontier(waiting)
    assert len(records) == 1
    assert rebuilt["population"] == 12


def test_routine_production_requires_living_workers_and_respects_reserve_caps():
    active = ensure_frontier(colony(food=120, wood=10))
    winter = environment_for_day(1)
    effects = daily_frontier_effects(active, winter)
    assert effects["food"] == 9
    assert effects["wood"] == 2
    active["population"] = 0
    assert daily_frontier_effects(active, winter) == {}
    active.update(population=12, food=2000, wood=800)
    effects = daily_frontier_effects(active, winter)
    assert effects.get("food", 0) == 0
    assert effects.get("wood", 0) == 0
    assert active["food"] == 2000


def test_leadership_accelerates_permanent_work_and_food_benefits_start_after_completion():
    state, _ = prepare_frontier(colony(day=100))
    ordinary, _ = apply_day(state, "quiet_day", "preserve_resources")
    focused, _ = apply_day(state, "quiet_day", "expand_fields")
    assert ordinary["frontier"]["projects"][0]["progress"] == 1
    assert focused["frontier"]["projects"][0]["progress"] == 2
    assert focused["wood"] == ordinary["wood"] - 1
    for _ in range(4):
        focused, record = apply_day(focused, "quiet_day", "expand_fields")
    assert focused["frontier"]["projects"][0]["completed_day"] == 104
    assert record["frontier"]["completed"][0]["id"] == "kitchen_gardens"
    next_effects = daily_frontier_effects(focused, environment_for_day(focused["day"]))
    assert next_effects["food"] > record["frontier"]["production"]["food"]


def test_named_expeditions_discover_permanent_sites_and_shelter_in_storms():
    state, _ = prepare_frontier(colony(day=100))
    state, _ = apply_day(state, "quiet_day", "send_scouts")
    expedition = deepcopy(state["frontier"]["expedition"])
    assert expedition["progress"] == 3
    assert len(expedition["crew"]) == 2
    sheltered, record = apply_day(state, {"world_event": "storm", "severity": 1}, "send_scouts")
    assert sheltered["frontier"]["expedition"]["progress"] == 3
    assert "sheltered" in record["frontier"]["expedition_status"]
    discovered, record = apply_day(sheltered, "quiet_day", "send_scouts")
    assert discovered["frontier"]["sites"][0]["discovered"] is True
    assert discovered["frontier"]["expedition"] is None
    assert record["frontier"]["discoveries"][0]["crew"] == expedition["crew"]
    scout = next(p for p in discovered["people"] if p["id"] == expedition["crew"][0]["id"])
    assert any("Silver river" in note for note in scout["story"]["notable_events"])
    assert "sheltered bend" in write_daily_entry(sheltered, record, discovered)
    personal_entry = write_personal_history_entry(sheltered, record, discovered)
    assert expedition["crew"][0]["name"] in personal_entry
    assert "expedition to Silver river" in personal_entry


def test_year_of_frontier_life_survives_and_keeps_discovering_after_the_first_map(monkeypatch):
    monkeypatch.setenv("COLONY_AI_MODE", "off")
    state, _ = prepare_frontier(colony())
    min_population = state["population"]
    for _ in range(365):
        world_event = choose_world_event(state)
        action = choose_leadership_action(state, world_event)
        state, record = apply_day(state, world_event, action)
        min_population = min(min_population, state["population"])
        assert state["food"] >= 0
        assert "missed_rations" not in record["survival_effects"]
    frontier = state["frontier"]
    assert min_population == 12
    assert all(p["completed_day"] is not None for p in frontier["projects"])
    assert all(s["discovered"] for s in frontier["sites"])
    assert frontier["expeditions_completed"] > len(frontier["sites"])
    assert frontier["knowledge"] >= 25
    assert {"settlement", "full_map", "archive_25"} <= {m["id"] for m in frontier["milestones"]}
    assert len(frontier["timeline"]) == 120
    assert frontier["timeline"][-1]["day"] == 365
    assert frontier["timeline"][-1]["population"] == state["population"]
    assert frontier["relief_convoys"] == 0

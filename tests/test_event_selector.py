from copy import deepcopy

from src import event_selector

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


def test_rules_mode_uses_rule_based_selector(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(
        event_selector,
        "choose_rule_based_event",
        lambda current_state: "quiet_day",
    )

    event_type = event_selector.choose_event(state, mode="rules")

    assert event_type == "quiet_day"


def test_openai_mode_uses_openai_selector(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        event_selector,
        "choose_event_with_openai",
        lambda current_state: "discovery",
    )

    event_type = event_selector.choose_event(state, mode="openai")

    assert event_type == "discovery"

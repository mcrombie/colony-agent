from copy import deepcopy

import pytest

from src import event_selector
from src.constants import CHAOS_GODS_EVENT_TYPE, PRESERVE_RESOURCES_ACTION_TYPE
from src.openai_selector import (
    MissingOpenAIConfigError,
    OpenAIAPICallError,
    _normalize_world_event_decision,
    _parse_with_retries,
    _state_for_leadership_prompt,
    _state_for_world_prompt,
)
from src.people import generate_people

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


def state_with_people(count=12):
    state = deepcopy(BASE_STATE)
    state["population"] = count
    state["people"] = generate_people(count, colony_health=6, colony_morale=7)
    return state


def test_choose_world_event_uses_openai_selector(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_world_event_with_openai",
        lambda current_state, environment=None: {
            "world_event": "discovery",
            "reasoning": "test",
        },
    )

    world_event = event_selector.choose_world_event(state)

    assert world_event["world_event"] == "discovery"


def test_choose_leadership_action_uses_openai_selector(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_leadership_action_with_openai",
        lambda current_state, world_event: "send_scouts",
    )

    leadership_action = event_selector.choose_leadership_action(state, "quiet_day")

    assert leadership_action == "send_scouts"


def test_missing_openai_key_fails_loudly(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(MissingOpenAIConfigError, match="OPENAI_API_KEY is not set"):
        event_selector.choose_world_event(state)


def test_api_call_failure_becomes_chaos_gods_event(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_world_event_with_openai",
        lambda current_state, environment=None: (_ for _ in ()).throw(
            OpenAIAPICallError("OpenAI API call failed.")
        ),
    )

    world_event = event_selector.choose_world_event(state)

    assert world_event["world_event"] == CHAOS_GODS_EVENT_TYPE
    assert world_event["severity"] == 3


def test_leadership_api_failure_preserves_resources(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_leadership_action_with_openai",
        lambda current_state, world_event: (_ for _ in ()).throw(
            OpenAIAPICallError("OpenAI API call failed.")
        ),
    )

    leadership_action = event_selector.choose_leadership_action(state, "quiet_day")

    assert leadership_action == PRESERVE_RESOURCES_ACTION_TYPE


def test_api_call_failure_logs_sanitized_warning(monkeypatch, capsys):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_world_event_with_openai",
        lambda current_state, environment=None: (_ for _ in ()).throw(
            OpenAIAPICallError("OpenAI API call failed: AuthenticationError")
        ),
    )

    event_selector.choose_world_event(state)

    captured = capsys.readouterr()
    assert "::warning title=OpenAI deity selector failed::" in captured.out
    assert "AuthenticationError" in captured.out


def test_president_api_call_failure_logs_sanitized_warning(monkeypatch, capsys):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_leadership_action_with_openai",
        lambda current_state, world_event: (_ for _ in ()).throw(
            OpenAIAPICallError("OpenAI API call failed: AuthenticationError")
        ),
    )

    event_selector.choose_leadership_action(state, "quiet_day")

    captured = capsys.readouterr()
    assert "::warning title=OpenAI president selector failed::" in captured.out
    assert "AuthenticationError" in captured.out


def test_openai_parse_retries_transient_failure(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr("src.openai_selector.time.sleep", lambda seconds: None)

    class Responses:
        def parse(self, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise ConnectionError("temporary connection error")
            return "ok"

    class Client:
        responses = Responses()

    result = _parse_with_retries(
        client=Client(),
        model="test-model",
        input_payload=[],
        text_format=object,
    )

    assert result == "ok"
    assert calls["count"] == 2


def test_world_prompt_includes_bounded_character_context():
    state = state_with_people(count=12)
    state["people"][0]["story"]["notable_events"].append(
        "Ada Aster helped hold the storehouse line on day 1."
    )

    environment = {
        "date": {"month": "February", "day_of_month": 19, "season": "winter"},
        "weather": {"condition": "snow", "severity": 2, "season": "winter"},
    }
    prompt = _state_for_world_prompt(state, environment=environment)
    character_context = prompt["character_context"]

    assert character_context["living_population"] == 12
    assert character_context["role_counts"]["scout"] == 1
    assert prompt["current_state"]["year"] == 1
    assert len(character_context["featured_colonists"]) <= 8
    assert prompt["environment"] == environment
    assert "wolf_attack" in prompt["allowed_world_events"]
    assert "storm" in prompt["allowed_world_events"]
    assert "undead_rising" in prompt["allowed_world_events"]
    assert prompt["current_state"]["dead_population"] == 0
    assert "people" not in prompt
    assert {
        "id",
        "name",
        "age",
        "role",
        "traits",
        "temperament",
        "fear",
        "desire",
        "status",
        "relationship_counts",
        "recent_story",
    } <= set(character_context["featured_colonists"][0])


def test_leadership_prompt_selects_event_relevant_colonists():
    state = state_with_people(count=12)
    state["president"] = {
        "id": state["people"][0]["id"],
        "name": state["people"][0]["name"],
        "since_day": 1,
    }

    prompt = _state_for_leadership_prompt(
        state,
        {"world_event": "discovery", "severity": 1},
    )
    featured_roles = {
        person["role"]
        for person in prompt["character_context"]["featured_colonists"][:2]
    }

    assert featured_roles == {"scout", "forager"}
    assert prompt["president"]["id"] == state["people"][0]["id"]
    assert prompt["president"]["name"] == state["people"][0]["name"]
    assert prompt["today_world_event"] == "discovery"
    assert prompt["today_event_details"]["severity"] == 1
    assert "fight_undead" in prompt["allowed_leadership_actions"]
    assert "Named colonists can inform priorities" in prompt["important_rules"][-1]


def test_illness_leadership_prompt_prioritizes_fragile_colonists():
    state = state_with_people(count=12)
    state["people"][7]["status"]["health"] = 1
    state["people"][2]["status"]["health"] = 2

    prompt = _state_for_leadership_prompt(state, "illness")
    featured = prompt["character_context"]["featured_colonists"]

    assert featured[0]["status"]["health"] == 1
    assert featured[1]["status"]["health"] == 2


def test_world_event_decision_normalizes_severity():
    decision = _normalize_world_event_decision(
        {"world_event": "wolf_attack", "severity": 8, "reasoning": "wolves"},
    )

    assert decision == {
        "world_event": "wolf_attack",
        "severity": 5,
        "reasoning": "wolves",
    }


def test_storm_decision_defaults_to_weather_severity():
    decision = _normalize_world_event_decision(
        {"world_event": "storm", "reasoning": "bad weather"},
        environment={"weather": {"severity": 4}},
    )

    assert decision["severity"] == 4


def test_undead_rising_decision_normalizes_severity():
    decision = _normalize_world_event_decision(
        {"world_event": "undead_rising", "severity": 9, "reasoning": "old dead"},
    )

    assert decision == {
        "world_event": "undead_rising",
        "severity": 5,
        "reasoning": "old dead",
    }

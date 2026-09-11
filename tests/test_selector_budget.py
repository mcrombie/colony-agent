"""No live services: exercise cost limits and the deployed local policy."""

from copy import deepcopy
import sys
from types import SimpleNamespace

import pytest

from src import event_selector, openai_selector
from src.frontier import prepare_frontier
from src.mechanics import apply_day


def colony(**overrides):
    state = {"day": 7, "colony_name": "Blergen", "population": 12,
             "food": 120, "wood": 60, "health": 7, "morale": 7,
             "security": 5, "known_threats": ["wolves", "winter"], "event_log": []}
    state.update(overrides)
    return state


@pytest.fixture(autouse=True)
def no_local_secrets(monkeypatch):
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.delenv("COLONY_AI_MODE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "mock-test-key")


@pytest.mark.parametrize("mode", [None, "off", "invalid", "true", "0"])
def test_default_off_and_unknown_modes_never_call_either_ai_role(monkeypatch, mode):
    if mode is not None:
        monkeypatch.setenv("COLONY_AI_MODE", mode)
    def forbidden(*args, **kwargs):
        pytest.fail("Default/off mode must not contact an AI service")
    monkeypatch.setattr(event_selector, "choose_world_event_with_openai", forbidden)
    monkeypatch.setattr(event_selector, "choose_leadership_action_with_openai", forbidden)
    state = colony()
    event = event_selector.choose_world_event(state)
    assert event["selector"] == "local"
    assert event_selector.choose_leadership_action(state, event) == "send_scouts"


@pytest.mark.parametrize("mode,days,expected", [
    ("weekly", [1, 6, 7, 8, 13, 14], [7, 14]),
    ("daily", [1, 6, 7, 8], [1, 6, 7, 8]),
])
def test_only_eligible_days_call_optional_roles(monkeypatch, mode, days, expected):
    calls = {"world": [], "leadership": []}
    monkeypatch.setenv("COLONY_AI_MODE", mode)
    def world(state, environment=None):
        calls["world"].append(state["day"])
        return {"world_event": "quiet_day", "reasoning": "mock"}
    def leader(state, event):
        calls["leadership"].append(state["day"])
        return "send_scouts"
    monkeypatch.setattr(event_selector, "choose_world_event_with_openai", world)
    monkeypatch.setattr(event_selector, "choose_leadership_action_with_openai", leader)
    for day in days:
        state = colony(day=day)
        event = event_selector.choose_world_event(state)
        event_selector.choose_leadership_action(state, event)
    assert calls == {"world": expected, "leadership": expected}


def test_missing_sdk_uses_local_decisions_and_missing_key_never_calls(monkeypatch):
    monkeypatch.setenv("COLONY_AI_MODE", "daily")
    def missing(*args, **kwargs):
        raise openai_selector.OpenAISelectorError("Optional SDK is unavailable")
    monkeypatch.setattr(event_selector, "choose_world_event_with_openai", missing)
    monkeypatch.setattr(event_selector, "choose_leadership_action_with_openai", missing)
    state = colony(health=2)
    event = event_selector.choose_world_event(state)
    assert event["world_event"] == "quiet_day"
    assert event["selector"] == "local_fallback"
    assert event_selector.choose_leadership_action(state, event) == "tend_the_sick"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(event_selector, "choose_world_event_with_openai", lambda *a, **k: pytest.fail("No key"))
    assert event_selector.choose_world_event(state)["selector"] == "local"


@pytest.mark.parametrize("model,reasoning", [("gpt-5.4-mini", {"effort": "low"}), ("generic-model", None)])
def test_parse_uses_fixed_output_cap_and_compatible_reasoning(model, reasoning):
    calls = []
    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_parsed={"world_event": "quiet_day"})
    openai_selector._parse_with_retries(
        SimpleNamespace(responses=SimpleNamespace(parse=parse)), model, [], object,
    )
    assert len(calls) == 1
    assert calls[0]["max_output_tokens"] == 384
    assert calls[0]["store"] is False
    assert calls[0].get("reasoning") == reasoning


def test_sdk_has_no_hidden_retries_and_twenty_second_timeout(monkeypatch):
    calls = []
    def fake_client(**kwargs):
        calls.append(kwargs)
        return object()
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=fake_client))
    monkeypatch.setitem(sys.modules, "pydantic", SimpleNamespace(BaseModel=object))
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    _, model, _ = openai_selector._openai_client()
    assert model == "gpt-5.4-mini"
    assert calls[0]["timeout"] == 20.0
    assert calls[0]["max_retries"] == 0


def test_incomplete_structured_response_is_a_single_failed_attempt():
    calls = []
    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_parsed=None)
    with pytest.raises(openai_selector.OpenAIAPICallError, match="output budget"):
        openai_selector._parse_with_retries(
            SimpleNamespace(responses=SimpleNamespace(parse=parse)), "gpt-5.4-mini", [], object,
        )
    assert len(calls) == 1


def test_prompt_excludes_unbounded_history_and_chart_data():
    state, _ = prepare_frontier(colony())
    state["event_log"] = [{"day": i, "world_event": "quiet_day", "summary": "x" * 10000,
                           "people_events": ["private marker"] * 1000} for i in range(20)]
    state["frontier"]["timeline"] = [{"day": i} for i in range(120)]
    prompt = openai_selector._state_for_world_prompt(state)
    assert len(prompt["recent_events"]) == 3
    assert all(len(e["summary"]) == 200 for e in prompt["recent_events"])
    assert all("people_events" not in e for e in prompt["recent_events"])
    assert "timeline" not in prompt["current_state"]["frontier"]
    assert len(prompt["character_context"]["featured_colonists"]) == 3


def test_local_decisions_are_repeatable_and_do_not_modify_state():
    state, _ = prepare_frontier(colony(day=101))
    before = deepcopy(state)
    first = event_selector.choose_world_event(state)
    second = event_selector.choose_world_event(state)
    assert first == second
    assert event_selector.choose_leadership_action(state, first) == event_selector.choose_leadership_action(state, second)
    assert before == state


def test_damaged_fifty_person_colony_recovers_without_replacement_settlers(monkeypatch):
    monkeypatch.setenv("COLONY_AI_MODE", "off")
    state, _ = prepare_frontier(colony(day=1802, population=50, health=1, morale=0, security=0, food=1218, wood=327))
    for _ in range(90):
        event = event_selector.choose_world_event(state)
        action = event_selector.choose_leadership_action(state, event)
        state, record = apply_day(state, event, action)
        assert state["population"] == 50
        assert "missed_rations" not in record["survival_effects"]
    assert state["health"] >= 5
    assert state["security"] >= 4
    assert state["morale"] >= 4
    assert state["frontier"]["relief_convoys"] == 0
    assert any(p["completed_day"] for p in state["frontier"]["projects"])
    assert state["frontier"]["expeditions_completed"] >= 1

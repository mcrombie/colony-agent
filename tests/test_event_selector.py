from copy import deepcopy

import pytest

from src import event_selector
from src.constants import CHAOS_GODS_EVENT_TYPE, PRESERVE_RESOURCES_ACTION_TYPE
from src.openai_selector import (
    MissingOpenAIConfigError,
    OpenAIAPICallError,
    _parse_with_retries,
)

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


def test_choose_world_event_uses_openai_selector(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_world_event_with_openai",
        lambda current_state: "discovery",
    )

    world_event = event_selector.choose_world_event(state)

    assert world_event == "discovery"


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
        lambda current_state: (_ for _ in ()).throw(
            OpenAIAPICallError("OpenAI API call failed.")
        ),
    )

    world_event = event_selector.choose_world_event(state)

    assert world_event == CHAOS_GODS_EVENT_TYPE


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
        lambda current_state: (_ for _ in ()).throw(
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

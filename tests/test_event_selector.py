from copy import deepcopy

import pytest

from src import event_selector
from src.constants import CHAOS_GODS_EVENT_TYPE
from src.openai_selector import MissingOpenAIConfigError, OpenAIAPICallError

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


def test_choose_event_uses_openai_selector(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_event_with_openai",
        lambda current_state: "discovery",
    )

    event_type = event_selector.choose_event(state)

    assert event_type == "discovery"


def test_missing_openai_key_fails_loudly(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(MissingOpenAIConfigError, match="OPENAI_API_KEY is not set"):
        event_selector.choose_event(state)


def test_api_call_failure_becomes_chaos_gods_event(monkeypatch):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_event_with_openai",
        lambda current_state: (_ for _ in ()).throw(
            OpenAIAPICallError("OpenAI API call failed.")
        ),
    )

    event_type = event_selector.choose_event(state)

    assert event_type == CHAOS_GODS_EVENT_TYPE


def test_api_call_failure_logs_sanitized_warning(monkeypatch, capsys):
    state = deepcopy(BASE_STATE)
    monkeypatch.setattr(event_selector, "load_local_env", lambda: None)
    monkeypatch.setattr(
        event_selector,
        "choose_event_with_openai",
        lambda current_state: (_ for _ in ()).throw(
            OpenAIAPICallError("OpenAI API call failed: AuthenticationError")
        ),
    )

    event_selector.choose_event(state)

    captured = capsys.readouterr()
    assert "::warning title=OpenAI selector failed::" in captured.out
    assert "AuthenticationError" in captured.out

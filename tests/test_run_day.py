from pathlib import Path

from src import run_day as run_day_module
from src.run_day import append_personal_history

SCRATCH_PATH = Path("tests/.tmp_people_history.md")


def test_append_personal_history_writes_nonempty_entry():
    try:
        SCRATCH_PATH.write_text("# Personal Stories\n", encoding="utf-8")

        append_personal_history(
            "Day 1 - Blergen Personal Stories:\n- Ada Aster worked.\n",
            SCRATCH_PATH,
        )

        assert SCRATCH_PATH.read_text(encoding="utf-8") == (
            "# Personal Stories\n"
            "\n"
            "Day 1 - Blergen Personal Stories:\n"
            "- Ada Aster worked.\n"
        )
    finally:
        SCRATCH_PATH.unlink(missing_ok=True)


def test_append_personal_history_ignores_empty_entry():
    try:
        SCRATCH_PATH.write_text("# Personal Stories\n", encoding="utf-8")

        append_personal_history("", SCRATCH_PATH)

        assert SCRATCH_PATH.read_text(encoding="utf-8") == "# Personal Stories\n"
    finally:
        SCRATCH_PATH.unlink(missing_ok=True)


def test_run_day_empty_colony_skips_openai_selectors(monkeypatch):
    saved = {}
    history_entries = []

    monkeypatch.setattr(
        run_day_module,
        "load_state",
        lambda: {
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
        },
    )
    monkeypatch.setattr(
        run_day_module,
        "choose_world_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("called deity")),
    )
    monkeypatch.setattr(
        run_day_module,
        "choose_leadership_action",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("called president")),
    )
    monkeypatch.setattr(run_day_module, "save_state", lambda state: saved.update(state))
    monkeypatch.setattr(run_day_module, "append_history", history_entries.append)
    monkeypatch.setattr(run_day_module, "append_personal_history", lambda entry: None)

    event_record = run_day_module.run_day()

    assert event_record["world_event"] == "empty_colony"
    assert event_record["leadership_action"] == "no_action"
    assert saved["population"] == 0
    assert saved["day"] == 2
    assert "president" not in history_entries[0]


def test_run_day_company_settlers_revive_before_selectors(monkeypatch):
    saved = {}
    calls = {"world": 0, "leadership": 0}

    monkeypatch.setattr(
        run_day_module,
        "load_state",
        lambda: {
            "day": 1,
            "colony_name": "Blergen",
            "population": 0,
            "food": 100,
            "wood": 0,
            "morale": 0,
            "security": 0,
            "health": 0,
            "known_threats": ["wolves", "winter"],
            "event_log": [],
            "people": [],
            "company_interventions": [{"type": "send_settlers", "count": 3}],
        },
    )

    def choose_world_event(state, environment=None):
        calls["world"] += 1
        assert state["population"] == 3
        return {"world_event": "quiet_day", "reasoning": "test"}

    def choose_leadership_action(state, world_event):
        calls["leadership"] += 1
        assert state["population"] == 3
        return "preserve_resources"

    monkeypatch.setattr(run_day_module, "choose_world_event", choose_world_event)
    monkeypatch.setattr(run_day_module, "choose_leadership_action", choose_leadership_action)
    monkeypatch.setattr(run_day_module, "save_state", lambda state: saved.update(state))
    monkeypatch.setattr(run_day_module, "append_history", lambda entry: None)
    monkeypatch.setattr(run_day_module, "append_personal_history", lambda entry: None)

    event_record = run_day_module.run_day()

    assert calls == {"world": 1, "leadership": 1}
    assert saved["population"] == 3
    assert saved["president"]["id"] == "person_003"
    assert "company_interventions" not in saved
    assert event_record["company_interventions"][0]["effects"] == {"population": 3}
    assert event_record["president"]["id"] == "person_003"


def test_run_day_accepts_cli_company_interventions(monkeypatch):
    saved = {}

    monkeypatch.setattr(
        run_day_module,
        "load_state",
        lambda: {
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
        },
    )
    monkeypatch.setattr(
        run_day_module,
        "choose_world_event",
        lambda state, environment=None: {"world_event": "quiet_day", "reasoning": "test"},
    )
    monkeypatch.setattr(
        run_day_module,
        "choose_leadership_action",
        lambda state, world_event: "preserve_resources",
    )
    monkeypatch.setattr(run_day_module, "save_state", lambda state: saved.update(state))
    monkeypatch.setattr(run_day_module, "append_history", lambda entry: None)
    monkeypatch.setattr(run_day_module, "append_personal_history", lambda entry: None)

    event_record = run_day_module.run_day(
        [
            {"type": "send_settlers", "count": 2},
            {"type": "send_food", "amount": 20},
            {"type": "send_supplies", "wood": 5, "security": 1},
        ]
    )

    assert saved["population"] == 2
    assert saved["food"] == 18
    assert saved["wood"] == 5
    assert saved["security"] == 1
    assert [record["type"] for record in event_record["company_interventions"]] == [
        "send_settlers",
        "send_food",
        "send_supplies",
    ]


def test_cli_args_build_company_interventions():
    args = run_day_module._parse_args(
        [
            "--send-settlers",
            "25",
            "--send-food",
            "300",
            "--send-supplies",
            "50",
            "2",
        ]
    )

    assert run_day_module._company_interventions_from_args(args) == [
        {"type": "send_settlers", "count": 25},
        {"type": "send_food", "amount": 300},
        {"type": "send_supplies", "wood": 50, "security": 2},
    ]


def test_cli_args_default_settlers_and_supplies():
    args = run_day_module._parse_args(["--send-settlers", "--send-supplies"])

    assert run_day_module._company_interventions_from_args(args) == [
        {"type": "send_settlers", "count": 100},
        {"type": "send_supplies"},
    ]

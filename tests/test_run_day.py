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

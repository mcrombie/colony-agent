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


def test_main_prints_history_entry(monkeypatch, capsys):
    history_entry = (
        "Day 1 (Year 1, January 1) - Blergen:\n"
        "President Ada Aster told the colonists to preserve resources.\n"
    )
    monkeypatch.setattr(
        run_day_module,
        "run_day",
        lambda interventions, **kwargs: {"history_entry": history_entry},
    )

    run_day_module.main([])

    assert capsys.readouterr().out == history_entry

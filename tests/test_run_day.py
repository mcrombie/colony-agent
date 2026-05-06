from pathlib import Path

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

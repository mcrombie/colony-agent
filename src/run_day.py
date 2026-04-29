"""Run one day of the colony simulation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.event_selector import choose_event
from src.mechanics import apply_event
from src.narrative import write_daily_entry

PROJECT_DIR = Path(__file__).resolve().parent
STATE_PATH = PROJECT_DIR / "state.json"
HISTORY_PATH = PROJECT_DIR / "history.md"


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as state_file:
        return json.load(state_file)


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    with path.open("w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2)
        state_file.write("\n")


def append_history(entry: str, path: Path = HISTORY_PATH) -> None:
    with path.open("a", encoding="utf-8") as history_file:
        history_file.write("\n" + entry)


def run_day() -> dict[str, Any]:
    """Advance the colony by one day and persist the result."""
    state_before = load_state()
    event_type = choose_event(state_before)
    state_after, event_record = apply_event(deepcopy(state_before), event_type)
    entry = write_daily_entry(state_before, event_record, state_after)

    append_history(entry)
    save_state(state_after)
    return event_record


def main() -> None:
    event_record = run_day()
    print(
        f"Day {event_record['day']}: "
        f"{event_record['event_type']} - {event_record['summary']}"
    )


if __name__ == "__main__":
    main()

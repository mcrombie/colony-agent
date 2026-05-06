"""Run one day of the colony simulation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.environment import environment_for_day
from src.event_selector import choose_leadership_action, choose_world_event
from src.mechanics import apply_day
from src.narrative import write_daily_entry, write_personal_history_entry
from src.people import ensure_people_exist

PROJECT_DIR = Path(__file__).resolve().parent
STATE_PATH = PROJECT_DIR / "state.json"
HISTORY_PATH = PROJECT_DIR / "history.md"
PEOPLE_HISTORY_PATH = PROJECT_DIR / "people_history.md"


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


def append_personal_history(entry: str, path: Path = PEOPLE_HISTORY_PATH) -> None:
    if not entry:
        return

    with path.open("a", encoding="utf-8") as history_file:
        history_file.write("\n" + entry)


def run_day() -> dict[str, Any]:
    """Advance the colony by one day and persist the result."""
    state_before = ensure_people_exist(load_state())
    environment = environment_for_day(state_before["day"])
    world_event = choose_world_event(state_before, environment=environment)
    leadership_action = choose_leadership_action(state_before, world_event)
    state_after, event_record = apply_day(
        deepcopy(state_before),
        world_event,
        leadership_action,
        environment=environment,
    )
    entry = write_daily_entry(state_before, event_record, state_after)
    personal_entry = write_personal_history_entry(
        state_before,
        event_record,
        state_after,
    )

    append_history(entry)
    append_personal_history(personal_entry)
    save_state(state_after)
    return event_record


def main() -> None:
    event_record = run_day()
    print(
        f"Day {event_record['day']}: "
        f"{event_record['world_event']} / "
        f"{event_record['leadership_action']} - "
        f"{event_record['summary']}"
    )


if __name__ == "__main__":
    main()

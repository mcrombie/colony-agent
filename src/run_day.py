"""Run one day of the colony simulation."""

from __future__ import annotations

import json
import argparse
from datetime import date, datetime, timezone
from copy import deepcopy
from pathlib import Path
from collections.abc import Sequence
from typing import Any

from src.constants import EMPTY_COLONY_EVENT_TYPE, NO_ACTION_ACTION_TYPE
from src.environment import environment_for_day, sync_calendar_state
from src.event_selector import choose_leadership_action, choose_world_event
from src.interventions import (
    DEFAULT_SETTLER_COUNT,
    DEFAULT_SUPPLY_SECURITY,
    DEFAULT_SUPPLY_WOOD,
    apply_company_interventions,
)
from src.mechanics import apply_day, clamp_state
from src.narrative import write_daily_entry, write_personal_history_entry
from src.people import ensure_people_exist, ensure_president
from src.frontier import prepare_frontier
from src.dashboard import render_dashboard, render_colony_svg
from src.storage import atomic_write, colony_lock, commit_day, recover_day

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


def run_day(
    company_intervention_requests: list[dict[str, Any]] | None = None,
    *,
    run_date: date | None = None,
    data_dir: Path = PROJECT_DIR,
    output_dir: Path = PROJECT_DIR.parent / "docs",
) -> dict[str, Any]:
    """Advance once per UTC date and recover interrupted writes before deciding."""
    today = run_date or datetime.now(timezone.utc).date()
    with colony_lock(data_dir):
        recover_day(data_dir, output_dir)
        state = load_state(data_dir / "state.json")
        previous = state.get("last_run_date")
        if previous and date.fromisoformat(previous) >= today:
            if date.fromisoformat(previous) > today:
                raise ValueError("Cannot advance before the last recorded UTC date")
            return {"skipped": True, "history_entry": "Already advanced for this UTC date; no API calls or new events.\n"}
        state_after, event_record = advance_state(state, company_intervention_requests)
        event_record["run_date"] = today.isoformat()
        state_after["event_log"][-1]["run_date"] = today.isoformat()
        state_after["last_run_date"] = today.isoformat()
        entry = event_record.pop("history_entry")
        personal_entry = event_record.pop("personal_history_entry")
        history_path = data_dir / "history.md"
        people_path = data_dir / "people_history.md"
        history = (history_path.read_text(encoding="utf-8") if history_path.exists() else "# Colony history\n") + "\n" + entry
        personal = (people_path.read_text(encoding="utf-8") if people_path.exists() else "# Personal history\n") + ("\n" + personal_entry if personal_entry else "")
        payload = {
            "history": history, "people": personal,
            "html": render_dashboard(state_after), "map": render_colony_svg(state_after),
            "state": json.dumps(state_after, indent=2) + "\n",
        }
        commit_day(payload, data_dir, output_dir)
        return {**event_record, "history_entry": entry}


def advance_state(state: dict[str, Any], company_intervention_requests=None):
    """Build the next state without writing files; selectors may use optional AI."""
    state_before = sync_calendar_state(ensure_people_exist(deepcopy(state)))
    state_before, company_interventions = apply_company_interventions(
        state_before,
        additional_interventions=company_intervention_requests,
    )
    state_before, relief = prepare_frontier(state_before)
    company_interventions.extend(relief)
    ensure_president(state_before)
    state_before = clamp_state(state_before)
    environment = environment_for_day(state_before["day"])
    if state_before["population"] <= 0:
        world_event = {
            "world_event": EMPTY_COLONY_EVENT_TYPE,
            "reasoning": "No colonists remain to experience events as a colony.",
        }
        leadership_action = NO_ACTION_ACTION_TYPE
    else:
        world_event = choose_world_event(state_before, environment=environment)
        leadership_action = choose_leadership_action(state_before, world_event)
    state_after, event_record = apply_day(
        deepcopy(state_before),
        world_event,
        leadership_action,
        environment=environment,
    )
    if company_interventions:
        event_record["company_interventions"] = company_interventions
    entry = write_daily_entry(state_before, event_record, state_after)
    personal_entry = write_personal_history_entry(
        state_before,
        event_record,
        state_after,
    )

    return state_after, {**event_record, "history_entry": entry, "personal_history_entry": personal_entry}


def render_only(data_dir: Path = PROJECT_DIR, output_dir: Path = PROJECT_DIR.parent / "docs") -> None:
    with colony_lock(data_dir):
        recover_day(data_dir, output_dir)
        state = load_state(data_dir / "state.json")
        atomic_write(output_dir / "index.html", render_dashboard(state))
        atomic_write(output_dir / "colony.svg", render_colony_svg(state))


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.render_only:
        render_only(args.data_dir, args.output_dir)
        print(f"Atlas refreshed: {args.output_dir / 'index.html'}")
        return
    event_record = run_day(_company_interventions_from_args(args), run_date=args.date,
                           data_dir=args.data_dir, output_dir=args.output_dir)
    print(event_record["history_entry"], end="")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Advance Blergen by one day.")
    parser.add_argument("--render-only", action="store_true", help="Refresh graphics without advancing time")
    parser.add_argument("--date", type=date.fromisoformat, help="UTC date; defaults to today")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR.parent / "docs")
    parser.add_argument(
        "--send-settlers",
        nargs="?",
        const=DEFAULT_SETTLER_COUNT,
        type=_non_negative_cli_int,
        metavar="COUNT",
        help=(
            "Have Blergen Company send new settlers before the day runs. "
            f"Defaults to {DEFAULT_SETTLER_COUNT}."
        ),
    )
    parser.add_argument(
        "--send-food",
        type=_non_negative_cli_int,
        metavar="AMOUNT",
        help="Have Blergen Company send food before the day runs.",
    )
    parser.add_argument(
        "--send-supplies",
        nargs="*",
        type=_non_negative_cli_int,
        metavar=("WOOD", "SECURITY"),
        help=(
            "Have Blergen Company send supplies before the day runs. "
            f"Defaults to {DEFAULT_SUPPLY_WOOD} wood and {DEFAULT_SUPPLY_SECURITY} security."
        ),
    )
    args = parser.parse_args(argv)
    if args.send_supplies is not None and len(args.send_supplies) > 2:
        parser.error("--send-supplies accepts at most WOOD and SECURITY")

    return args


def _company_interventions_from_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    interventions = []
    if args.send_settlers is not None:
        interventions.append({"type": "send_settlers", "count": args.send_settlers})

    if args.send_food is not None:
        interventions.append({"type": "send_food", "amount": args.send_food})

    if args.send_supplies is not None:
        supplies = args.send_supplies
        intervention = {"type": "send_supplies"}
        if len(supplies) >= 1:
            intervention["wood"] = supplies[0]
        if len(supplies) == 2:
            intervention["security"] = supplies[1]
        interventions.append(intervention)

    return interventions


def _non_negative_cli_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")

    return parsed


if __name__ == "__main__":
    main()

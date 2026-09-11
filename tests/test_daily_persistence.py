from datetime import date, timedelta
import json

import pytest

from src import run_day, storage
from src.frontier import ensure_frontier


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("COLONY_AI_MODE", "off")
    data, output = tmp_path / "src", tmp_path / "docs"
    data.mkdir()
    state = {"day": 1, "colony_name": "Blergen", "population": 12,
             "food": 100, "wood": 30, "health": 6, "morale": 6,
             "security": 4, "known_threats": [], "event_log": []}
    (data / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (data / "history.md").write_text("# Old history\n", encoding="utf-8")
    return data, output


def test_daily_run_is_idempotent_and_advances_on_next_date(world, monkeypatch):
    data, output = world
    today = date(2026, 9, 11)
    record = run_day.run_day(run_date=today, data_dir=data, output_dir=output)
    state = json.loads((data / "state.json").read_text())
    assert state["day"] == 2 and state["last_run_date"] == today.isoformat()
    assert state["event_log"][-1]["run_date"] == today.isoformat()
    assert (data / "history.md").read_text().startswith("# Old history\n")
    assert "Day 1" in record["history_entry"]
    before = {p: p.read_bytes() for p in [data / "state.json", data / "history.md", data / "people_history.md", output / "index.html", output / "colony.svg"]}
    with monkeypatch.context() as guard:
        guard.setattr(run_day, "advance_state", lambda *a: pytest.fail("Duplicate run selected events"))
        assert run_day.run_day(run_date=today, data_dir=data, output_dir=output)["skipped"]
    assert all(p.read_bytes() == raw for p, raw in before.items())
    run_day.run_day(run_date=today + timedelta(days=1), data_dir=data, output_dir=output)
    assert json.loads((data / "state.json").read_text())["day"] == 3


def test_partial_write_recovers_without_duplicate_history_or_selection(world, monkeypatch):
    data, output = world
    today = date(2026, 9, 11)
    original_write = storage.atomic_write
    def interrupted(path, content):
        if path.name == "state.json":
            raise OSError("simulated interrupted save")
        original_write(path, content)
    with monkeypatch.context() as failure:
        failure.setattr(storage, "atomic_write", interrupted)
        with pytest.raises(OSError, match="interrupted"):
            run_day.run_day(run_date=today, data_dir=data, output_dir=output)
    assert (data / ".pending-day.json").exists()
    monkeypatch.setattr(run_day, "advance_state", lambda *a: pytest.fail("Recovery selected another day"))
    assert run_day.run_day(run_date=today, data_dir=data, output_dir=output)["skipped"]
    assert not (data / ".pending-day.json").exists()
    assert (data / "history.md").read_text().count("Day 1 (") == 1
    assert json.loads((data / "state.json").read_text())["day"] == 2


def test_backdated_run_rejected_and_render_does_not_advance(world):
    data, output = world
    run_day.run_day(run_date=date(2026, 9, 11), data_dir=data, output_dir=output)
    before = (data / "state.json").read_bytes()
    with pytest.raises(ValueError, match="before"):
        run_day.run_day(run_date=date(2026, 9, 10), data_dir=data, output_dir=output)
    run_day.render_only(data, output)
    assert (data / "state.json").read_bytes() == before


def test_company_interventions_precede_selection(world, monkeypatch):
    data, output = world
    state = json.loads((data / "state.json").read_text())
    state.update(population=0, people=[])
    (data / "state.json").write_text(json.dumps(state))
    def select(current, environment=None):
        assert current["population"] == 3
        assert current["food"] == 120
        return {"world_event": "quiet_day"}
    monkeypatch.setattr(run_day, "choose_world_event", select)
    record = run_day.run_day([{"type": "send_settlers", "count": 3}, {"type": "send_food", "amount": 20}],
                            run_date=date(2026, 9, 11), data_dir=data, output_dir=output)
    assert [i["type"] for i in record["company_interventions"]] == ["send_settlers", "send_food"]


def test_recently_abandoned_frontier_waits_without_selectors(monkeypatch):
    state = ensure_frontier({"day": 10, "colony_name": "Blergen", "population": 0,
                            "people": [], "food": 0, "wood": 0, "health": 0,
                            "morale": 0, "security": 0, "known_threats": [], "event_log": []})
    monkeypatch.setattr(run_day, "choose_world_event", lambda *a, **kw: pytest.fail("Empty colony called selector"))
    after, record = run_day.advance_state(state)
    assert after["population"] == 0 and after["day"] == 11
    assert record["world_event"] == "empty_colony"


def test_concurrent_run_lock_releases(world):
    data, _ = world
    with storage.colony_lock(data):
        with pytest.raises(RuntimeError, match="active"):
            with storage.colony_lock(data):
                pytest.fail("Acquired second lock")
    with storage.colony_lock(data):
        pass

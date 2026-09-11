from copy import deepcopy
from xml.etree import ElementTree

from src.dashboard import _timeline, render_colony_svg, render_dashboard, write_dashboard


def colony():
    return {
        "colony_name": "Blergen",
        "day": 4,
        "population": 6,
        "food": 36,
        "wood": 18,
        "health": 7,
        "morale": 5,
        "security": 4,
        "event_log": [{"day": 3, "event_type": "discovery", "summary": "A river was found."}],
        "people": [],
    }


def test_dashboard_writes_offline_artifacts_without_changing_legacy_save(tmp_path):
    state = colony()
    before = deepcopy(state)

    html_path, svg_path = write_dashboard(state, tmp_path)

    assert state == before
    html = html_path.read_text(encoding="utf-8")
    assert "Kitchen gardens" in html
    assert "Last completed" in html and "Day 3" in html
    assert "next day 4" in html
    assert "A river was found." in html
    assert "<script" not in html and "https://" not in html
    assert 'src="http' not in html and "@import" not in html
    assert svg_path.name == "colony.svg"
    root = ElementTree.fromstring(svg_path.read_text(encoding="utf-8"))
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.find("{http://www.w3.org/2000/svg}desc") is not None


def test_renderer_escapes_narrative_and_svg_text():
    state = colony()
    hostile = '<script>alert("colony")</script>&'
    state["colony_name"] = hostile
    state["event_log"][0]["summary"] = hostile
    state["people"] = [{"name": hostile, "role": hostile, "age": 32,
                        "status": {"alive": True},
                        "personality": {"desire": hostile},
                        "story": {"notable_events": [hostile]}}]
    state["frontier"] = {"sites": [{"id": "hostile", "name": hostile,
                                    "biome": hostile, "x": float("inf"),
                                    "y": -200, "discovered": True}]}

    html = render_dashboard(state)
    svg = render_colony_svg(state)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in svg
    assert "nan" not in svg and "inf" not in svg
    ElementTree.fromstring(svg)


def test_atlas_uses_active_expedition_work_and_completed_visits_separately():
    state = colony()
    state["frontier"] = {
        "sites": [{"id": "river", "name": "River", "discovered": True, "survey": 1, "required": 6}],
        "expedition": {"site_id": "river", "progress": 3, "required": 12},
    }
    assert "1 completed visits; current expedition 25%" in render_colony_svg(state)
    state["frontier"]["expedition"] = None
    assert "1 completed visits; discovery 100%" in render_colony_svg(state)


def test_trends_use_exact_snapshots_not_inferred_effects():
    state = colony()
    state["event_log"] = [{"day": 1, "effects": {"food": -1000}},
                          {"day": 2, "effects": {"food": 30}}]
    assert _timeline(state) == [{"day": 3, **{k: state[k] for k in
        ("population", "food", "wood", "health", "morale", "security")}}]
    html = render_dashboard(state)
    assert "Trend begins with the next daily observation." in html

    state["frontier"] = {"timeline": [
        {"day": 1, "food": 10, "population": 8},
        {"day": 2, "food": 40, "population": 7},
        {"day": 3, "food": 99, "population": 99},
    ]}
    before = deepcopy(state)
    html = render_dashboard(state)
    assert state == before
    assert 'Food, day 1 to 3: 10 to 36.' in html
    assert "-4 since last observation" in html
    assert _timeline(state)[-1]["food"] == 36
    assert "<td>1</td><td>8</td><td>10</td>" in html


def test_renderer_handles_abandoned_colony_and_single_day():
    state = colony()
    state.update(day=1, population=0, event_log=[])
    html = render_dashboard(state)
    assert "No living settlers are recorded" in html
    assert "Day 0" in html
    assert "0.0</strong><span>days of food" in html
    assert "first daily entry has yet to be written" in html


def test_chart_history_is_bounded_and_sorted():
    state = colony()
    state["day"] = 202
    state["frontier"] = {"timeline": [{"day": day, "food": day} for day in range(200, 0, -1)]}
    points = _timeline(state)
    assert len(points) == 120
    assert points[0]["day"] == 82
    assert points[-1]["day"] == 201

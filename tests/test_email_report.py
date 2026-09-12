from copy import deepcopy
from html.parser import HTMLParser

import pytest

from src.email_report import build_report


def colony():
    return {
        "colony_name": "Blergen", "day": 366, "population": 12, "food": 144,
        "wood": 51, "health": 7, "morale": 6, "security": 3,
        "event_log": [{
            "day": 365, "run_date": "2026-09-11", "world_event": "discovery",
            "summary": "The scouting party found a sheltered river crossing.",
            "leadership_action": "send_scouts", "president": {"name": "Ada Aster"},
            "effects": {"food": 9999},
            "frontier": {"production": {"food": 13, "wood": 2},
                "discoveries": [{"name": "Silver river", "first_visit": True, "summary": "Fish shelter in a quiet bend."}],
                "completed": [{"name": "Kitchen gardens"}],
                "milestones": [{"name": "First roots", "day": 365}]},
            "people_events": {"actions": [{"summary": "Orin Nell and Una Nell marked a safe path home."}],
                "deaths": [{"name": "Bram Aster", "cause": "illness"}]},
        }],
        "frontier": {
            "timeline": [{"day": 364, "population": 13, "food": 132, "wood": 53,
                          "health": 6, "morale": 6, "security": 4},
                         {"day": 365, "population": 12, "food": 144, "wood": 51,
                          "health": 7, "morale": 6, "security": 3}],
            "projects": [{"id": "gardens", "name": "Kitchen gardens", "completed_day": 365,
                          "progress": 10, "required": 10},
                         {"id": "cistern", "name": "Rain cistern", "completed_day": None,
                          "progress": 2, "required": 14, "description": "A clean supply of water."}],
            "sites": [{"id": "river", "name": "Silver river", "discovered": True, "survey": 1}],
            "expedition": {"site_id": "river", "progress": 2, "required": 12,
                           "crew": [{"name": "Orin Nell"}, {"name": "Una Nell"}]},
            "knowledge": 3, "milestones": [{"name": "First roots", "day": 365}],
        },
    }


def test_report_uses_completed_event_date_and_measured_changes_without_mutation():
    state = colony()
    before = deepcopy(state)
    report = build_report(state)
    assert state == before
    assert set(report) == {"subject", "text", "html"}
    assert "Day 365" in report["subject"] and "Day 366" not in report["subject"]
    assert "December 31, Year 1" in report["text"]
    assert "2026-09-11 (UTC)" in report["text"]
    assert "Food: 144 units (+12 versus day 364)" in report["text"]
    assert "Population: 12 settlers (-1 versus day 364)" in report["text"]
    assert "9999" not in report["text"]
    assert "Food reserve: 12.0 days" in report["text"]
    assert "Watch list: security 3/10" in report["text"]


def test_report_includes_frontier_work_expedition_and_people_in_both_formats():
    report = build_report(colony())
    for format_ in ("text", "html"):
        body = report[format_]
        for phrase in ("Rain cistern", "2 / 14 work units", "Kitchen gardens",
                       "Silver river", "2 / 12 survey work", "Crew: Orin Nell, Una Nell",
                       "Fish shelter in a quiet bend", "First roots",
                       "Orin Nell and Una Nell marked a safe path home", "Bram Aster (illness)",
                       "index.html", "colony.svg", "Both work offline"):
            assert phrase in body
    assert report["text"].count("Milestones reached today: First roots") == 1


def test_missing_snapshot_never_fabricates_deltas_from_event_effects():
    state = colony()
    state["frontier"].pop("timeline")
    state["health"] = float("nan")
    report = build_report(state)
    assert "Food: 144 units (change not recorded)" in report["text"]
    assert "Health: Not recorded (change not recorded)" in report["text"]
    assert "No earlier measured snapshot is available" in report["text"]
    assert "9999" not in report["text"]
    assert "nan" not in report["html"]


def test_nonconsecutive_snapshot_comparison_states_the_gap():
    state = colony()
    state["frontier"]["timeline"][0]["day"] = 360
    report = build_report(state)
    assert "the gap is 5 days" in report["text"]
    assert "+12 versus day 360" in report["text"]


def test_old_or_empty_state_does_not_claim_a_day_was_completed():
    report = build_report({"day": 12, "population": 0, "event_log": [], "frontier": None})
    assert "No completed day recorded" in report["subject"]
    assert "Day 11" not in report["text"]
    assert "No completed daily event" in report["text"]
    assert "No living settlers" in report["text"]
    assert "Food: Not recorded" in report["text"]
    assert "No earlier measured snapshot" in report["text"]
    assert build_report({})["html"]


def test_explicit_event_selection_uses_saved_historical_snapshot():
    state = colony()
    state["event_log"].insert(0, {"day": 364, "summary": "An earlier quiet day."})
    report = build_report(state, [{"day": 364, "summary": "An earlier quiet day."},
                                  {"day": 363, "summary": "Older still."}])
    assert "Day 364" in report["subject"]
    assert "Food: 132 units" in report["text"]
    assert "Food: 144 units" not in report["text"]
    assert "An earlier quiet day" in report["html"]
    assert "Day 365" in build_report(state, {"skipped": True})["subject"]


class EmailParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.links = []
        self.event_attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.links.extend(value for key, value in attrs if key == "href")
        self.event_attributes.extend(key for key, _ in attrs if key.startswith("on"))


def test_hostile_text_is_escaped_subject_is_single_line_and_email_has_no_active_content():
    state = colony()
    hostile = '<img src=x onerror="alert(1)"><script>bad()</script>&'
    state["colony_name"] = "Blergen\r\nBcc: victim@example.com"
    state["event_log"][-1]["summary"] = hostile
    state["event_log"][-1]["people_events"]["actions"][0]["summary"] = hostile
    state["frontier"]["projects"][1]["name"] = hostile
    report = build_report(state, dashboard_url='https://example.com/atlas?a=1&b="quoted"',
                          run_url="https://github.com/owner/repo/actions/runs/123")
    assert "\r" not in report["subject"] and "\n" not in report["subject"]
    assert "&lt;script&gt;" in report["html"]
    parser = EmailParser()
    parser.feed(report["html"])
    assert not ({"script", "svg", "img", "iframe", "link"} & set(parser.tags))
    assert not parser.event_attributes
    assert len(parser.links) == 2
    assert "&amp;b=&quot;quoted&quot;" in report["html"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://example.com", "file:///tmp/a",
                                "//example.com", "https://user:password@example.com/",
                                "https://example.com\n/", "https://example.com:bad/",
                                "https://example.com\\@evil.invalid/", "https:///missing"])
def test_unverified_or_unsafe_link_syntax_is_omitted(url):
    report = build_report(colony(), dashboard_url=url, run_url=url)
    parser = EmailParser()
    parser.feed(report["html"])
    assert parser.links == []
    assert "Open the full dashboard:" not in report["text"]

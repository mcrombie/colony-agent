"""Build a daily frontier email without sending mail or changing the colony.

The transport supplies recipients and attachments. This renderer uses inline
table layouts, no remote assets, and no JavaScript or inline SVG. Optional links
must be verified by the caller; only safe HTTPS URL syntax is accepted here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from html import escape
from typing import Any
from urllib.parse import urlsplit

from src.environment import date_for_day

METRICS = (
    ("population", "Population", "settlers"),
    ("food", "Food", "units"),
    ("wood", "Wood", "units"),
    ("health", "Health", "/ 10"),
    ("morale", "Morale", "/ 10"),
    ("security", "Security", "/ 10"),
)
ATTACHMENT_NOTE = (
    "The full visual dashboard and atlas are attached as index.html and colony.svg. "
    "Save index.html and open it in a browser to explore the charts, project ledger, "
    "and personal stories; open colony.svg to view the atlas. Both work offline."
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _items(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _line(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _esc(value: Any) -> str:
    return escape(_line(value), quote=True)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _day(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number >= 1 and number.is_integer() else None


def _fmt(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "Not recorded"
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.1f}"


def _title(value: Any) -> str:
    return _line(value).replace("_", " ").capitalize()


def _https_url(value: Any) -> str:
    """Accept explicit HTTPS links only; do not perform network requests."""
    if not isinstance(value, str) or any(char.isspace() or ord(char) < 32 for char in value):
        return ""
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port  # Validate malformed/non-numeric ports as well.
    except ValueError:
        return ""
    if (parsed.scheme.lower() != "https" or not host or parsed.username is not None
            or parsed.password is not None or "\\" in value
            or any(char in host for char in '<>"\'') or port == 0):
        return ""
    return value


def _latest_record(state: Mapping[str, Any], records: Any) -> Mapping[str, Any]:
    candidates = [item for item in _items(records) if _day(item.get("day")) and not item.get("skipped")]
    if not candidates:
        candidates = [item for item in _items(state.get("event_log")) if _day(item.get("day")) and not item.get("skipped")]
    return max(candidates, key=lambda item: _day(item["day"])) if candidates else {}


def _snapshots(state: Mapping[str, Any], frontier: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    snapshots = {}
    for point in _items(frontier.get("timeline")):
        day = _day(point.get("day"))
        if day is not None:
            snapshots[day] = point
    for event in _items(state.get("event_log")):
        day = _day(event.get("day"))
        if day is not None and isinstance(event.get("snapshot"), Mapping):
            snapshots.setdefault(day, event["snapshot"])
    return snapshots


def _bar(value: float, maximum: float, *, color: str = "#54765a") -> str:
    if maximum <= 0:
        return ""
    percent = max(0, min(100, round(value / maximum * 100)))
    filled = f'<td width="{percent}%" bgcolor="{color}" style="height:5px;font-size:0;line-height:0;">&nbsp;</td>' if percent else ""
    empty = f'<td width="{100-percent}%" bgcolor="#e1e8d8" style="height:5px;font-size:0;line-height:0;">&nbsp;</td>' if percent < 100 else ""
    return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:8px;"><tr>{filled}{empty}</tr></table>'


def _section(title: str, lines: list[str], extra_html: str = "") -> str:
    paragraphs = "".join(f'<p style="margin:0 0 12px;font-size:14px;line-height:1.65;color:#365342;">{_esc(line)}</p>' for line in lines)
    return f'<tr><td style="padding:24px 28px;border-bottom:1px solid #dce3d3;"><h2 style="font-family:Georgia,serif;font-weight:normal;font-size:23px;line-height:1.3;margin:0 0 15px;color:#173f32;">{_esc(title)}</h2>{paragraphs}{extra_html}</td></tr>'


def _unique(lines: list[str]) -> list[str]:
    return list(dict.fromkeys(line for line in lines if line))


def build_report(
    state: Mapping[str, Any], records: Any = None, *, dashboard_url: str = "", run_url: str = "",
) -> dict[str, str]:
    """Return ``subject``, ``text``, and ``html`` for the latest recorded day.

    ``records`` may be a returned event or a sequence of events for this run.
    Empty/skipped records fall back to the saved log. Prior measurements are
    required for deltas; event effects are never treated as a previous balance.
    No I/O, state migration, simulation, API calls, or mail delivery occurs.
    """
    state = _mapping(state)
    latest = _latest_record(state, records)
    day = _day(latest.get("day"))
    name = _line(state.get("colony_name")) or "Blergen"
    frontier = _mapping(state.get("frontier"))
    daily_frontier = _mapping(latest.get("frontier"))
    day_label = f"Day {day:,}" if day is not None else "No completed day recorded"
    simulation_date = ""
    if day is not None:
        calendar = date_for_day(day)
        simulation_date = f"{calendar['month']} {calendar['day_of_month']}, Year {calendar['year']} · {_title(calendar['season'])}"
    run_date = ""
    try:
        if latest.get("run_date"):
            run_date = date.fromisoformat(str(latest["run_date"])).isoformat()
    except (ValueError, TypeError):
        pass
    subject = f"{name} · {day_label} · Frontier field report"
    title_note = simulation_date or "Saved colony status"
    if run_date:
        title_note += f" | Daily run: {run_date} (UTC)"

    happenings = []
    if latest:
        happenings.append(_line(latest.get("summary")) or f"Recorded event: {_title(latest.get('world_event', latest.get('event_type', 'daily event')))}.")
        president = _mapping(latest.get("president"))
        if latest.get("leadership_action"):
            leader = f"President {_line(president['name'])}" if president.get("name") else "Leadership"
            happenings.append(f"{leader}: {_title(latest['leadership_action'])}.")
        weather = _mapping(latest.get("weather"))
        if weather.get("summary") and _line(weather["summary"]) not in happenings[0]:
            happenings.append(_line(weather["summary"]))
        happenings.extend(_line(intervention.get("summary")) for intervention in _items(latest.get("company_interventions")))
    else:
        happenings.append("No completed daily event is present in this save. The measurements below describe the saved colony; no new activity is inferred.")
    happenings = _unique(happenings)

    snapshots = _snapshots(state, frontier)
    previous_days = [point_day for point_day in snapshots if day is not None and point_day < day]
    previous_day = max(previous_days) if previous_days else None
    previous = snapshots.get(previous_day, {})
    current = dict(state)
    # A caller can explicitly report an earlier run: use its exact saved point.
    latest_saved_day = _day(_latest_record(state, None).get("day"))
    if day is not None and latest_saved_day is not None and day < latest_saved_day:
        current = dict(snapshots.get(day, _mapping(latest.get("snapshot"))))
    values_text, rows = [], []
    if previous_day is not None:
        comparison_note = (f"Changes compare with day {previous_day:,}." if day == previous_day + 1
                           else f"Changes compare with the last recorded observation, day {previous_day:,}; the gap is {day-previous_day} days.")
    else:
        comparison_note = "No earlier measured snapshot is available; changes are not estimated from event effects."
    for key, label, units in METRICS:
        value = _number(current.get(key))
        before = _number(previous.get(key))
        display = f"{_fmt(value)} {units}" if value is not None else "Not recorded"
        delta = f"{value-before:+g}" if value is not None and before is not None else "—"
        values_text.append(f"{label}: {display}" + (f" ({delta} versus day {previous_day:,})" if delta != "—" else " (change not recorded)"))
        bar = _bar(value, 10) if value is not None and units == "/ 10" else ""
        rows.append(f'<tr><th scope="row" align="left" style="padding:12px 0;border-bottom:1px solid #e6ebdf;font-size:13px;font-weight:normal;color:#526853;">{label}</th><td align="right" style="padding:12px 12px;border-bottom:1px solid #e6ebdf;font-size:14px;color:#173f32;">{_esc(display)}{bar}</td><td align="right" style="padding:12px 0;border-bottom:1px solid #e6ebdf;font-size:13px;color:#526853;">{delta}</td></tr>')
    resource_notes = []
    population, food = _number(current.get("population")), _number(current.get("food"))
    if population is not None and population > 0 and food is not None:
        resource_notes.append(f"Food reserve: {food/population:.1f} days at one unit per settler per day, before new production.")
    elif population == 0:
        resource_notes.append("No living settlers are recorded in the current population.")
    production = _mapping(daily_frontier.get("production"))
    produced = [f"{_fmt(production[key])} {key}" for key in ("food", "wood") if _number(production.get(key)) is not None]
    if produced:
        resource_notes.append("Routine production today: " + ", ".join(produced) + ".")
    watch = [f"{label.lower()} {_fmt(current[key])}/10" for key, label, _ in METRICS if key in ("health", "morale", "security") and _number(current.get(key)) is not None and _number(current[key]) <= 3]
    if watch:
        resource_notes.append("Watch list: " + ", ".join(watch) + ".")

    project_lines, project_bars = [], []
    projects = _items(frontier.get("projects"))
    completed_today = [_line(project.get("name")) for project in projects if day is not None and _day(project.get("completed_day")) == day]
    completed_today += [_line(project.get("name")) for project in _items(daily_frontier.get("completed"))]
    if completed_today:
        project_lines.append("Completed today: " + ", ".join(_unique(completed_today)) + ".")
    if projects:
        done = sum(_day(project.get("completed_day")) is not None for project in projects)
        project_lines.append(f"Civic projects complete: {done} of {len(projects)}.")
        active = next((project for project in projects if project.get("completed_day") is None), None)
        if active:
            progress, required = _number(active.get("progress")), _number(active.get("required"))
            label = _line(active.get("name")) or "Current project"
            project_lines.append(f"Under construction: {label} — {_fmt(progress)} / {_fmt(required)} work units. " + _line(active.get("description")))
            if progress is not None and required is not None and required > 0:
                project_bars.append(f'<p style="font-size:12px;margin:12px 0 0;color:#526853;">{_esc(label)} · {max(0,min(100,progress/required*100)):.0f}% complete</p>{_bar(progress,required)}')
    else:
        project_lines.append("No civic project progress is recorded yet.")
    if daily_frontier.get("summary") and _line(daily_frontier["summary"]) not in " ".join(happenings + project_lines):
        project_lines.append(_line(daily_frontier["summary"]))

    exploration = []
    sites = _items(frontier.get("sites"))
    if sites:
        exploration.append(f"Atlas: {sum(bool(site.get('discovered')) for site in sites)} of {len(sites)} sites discovered.")
    expedition = _mapping(frontier.get("expedition"))
    if expedition:
        site = next((site for site in sites if site.get("id") == expedition.get("site_id")), {})
        crew = ", ".join(_line(person.get("name")) for person in _items(expedition.get("crew")) if person.get("name"))
        exploration.append(f"Current expedition: {_line(site.get('name')) or 'Destination not recorded'} — {_fmt(expedition.get('progress'))} / {_fmt(expedition.get('required'))} survey work." + (f" Crew: {crew}." if crew else ""))
    elif frontier:
        exploration.append("No expedition is currently in the field.")
    for discovery in _items(daily_frontier.get("discoveries")):
        prefix = "First discovery" if discovery.get("first_visit") else "Return expedition"
        exploration.append(f"{prefix}: {_line(discovery.get('name')) or 'Frontier site'}. {_line(discovery.get('summary'))}")
    if daily_frontier.get("expedition_status"):
        exploration.append(_line(daily_frontier["expedition_status"]))
    if _number(frontier.get("knowledge")) is not None:
        exploration.append(f"Knowledge in the survey archive: {_fmt(frontier['knowledge'])}.")
    milestones = [_line(milestone.get("name")) for milestone in _items(frontier.get("milestones")) if day is not None and _day(milestone.get("day")) == day]
    milestones += [_line(milestone.get("name")) for milestone in _items(daily_frontier.get("milestones"))]
    if milestones:
        exploration.append("Milestones reached today: " + ", ".join(_unique(milestones)) + ".")
    if not exploration:
        exploration.append("No frontier survey or milestone has been recorded yet.")

    people_events = _mapping(latest.get("people_events"))
    personal = [_line(action.get("summary")) for action in _items(people_events.get("actions")) if action.get("summary")]
    deaths = []
    for person in _items(people_events.get("deaths")):
        deaths.append(f"{_line(person.get('name')) or 'An unnamed settler'}" + (f" ({_title(person['cause']).lower()})" if person.get("cause") else ""))
    if deaths:
        personal.insert(0, "Remembering those lost today: " + ", ".join(deaths) + ".")
    personal = _unique(personal)
    if len(personal) > 5:
        remaining = len(personal) - 5
        personal = personal[:5] + [f"{remaining} more personal records appear in the attached dashboard and colony history."]
    if not personal:
        personal = ["No individual stories were recorded for this day." if latest else "Individual stories will appear after a daily event is recorded."]

    links = [("Open the full dashboard", _https_url(dashboard_url)), ("View the daily run", _https_url(run_url))]
    links = [(label, url) for label, url in links if url]
    link_html = "".join(f'<p style="margin:14px 0 0;"><a href="{escape(url,quote=True)}" style="color:#23583f;font-size:14px;font-weight:bold;text-decoration:underline;">{label} &#8599;</a></p>' for label, url in links)
    sections = [
        ("What happened", happenings),
        ("The colony at a glance", values_text + [comparison_note] + resource_notes),
        ("Building a lasting settlement", project_lines),
        ("Beyond the palisade", exploration),
        ("Lives behind the numbers", personal),
        ("Your visual field kit", [ATTACHMENT_NOTE] + [f"{label}: {url}" for label, url in links]),
    ]
    text = f"{name.upper()} / FRONTIER FIELD REPORT\n{day_label}\n{title_note}\n\n" + "\n\n".join(title + "\n" + "\n".join("- " + line for line in lines) for title, lines in sections) + "\n"
    metrics_html = '<table width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><caption style="text-align:left;font-size:12px;color:#526853;padding-bottom:10px;">Saved measurements</caption><thead><tr><th scope="col" align="left" style="font-size:11px;color:#657763;">Measure</th><th scope="col" align="right" style="font-size:11px;color:#657763;padding-right:12px;">Current</th><th scope="col" align="right" style="font-size:11px;color:#657763;">Change</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table><p style="font-size:11px;line-height:1.6;color:#657763;margin:14px 0 0;">' + _esc(comparison_note) + '</p>'
    metrics_html += "".join(f'<p style="font-size:12px;line-height:1.6;color:#526853;margin:12px 0 0;">{_esc(note)}</p>' for note in resource_notes)
    body = (_section("What happened", happenings)
            + _section("The colony at a glance", [], metrics_html)
            + _section("Building a lasting settlement", project_lines, "".join(project_bars))
            + _section("Beyond the palisade", exploration)
            + _section("Lives behind the numbers", personal)
            + _section("Your visual field kit", [ATTACHMENT_NOTE], link_html))
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_esc(subject)}</title></head><body style="margin:0;padding:0;background-color:#f1f2e9;font-family:Arial,Helvetica,sans-serif;color:#173f32;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f1f2e9"><tr><td align="center" style="padding:22px 10px;">
      <table role="presentation" width="620" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:620px;border:1px solid #d6dfcc;background-color:#fcfcf7;">
      <tr><td bgcolor="#173f32" style="padding:30px 28px;color:#f4f4e7;"><p style="margin:0 0 13px;font-size:10px;font-weight:bold;letter-spacing:2px;color:#d0dcc6;">THE FRONTIER OBSERVATORY</p><h1 style="margin:0 0 13px;font-family:Georgia,serif;font-size:36px;line-height:1.15;font-weight:normal;color:#f4f4e7;">{_esc(name)}</h1><p style="margin:0 0 6px;font-size:17px;color:#e0c78c;">{day_label} / Field report</p><p style="margin:0;font-size:12px;line-height:1.6;color:#d0dcc6;">{_esc(title_note)}</p></td></tr>
      {body}<tr><td style="padding:20px 28px;font-size:11px;line-height:1.6;color:#657763;">Generated from the colony's recorded state and events. Dates above distinguish simulation time from the real daily run.</td></tr></table></td></tr></table></body></html>'''
    return {"subject": subject, "text": text, "html": html}

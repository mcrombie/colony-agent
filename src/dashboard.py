"""Render the frontier observatory using only Python's standard library.

The HTML works directly from disk, makes no network requests, and embeds its SVGs.
Only recorded snapshots are plotted; old effect logs cannot reconstruct clamped
resource levels. Rendering never advances or changes the supplied colony state.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from src.environment import date_for_day

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs"
METRICS = ("population", "food", "wood", "health", "morale", "security")


def _esc(value: Any) -> str:
    return escape(str(value), quote=True)


def _number(value: Any, default: float = 0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _fmt(value: Any) -> str:
    return f"{_number(value):,.0f}"


def _title(value: Any) -> str:
    return str(value).replace("_", " ").capitalize()


def _completed_day(state: dict[str, Any]) -> int:
    return max(0, int(_number(state.get("day", 1))) - 1)


def _timeline(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return exact recorded points plus the current save, ordered by day."""
    by_day = {}
    for point in state.get("frontier", {}).get("timeline", []):
        if isinstance(point, dict) and "day" in point:
            by_day[int(_number(point["day"]))] = dict(point)
    for event in state.get("event_log", []):
        if isinstance(event.get("snapshot"), dict):
            day = int(_number(event.get("day")))
            by_day.setdefault(day, {**event["snapshot"], "day": day})
    day = _completed_day(state)
    by_day[day] = {**by_day.get(day, {}), "day": day, **{
        key: state[key] for key in METRICS if key in state
    }}
    return [by_day[key] for key in sorted(by_day) if key <= day][-120:]


def _chart(points: list[dict[str, Any]], key: str, color: str) -> str:
    values = [(int(_number(p["day"])), _number(p[key])) for p in points if key in p]
    if len(values) < 2:
        return '<p class="chart-empty">Trend begins with the next daily observation.</p>'
    min_day, max_day = values[0][0], values[-1][0]
    low = min(0, min(v for _, v in values))
    high = max(1, max(v for _, v in values))
    def xy(day: int, value: float) -> tuple[float, float]:
        return 40 + 250 * (day - min_day) / max(1, max_day - min_day), 72 - 58 * (value - low) / (high - low)
    coords = [xy(day, value) for day, value in values]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = f"{coords[0][0]:.1f},72 {line} {coords[-1][0]:.1f},72"
    name = _title(key)
    summary = f"{name}, day {min_day} to {max_day}: {values[0][1]:g} to {values[-1][1]:g}. Vertical scale {low:g} to {high:g}."
    return f'''<svg class="spark" viewBox="0 0 308 102" role="img" aria-label="{_esc(summary)}">
      <path d="M40 14H290 M40 72H290" stroke="#d9ded4" stroke-dasharray="3 4" fill="none"/>
      <polygon points="{area}" fill="{color}" opacity=".09"/>
      <polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>
      <circle cx="{coords[-1][0]:.1f}" cy="{coords[-1][1]:.1f}" r="3.5" fill="{color}"/>
      <g fill="#62716a" font-size="10" font-family="system-ui,sans-serif">
      <text x="32" y="18" text-anchor="end">{high:g}</text><text x="32" y="76" text-anchor="end">{low:g}</text>
      <text x="40" y="96">Day {min_day}</text><text x="290" y="96" text-anchor="end">{max_day}</text></g></svg>'''


def render_colony_svg(state: dict[str, Any]) -> str:
    """Return an accessible illustrated atlas with real simulation site positions."""
    frontier = state.get("frontier", {})
    sites = frontier.get("sites", [])
    population = _number(state.get("population"))
    buildings = min(12, max(1, math.ceil(population / 6))) if population else 0
    center_x, center_y = 450, 243
    decorations = []
    # Terrain marks are illustrative. Site positions below are simulation data.
    for x, y in [(88, 120), (120, 152), (88, 178), (730, 102), (772, 128), (812, 99), (188, 325), (225, 347)]:
        decorations.append(f'<path d="M{x-9} {y+12}l9 -24 9 24z M{x} {y+12}v9" fill="#567a66" stroke="#365d4d" stroke-width="1.4" opacity=".7"/>')
    for x, y in [(603, 100), (650, 120), (108, 270), (730, 336)]:
        decorations.append(f'<path d="M{x-21} {y+12}l21 -30 22 30 M{x-7} {y-8}l7 5 7 -5" fill="none" stroke="#8ca48b" stroke-width="2"/>')
    routes, markers, village = [], [], []
    expedition = frontier.get("expedition") or {}
    for index, site in enumerate(sites):
        x = 95 + max(0, min(100, _number(site.get("x", 50)))) * 7.1
        y = 85 + max(0, min(100, _number(site.get("y", 50)))) * 3.15
        discovered = bool(site.get("discovered"))
        active = site.get("id") == expedition.get("site_id")
        color = "#d6a04d" if active else "#245848" if discovered else "#87988a"
        routes.append(f'<path d="M{center_x} {center_y}Q{x:.0f} {center_y-55} {x:.0f} {y:.0f}" fill="none" stroke="{color}" stroke-width="{3 if active else 1.5}" stroke-dasharray="6 7" opacity=".7"/>')
        name = str(site.get("name", f"Site {index + 1}"))
        label = name if discovered else f"Uncharted {_title(site.get('biome', 'site')).lower()}"
        status = "Discovered" if discovered else "Expedition in progress" if active else "Unsurveyed"
        visits = _number(site.get("survey"))
        required = max(1, _number(expedition.get("required"), 1))
        percent = min(100, max(0, _number(expedition.get("progress")) / required * 100)) if active else 100 if discovered else 0
        markers.append(f'''<g><title>{_esc(name)}: {status}; {visits:g} completed visits; {'current expedition' if active else 'discovery'} {percent:g}%</title>
          <circle cx="{x:.0f}" cy="{y:.0f}" r="17" fill="#f5f3e7" stroke="{color}" stroke-width="2"/>
          <text x="{x:.0f}" y="{y+5:.0f}" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" fill="{color}">{index+1 if discovered else '?'}</text>
          <text x="{x:.0f}" y="{y+34:.0f}" text-anchor="middle" font-family="system-ui,sans-serif" font-weight="600" font-size="12" fill="#204b3c" stroke="#eef1df" stroke-width="5" paint-order="stroke">{_esc(label)}</text>
          <rect x="{x-28:.0f}" y="{y+43:.0f}" width="56" height="3" rx="1.5" fill="#c9d5bf"/>
          <rect x="{x-28:.0f}" y="{y+43:.0f}" width="{percent*.56:.1f}" height="3" rx="1.5" fill="{color}"/></g>''')
    for index in range(buildings):
        col, row = index % 4, index // 4
        x, y = 400 + col * 28, 198 + row * 26
        village.append(f'<g><rect x="{x}" y="{y}" width="19" height="16" rx="1" fill="#e8d3a8" stroke="#284e3e"/><path d="M{x-3} {y}l12 -10 13 10z" fill="#466450" stroke="#284e3e"/><rect x="{x+8}" y="{y+7}" width="5" height="9" fill="#365846"/></g>')
    name = state.get("colony_name", "Blergen")
    discovered = sum(bool(site.get("discovered")) for site in sites)
    title = f"{name} frontier atlas, after day {_completed_day(state)}"
    description = f"{_fmt(population)} settlers. {discovered} of {len(sites)} frontier sites discovered. Site coordinates come from the simulation. Terrain and settlement buildings are illustrative."
    empty = '<text x="450" y="343" text-anchor="middle" fill="#486b53" font-size="15" font-family="system-ui,sans-serif">Frontier surveys begin with the next daily run.</text>' if not sites else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500" role="img" aria-labelledby="atlas-title atlas-desc">
      <title id="atlas-title">{_esc(title)}</title><desc id="atlas-desc">{_esc(description)}</desc>
      <defs><pattern id="grid" width="45" height="45" patternUnits="userSpaceOnUse"><path d="M45 0H0V45" fill="none" stroke="#cad4bd" stroke-width=".7"/></pattern></defs>
      <rect width="900" height="500" rx="16" fill="#eaf0dc"/><rect x="22" y="22" width="856" height="422" fill="url(#grid)"/>
      <g fill="none" stroke="#d2ddc3" stroke-width="1.5"><path d="M0 143Q110 49 268 107T541 80T900 77"/><path d="M0 158Q110 64 268 122T541 95T900 92"/><path d="M0 175Q110 81 268 139T541 112T900 109"/><path d="M0 369Q110 280 300 361T594 334T900 319"/><path d="M0 384Q110 295 300 376T594 349T900 334"/><path d="M0 399Q110 310 300 391T594 364T900 349"/></g>
      <path d="M518 0C465 102 680 156 607 247S593 395 658 455" fill="none" stroke="#c5dcd5" stroke-width="31"/>
      <path d="M518 0C465 102 680 156 607 247S593 395 658 455" fill="none" stroke="#f1f6e9" stroke-width="2" opacity=".85"/>
      {''.join(decorations)}{''.join(routes)}
      <ellipse cx="450" cy="238" rx="84" ry="56" fill="#d7dfbd" stroke="#a6b595" stroke-dasharray="3 5"/>
      {''.join(village)}{''.join(markers)}
      <rect x="375" y="284" width="150" height="30" rx="15" fill="#183f32"/>
      <text x="450" y="304" text-anchor="middle" fill="#f4f3e5" font-family="system-ui,sans-serif" font-size="15" font-weight="700">{_esc(str(name)[:20])}</text>
      {empty}<g transform="translate(843,45)" stroke="#466553" fill="none"><path d="M0 42V0l-6 15 6 -4 6 4z" stroke-width="1.5"/><text x="0" y="-8" text-anchor="middle" stroke="none" fill="#466553" font-family="system-ui,sans-serif" font-size="11">N</text></g>
      <rect x="0" y="452" width="900" height="48" fill="#173f32"/>
      <text x="25" y="481" fill="#edf1df" font-family="system-ui,sans-serif" font-size="12" letter-spacing="1.5">FRONTIER ATLAS / DAY {_completed_day(state)}</text>
      <text x="875" y="481" text-anchor="end" fill="#c9d9c1" font-family="system-ui,sans-serif" font-size="12">{discovered} / {len(sites)} sites discovered</text>
    </svg>'''


CSS = '''
:root{color-scheme:light;--ink:#173f32;--muted:#5c6e60;--paper:#f5f4eb;--line:#d7dfd0;--accent:#b78431}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,Helvetica,sans-serif;line-height:1.6}a{color:inherit}a:focus-visible,summary:focus-visible{outline:3px solid #b78431;outline-offset:5px}.skip{position:absolute;left:16px;top:-80px;background:#fff;padding:10px;z-index:5}.skip:focus{top:10px}
.wrap{max-width:1320px;margin:auto;padding:0 40px}.topbar{border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:20px;padding:24px 0;font-size:12px;font-weight:bold;letter-spacing:2px}.brand{display:flex;align-items:center;gap:12px}.brand svg{width:28px;height:28px}.topbar nav{display:flex;gap:25px;letter-spacing:.4px;font-weight:normal}.topbar nav a{text-decoration:none}.topbar nav a:hover{text-decoration:underline}.eyebrow{font-size:11px;letter-spacing:2px;text-transform:uppercase;font-weight:bold;color:var(--muted);margin:0 0 10px}.hero{display:flex;justify-content:space-between;gap:30px;align-items:flex-end;padding:48px 0 30px}h1{font-family:Georgia,'Times New Roman',serif;font-size:clamp(44px,6vw,74px);line-height:1.02;letter-spacing:-3px;margin:0 0 16px;font-weight:normal}h1 span{color:#5e7862}h2{font-size:23px;font-family:Georgia,'Times New Roman',serif;font-weight:normal;line-height:1.3;margin:0}h3{font-size:15px;line-height:1.4;margin:0}.subtitle{color:var(--muted);margin:0;max-width:600px;font-size:15px}.stamp{border-left:1px solid var(--line);padding-left:28px;min-width:190px;font-size:13px;color:var(--muted)}.stamp strong{font-family:Georgia,serif;font-size:34px;line-height:1.2;display:block;color:var(--ink);font-weight:normal}.stamp p{margin:7px 0 0}.attention{border:1px solid #decdac;background:#f3ead8;color:#684f29;border-radius:8px;padding:12px 18px;font-size:13px;margin:0 0 24px}.grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:24px}.card{background:#fcfcf7;border:1px solid var(--line);border-radius:14px;overflow:hidden}.head{display:flex;align-items:center;justify-content:space-between;gap:15px;padding:24px 25px 17px}.head .eyebrow{margin:0 0 5px}.tag{display:inline-block;border:1px solid var(--line);border-radius:20px;padding:3px 10px;font-size:10px;letter-spacing:.7px;text-transform:uppercase;white-space:nowrap}.atlas{padding:0 16px}.atlas svg{width:100%;height:auto;display:block}.caption{color:var(--muted);font-size:11px;line-height:1.5;padding:12px 25px 19px;margin:0}.fieldnotes{padding:0 25px 22px}.dispatch{font-size:14px;color:#3e5946;margin:0 0 20px}.focus{border-left:2px solid var(--accent);padding-left:15px;margin-bottom:24px}.focus .eyebrow{color:#89632b;margin-bottom:6px}.focus p{margin:6px 0 0;font-size:13px;color:var(--muted)}.progress-label{display:flex;justify-content:space-between;gap:12px;font-size:12px;margin:12px 0 6px}.track{height:6px;background:#e5eadc;border-radius:5px;overflow:hidden}.track span{display:block;height:100%;background:#4c7254;border-radius:5px}.smallstats{display:flex;gap:20px;border-top:1px solid var(--line);padding-top:18px}.smallstats strong{display:block;font-size:26px;font-family:Georgia,serif;font-weight:normal}.smallstats span{font-size:11px;color:var(--muted)}.section{margin-top:35px}.sectiontitle{display:flex;justify-content:space-between;gap:20px;align-items:center;margin:0 0 17px}.sectiontitle p{font-size:12px;color:var(--muted);margin:0}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.metric{padding:20px 20px 12px}.metric-top{display:flex;align-items:center;justify-content:space-between;gap:10px}.metric-top h3{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted)}.value{font-family:Georgia,serif;font-size:35px;margin:7px 0 0;line-height:1.25}.value small{font-family:Arial,sans-serif;font-size:13px;color:var(--muted)}.delta{font-size:11px;color:#547258;white-space:nowrap}.spark{display:block;width:100%;height:auto;max-height:112px}.chart-empty{font-size:11px;color:var(--muted);min-height:66px;display:flex;align-items:center;margin:4px 0}.ledger{padding:0 24px 21px}.project{padding:13px 0;border-bottom:1px solid var(--line)}.project:last-child{border:0}.project summary{cursor:pointer;font-size:13px;font-weight:bold}.project p{font-size:12px;color:var(--muted);margin:10px 0}.project summary .tag{float:right;font-size:9px;font-weight:normal}.people{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.person{padding:20px}.avatar{width:37px;height:37px;border:1px solid #c6d2be;border-radius:50%;display:grid;place-items:center;font-family:Georgia,serif;font-size:14px;background:#edf0e2;margin-bottom:14px}.role{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin:4px 0 14px}.quote{font-family:Georgia,serif;font-size:16px;line-height:1.6;margin:0 0 15px}.personal{font-size:12px;color:var(--muted);margin:0}.chronicle{list-style:none;margin:0;padding:0 25px 20px}.chronicle li{display:grid;grid-template-columns:60px 1fr;gap:17px;padding:18px 0;border-bottom:1px solid var(--line)}.chronicle li:last-child{border-bottom:0}.chronicle time{font-size:10px;letter-spacing:1px;color:var(--muted);padding-top:2px}.chronicle h3{font-size:13px}.chronicle p{font-size:12px;line-height:1.6;color:var(--muted);margin:6px 0 0}.muted{color:var(--muted);font-size:13px}.table-wrap{overflow-x:auto}table{border-collapse:collapse;font-size:12px;width:100%;margin-top:10px}th,td{text-align:right;padding:8px 10px;border-bottom:1px solid var(--line)}th:first-child,td:first-child{text-align:left}.data{margin-top:14px;font-size:12px;color:var(--muted)}.data summary{cursor:pointer}.milestone{padding:10px 0;border-bottom:1px solid var(--line);font-size:13px}.milestone span{font-size:10px;color:var(--muted);display:block}.footer{margin-top:40px;padding:24px 0 35px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:20px;font-size:11px;color:var(--muted)}
@media(max-width:900px){.wrap{padding:0 24px}.grid{grid-template-columns:1fr}.fieldnotes{display:grid;grid-template-columns:1fr 1fr;gap:15px}.fieldnotes .dispatch{grid-column:1/-1}.smallstats{grid-column:1/-1}.metrics{gap:12px}.people{gap:12px}.stamp{min-width:170px}.hero{padding-top:35px}}
@media(max-width:600px){.wrap{padding:0 16px}.topbar{padding:19px 0;font-size:10px;letter-spacing:1.2px}.topbar nav{gap:13px;font-size:11px}.topbar nav a:last-child{display:none}.hero{display:block;padding:28px 0 23px}h1{letter-spacing:-2px}.stamp{border:0;padding:18px 0 0;display:flex;align-items:center;gap:14px}.stamp strong{font-size:24px}.stamp .eyebrow{margin:0}.stamp p{margin:0;font-size:11px}.subtitle{font-size:13px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.metric{padding:16px 12px 8px}.value{font-size:29px}.metric-top{display:block}.delta{display:block;margin-top:2px}.sectiontitle{align-items:flex-start}.sectiontitle p{max-width:145px;text-align:right;font-size:10px}.head{padding:21px 20px 15px}.head h2{font-size:21px}.tag{font-size:9px}.fieldnotes{display:block;padding:0 20px 20px}.focus{margin-bottom:18px}.people{grid-template-columns:1fr}.person{display:grid;grid-template-columns:42px 1fr;column-gap:12px}.person .avatar{grid-row:1/3}.person .role{margin-bottom:10px}.person .quote,.person .personal{grid-column:2}.footer{display:block}.footer span{display:block;margin-bottom:8px}.caption{font-size:10px;padding:10px 20px 17px}.atlas{padding:0 8px}.chronicle{padding:0 20px 15px}.chronicle li{grid-template-columns:49px 1fr;gap:10px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}@media print{body{background:white}.wrap{max-width:none;padding:0}.topbar nav,.data{display:none}.card{break-inside:avoid}.hero{padding-top:24px}.section{margin-top:20px}}
'''


def _projects(frontier: dict[str, Any]) -> str:
    result = []
    for project in frontier.get("projects", []):
        done = project.get("completed_day") is not None
        required = max(1, _number(project.get("required"), 1))
        progress = _number(project.get("progress"))
        percent = max(0, min(100, progress / required * 100))
        tag = f"Day {_fmt(project['completed_day'])}" if done else f"{percent:.0f}%"
        result.append(f'''<details class="project"><summary>{_esc(project.get('name','Project'))} <span class="tag">{'Complete · ' if done else ''}{tag}</span></summary>
          <p>{_esc(project.get('description',''))}</p><div class="progress-label"><span>Work recorded</span><span>{progress:g} / {required:g}</span></div>
          <div class="track" role="img" aria-label="{percent:.0f} percent complete"><span style="width:{percent:.1f}%"></span></div></details>''')
    return "".join(result) or '<p class="muted">A new chapter of civic projects begins on the next daily run.</p>'


def _people(state: dict[str, Any]) -> str:
    living = [p for p in state.get("people", []) if p.get("status", {}).get("alive", True)]
    if not living:
        return '<p class="muted">No living settlers are recorded. The chronicle preserves their history.</p>'
    # Rotate the portraits daily, preferring people who appeared in the last event.
    offset = _completed_day(state) % len(living)
    candidates = living[offset:] + living[:offset]
    recent = (state.get("event_log") or [{}])[-1]
    recent_ids = {p.get("id") for a in recent.get("people_events", {}).get("actions", []) for p in a.get("people", [])}
    candidates.sort(key=lambda person: person.get("id") not in recent_ids)
    cards = []
    for person in candidates[:3]:
        name = str(person.get("name", "Unnamed settler"))
        initials = "".join(part[0] for part in name.split()[:2])
        personality = person.get("personality", {})
        desire = personality.get("desire", "to see the settlement endure")
        events = person.get("story", {}).get("notable_events", [])
        story = events[-1] if events else "Their story is still being written."
        cards.append(f'''<article class="card person"><div class="avatar" aria-hidden="true">{_esc(initials)}</div><h3>{_esc(name)}</h3>
          <p class="role">{_esc(_title(person.get('role','settler')))} · age {_fmt(person.get('age'))}</p>
          <p class="quote">Hopes {_esc(desire)}.</p><p class="personal">{_esc(story)}</p></article>''')
    return "".join(cards)


def render_dashboard(state: dict[str, Any]) -> str:
    """Render a complete offline HTML dashboard without mutating ``state``."""
    frontier = state.get("frontier", {})
    points = _timeline(state)
    day = _completed_day(state)
    date = date_for_day(max(1, day))
    name = _esc(state.get("colony_name", "Blergen"))
    events = state.get("event_log", [])
    latest = events[-1] if events else {}
    report = frontier.get("last_report", {})
    population = _number(state.get("population"))
    food_days = _number(state.get("food")) / population if population else 0
    worries = [f"{_title(key)} is {_fmt(state[key])}/10" for key in ("health", "morale", "security") if key in state and _number(state[key]) <= 3]
    if population and food_days < 3:
        worries.append(f"Food stores cover {food_days:.1f} daily rations")
    attention = f'<aside class="attention"><strong>Watch list</strong> · {_esc(" · ".join(worries))}</aside>' if worries else ""
    metric_cards = []
    colors = {"population": "#417965", "food": "#9b752e", "wood": "#72634c", "health": "#4b8268", "morale": "#807444", "security": "#4e7682"}
    for key in METRICS:
        previous = next((p[key] for p in reversed(points[:-1]) if key in p), None)
        delta = _number(state.get(key)) - _number(previous) if previous is not None else None
        change = f'{delta:+g} since last observation' if delta is not None else 'Current observation'
        suffix = " / 10" if key in ("health", "morale", "security") else " settlers" if key == "population" else " units"
        metric_cards.append(f'''<article class="card metric"><div class="metric-top"><h3>{_title(key)}</h3><span class="delta">{change}</span></div>
          <p class="value">{_fmt(state.get(key))}<small>{suffix}</small></p>{_chart(points,key,colors[key])}</article>''')
    projects = frontier.get("projects", [])
    complete = sum(p.get("completed_day") is not None for p in projects)
    active_project = next((p for p in projects if p.get("completed_day") is None), None)
    focus = '<div class="focus"><p class="eyebrow">Next civic project</p>'
    if active_project:
        progress = _number(active_project.get("progress"))
        required = max(1, _number(active_project.get("required"), 1))
        percent = max(0, min(100, progress / required * 100))
        focus += f'<h3>{_esc(active_project.get("name","Project"))}</h3><p>{_esc(active_project.get("description",""))}</p><div class="progress-label"><span>Work completed</span><span>{progress:g} / {required:g}</span></div><div class="track" role="img" aria-label="{percent:.0f} percent complete"><span style="width:{percent:.1f}%"></span></div>'
    else:
        focus += '<h3>Foundations for tomorrow</h3><p>Projects and expeditions develop with each daily run.</p>' if not projects else '<h3>A lasting settlement</h3><p>All founding projects are complete. The frontier continues to unfold.</p>'
    focus += '</div>'
    expedition = frontier.get("expedition") or {}
    sites = frontier.get("sites", [])
    site = next((s for s in sites if s.get("id") == expedition.get("site_id")), None)
    if site:
        crew = ", ".join(p.get("name", "Settler") for p in expedition.get("crew", []))
        expedition_html = f'<div class="focus"><p class="eyebrow">Beyond the palisade</p><h3>{_esc(site.get("name","Frontier expedition"))}</h3><p>{_esc(crew or "The scouting party")} · {_fmt(expedition.get("progress"))} / {_fmt(expedition.get("required"))} survey work</p></div>'
    else:
        expedition_html = '<div class="focus"><p class="eyebrow">Beyond the palisade</p><h3>Watching the horizon</h3><p>New surveys reveal resources and stories around the settlement.</p></div>'
    chronicle = []
    for event in reversed(events[-6:]):
        title = _title(event.get("world_event", event.get("event_type", "Daily record")))
        summary = event.get("summary", "A day in the settlement.")
        chronicle.append(f'<li><time>DAY {_fmt(event.get("day"))}</time><div><h3>{_esc(title)}</h3><p>{_esc(summary)}</p></div></li>')
    milestone_html = "".join(f'<div class="milestone"><span>DAY {_fmt(m.get("day"))}</span>{_esc(m.get("name", "Milestone"))}</div>' for m in reversed(frontier.get("milestones", [])[-5:]))
    if not milestone_html:
        milestone_html = '<p class="muted">The next discoveries and completed projects will appear here.</p>'
    rows = "".join('<tr><td>'+_fmt(p['day'])+'</td>'+''.join('<td>'+(_fmt(p[k]) if k in p else '—')+'</td>' for k in METRICS)+'</tr>' for p in reversed(points))
    roles = Counter(str(p.get("role", "settler")) for p in state.get("people", []) if p.get("status", {}).get("alive", True))
    role_note = " · ".join(f"{count} {role.replace('_',' ')}{'s' if count != 1 else ''}" for role, count in roles.most_common(4))
    latest_weather = latest.get("weather", {}).get("condition", date["season"])
    dispatch = report.get("summary") or latest.get("summary") or "A small settlement, an open horizon, and a new page waiting in the daily chronicle."
    timeline_note = f"{len(points)} saved observations · independent scales" if len(points) > 1 else "History starts here · no estimated past values"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <meta name="description" content="Daily frontier observatory for {name}: settlement atlas, resources, expeditions and personal stories."><title>{name} · Frontier observatory</title><style>{CSS}</style></head>
      <body><a class="skip" href="#main">Skip to colony report</a><div class="wrap"><header class="topbar"><div class="brand"><svg viewBox="0 0 30 30" aria-hidden="true"><path d="M15 1L28 24H2z M15 7v17 M7 17h16" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="15" cy="15" r="5" fill="none" stroke="currentColor"/></svg>THE FRONTIER OBSERVATORY</div><nav aria-label="Page sections"><a href="#atlas">Atlas</a><a href="#vitals">Vitals</a><a href="#chronicle">Chronicle</a></nav></header>
      <main id="main"><section class="hero"><div><p class="eyebrow">Field report / Chapter {_fmt(frontier.get('chapter',1))}</p><h1>{name}.<br><span>A life on the frontier.</span></h1><p class="subtitle">A living settlement told through its people, its resources, and the country still waiting to be explored.</p></div><div class="stamp"><div><p class="eyebrow">Last completed</p><strong>Day {day:,}</strong></div><p>{date['month']} {date['day_of_month']}, Year {date['year']}<br>{_esc(_title(latest_weather))} · next day {day+1:,}</p></div></section>{attention}
      <div class="grid"><section class="card" id="atlas"><div class="head"><div><p class="eyebrow">The known world</p><h2>Settlement &amp; surroundings</h2></div><span class="tag">{_esc(date['season'])}</span></div><div class="atlas">{render_colony_svg(state)}</div><p class="caption">Illustrated atlas. Site positions use simulation coordinates; terrain and buildings are schematic. Dashed routes show survey destinations. <a href="colony.svg" download>Save atlas SVG</a></p></section>
      <section class="card"><div class="head"><div><p class="eyebrow">The daily dispatch</p><h2>Work worth returning to</h2></div></div><div class="fieldnotes"><p class="dispatch">{_esc(dispatch)}</p>{focus}{expedition_html}<div class="smallstats"><div><strong>{complete} / {len(projects)}</strong><span>civic projects</span></div><div><strong>{sum(bool(s.get('discovered')) for s in sites)} / {len(sites)}</strong><span>sites discovered</span></div><div><strong>{food_days:.1f}</strong><span>days of food*</span></div></div><p class="caption" style="padding:10px 0 0">*At one unit per settler per day, before new production.</p></div></section></div>
      <section class="section" id="vitals"><div class="sectiontitle"><h2>The pulse of the colony</h2><p>{timeline_note}</p></div><div class="metrics">{''.join(metric_cards)}</div><details class="data"><summary>Read the observation data</summary><p>Only saved measurements are plotted. Older event effects do not reliably reconstruct absolute resource levels after limits and interventions.</p><div class="table-wrap"><table><caption>Most recent 120 daily observations</caption><thead><tr><th scope="col">Day</th>{''.join('<th scope="col">'+_title(k)+'</th>' for k in METRICS)}</tr></thead><tbody>{rows}</tbody></table></div></details></section>
      <section class="section" id="people"><div class="sectiontitle"><h2>Lives behind the numbers</h2><p>{_esc(role_note)}</p></div><div class="people">{_people(state)}</div></section>
      <div class="grid section"><section class="card" id="chronicle"><div class="head"><div><p class="eyebrow">From the colony ledger</p><h2>The recent chronicle</h2></div><span class="tag">{len(events):,} recorded days</span></div><ol class="chronicle">{''.join(chronicle) or '<li><p class="muted">The first daily entry has yet to be written.</p></li>'}</ol></section><section class="card"><div class="head"><div><p class="eyebrow">What we are building</p><h2>A settlement that lasts</h2></div></div><div class="ledger">{_projects(frontier)}<p class="eyebrow" style="margin-top:25px">Milestones</p>{milestone_html}</div></section></div></main>
      <footer class="footer"><span>{name} / The frontier observatory / After simulation day {day:,}</span><span>Generated from the saved colony · Works offline · No external assets</span></footer></div></body></html>'''


def write_dashboard(state: dict[str, Any], output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    """Write HTML and SVG artifacts; do not modify or advance the colony."""
    if "frontier" not in state:
        # Display the planned map for legacy saves without issuing relief or
        # persisting a migration. The first daily run owns that state transition.
        from src.frontier import ensure_frontier

        state = ensure_frontier(state)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path, svg_path = output_dir / "index.html", output_dir / "colony.svg"
    html_path.write_text(render_dashboard(state), encoding="utf-8")
    svg_path.write_text(render_colony_svg(state), encoding="utf-8")
    return html_path, svg_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the saved colony without advancing time or calling AI.")
    parser.add_argument("--state", type=Path, default=Path(__file__).with_name("state.json"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8"))
    for path in write_dashboard(state, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()

"""Durable frontier work, exploration, and subsistence without external services.

The original event mechanics remain usable alone. ``prepare_frontier`` opts a
save into this layer; ordinary household work then continues alongside the
president's daily order. All public preparation helpers return independent
copies. Day application helpers deliberately mutate the next-day state.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.people import add_new_people, ensure_people_exist, living_people

PROJECTS = (
    ("kitchen_gardens", "Kitchen gardens", "Cold frames and roots provide dependable daily food.", 10),
    ("rain_cistern", "Rain cistern", "Clean water softens heat and cold-weather sickness.", 14),
    ("watchtower", "Watchtower", "Maintained patrols keep the settlement secure.", 18),
    ("clinic", "Village clinic", "Routine care helps the colony recover from illness.", 22),
    ("river_dock", "River dock", "Fishing crews bring home a second dependable food supply.", 26),
    ("observatory", "Hill observatory", "A survey archive turns return journeys into new knowledge.", 30),
)
SITES = (
    ("river", "Silver river", "river", 24, 31, 6, "A sheltered bend holds fish through the winter."),
    ("pinewood", "Whispering pines", "forest", 20, 68, 8, "Resin-rich fallen pine can heat the settlement."),
    ("ridge", "Copper ridge", "mountain", 65, 18, 10, "A high pass connects the old trails beyond the valley."),
    ("marsh", "Lantern marsh", "wetland", 78, 70, 12, "Night-blooming reeds mark a safe path across the marsh."),
    ("ruins", "The old waystation", "ruins", 85, 38, 14, "Weathered route records hint at an earlier settlement."),
    ("beacon", "Distant beacon", "mountain", 45, 7, 16, "The old beacon offers a view beyond the colony's first map."),
)
PROJECT_ACTIONS = {
    "kitchen_gardens": {"expand_fields", "harvest_crops"},
    "rain_cistern": {"gather_clay", "make_pottery"},
    "watchtower": {"strengthen_defenses", "gather_wood"},
    "clinic": {"tend_the_sick"},
    "river_dock": {"gather_wood", "send_scouts"},
    "observatory": {"send_scouts", "build_with_brick"},
}
RETURN_FINDINGS = (
    "mapped a safer crossing",
    "recorded a seasonal wildlife migration",
    "recovered a fragment of the old route archive",
    "marked a sheltered overnight camp",
    "charted a clear view of the evening stars",
    "identified a useful medicinal plant",
)


def ensure_frontier(state: dict[str, Any]) -> dict[str, Any]:
    """Copy and migrate a save without running time, issuing aid, or editing people."""
    updated = deepcopy(state)
    frontier = updated.setdefault("frontier", {})
    frontier.setdefault("version", 1)
    frontier.setdefault("chapter", 1)
    frontier.setdefault("started_day", int(updated.get("day", 1)))
    frontier.setdefault("focus", "Rebuild the settlement")
    frontier.setdefault("knowledge", 0)
    frontier.setdefault("expeditions_completed", 0)
    frontier.setdefault("milestones", [])
    frontier.setdefault("timeline", [])
    frontier.setdefault("archive", [])
    frontier.setdefault("expedition", None)
    frontier.setdefault("last_report", {})
    frontier.setdefault("relief_convoys", 0)
    frontier.setdefault("last_relief_day", None)
    frontier.setdefault("empty_since_day", None)
    # Fill missing catalog entries by identity, preserving every saved result.
    existing_projects = {p["id"]: p for p in frontier.get("projects", [])}
    projects = []
    for identifier, name, description, required in PROJECTS:
        project = existing_projects.pop(identifier, {})
        defaults = {"id": identifier, "name": name, "description": description,
                    "progress": 0, "required": required, "completed_day": None}
        projects.append({**defaults, **project})
    frontier["projects"] = projects + list(existing_projects.values())
    existing_sites = {s["id"]: s for s in frontier.get("sites", [])}
    sites = []
    for identifier, name, biome, x, y, required, finding in SITES:
        site = existing_sites.pop(identifier, {})
        defaults = {"id": identifier, "name": name, "biome": biome, "x": x, "y": y,
                    "required": required, "finding": finding, "discovered": False,
                    "survey": 0, "discovered_day": None}
        sites.append({**defaults, **site})
    frontier["sites"] = sites + list(existing_sites.values())
    return updated


def prepare_frontier(state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Activate frontier life, preserving the old cast and any earlier history.

    An already abandoned legacy save receives one modest relief expedition.
    Later extinctions wait thirty simulated days, leaving their consequences in
    the chronicle. This is new immigration, never resurrection or a world reset.
    """
    newly_activated = "frontier" not in state
    updated = ensure_frontier(ensure_people_exist(state))
    frontier = updated["frontier"]
    day = int(updated.get("day", 1))
    if updated["population"] > 0:
        frontier["empty_since_day"] = None
        return updated, []
    if frontier["empty_since_day"] is None:
        frontier["empty_since_day"] = day
    last_relief = frontier["last_relief_day"]
    waiting_since = max(last_relief or 0, frontier["empty_since_day"])
    if not newly_activated and day - waiting_since < 30:
        return updated, []
    newcomers = add_new_people(
        updated, 12, colony_health=7, colony_morale=7,
        story_note="{name} joined the frontier relief expedition to rebuild among the old settlement's remains.",
    )
    food_before, wood_before = updated.get("food", 0), updated.get("wood", 0)
    updated["food"] = max(food_before, 12 * 10)
    updated["wood"] = max(wood_before, 40)
    updated["security"] = max(updated.get("security", 0), 4)
    frontier["relief_convoys"] += 1
    frontier["last_relief_day"] = day
    frontier["empty_since_day"] = None
    frontier["chapter"] += 1
    frontier["expedition"] = None
    record = {"type": "frontier_relief", "day": day,
              "source": "Blergen Company", "effects": {
                  "population": len(newcomers), "food": updated["food"] - food_before,
                  "wood": updated["wood"] - wood_before},
              "summary": "Twelve new settlers arrived to rebuild Blergen; the old dead and their history remain remembered."}
    frontier["archive"].append({"day": day, "summary": record["summary"]})
    return updated, [record]


def daily_frontier_effects(
    state: dict[str, Any], environment: dict[str, Any],
) -> dict[str, int]:
    """Routine work takes place even when leadership is busy with a crisis."""
    frontier = state.get("frontier")
    population = int(state.get("population", 0))
    if not frontier or population <= 0:
        return {}
    complete = _completed_projects(frontier)
    discovered = {s["id"] for s in frontier["sites"] if s.get("discovered")}
    season = environment.get("date", {}).get("season", "spring")
    food_percent = 75 if season == "winter" else 85
    food_percent += 30 * ("kitchen_gardens" in complete)
    food_percent += 15 * ("river_dock" in complete)
    food_percent += 5 * ("river" in discovered)
    food = max(1, (population * food_percent + 99) // 100)
    # Stop adding routine surplus at a ninety-day reserve; deliberate harvests
    # and trade may still exceed this, without silently deleting old supplies.
    effects = {"food": min(food, max(0, population * 90 - int(state.get("food", 0)))),
               "wood": min(2 + ("pinewood" in discovered), max(0, 600 - int(state.get("wood", 0))))}
    day = int(state.get("day", 1))
    if day % 3 == 0 and state.get("morale", 0) < 7:
        effects["morale"] = 1  # Shared meals and ordinary companionship.
    if "watchtower" in complete and state.get("security", 0) < 6:
        effects["security"] = 1
    if "clinic" in complete and state.get("health", 0) < 7:
        effects["health"] = 1
    condition = environment.get("weather", {}).get("condition")
    if "rain_cistern" in complete and condition in {
        "hard_freeze", "dry_heat", "hot", "cold_rain", "early_frost"
    }:
        effects["health"] = effects.get("health", 0) + 1
    return {key: value for key, value in effects.items() if value}


def advance_frontier(
    state: dict[str, Any], *, day: int, world_event: str, leadership_action: str,
    environment: dict[str, Any], production: dict[str, int],
) -> dict[str, Any]:
    """Finish work and expeditions after survival; mutate the next state."""
    if "frontier" not in state:
        return {}
    frontier = state["frontier"]
    report: dict[str, Any] = {"production": production, "completed": [], "discoveries": []}
    if not living_people(state):
        frontier["expedition"] = None
        if frontier["empty_since_day"] is None:
            frontier["empty_since_day"] = day
        report["summary"] = "The frontier camps stand empty; the company is awaiting its next relief window."
        frontier["focus"] = "Await a relief expedition"
    else:
        _advance_project(state, day, leadership_action, report)
        _advance_expedition(state, day, world_event, leadership_action, environment, report)
        _record_milestones(state, day, report)
        if "summary" not in report:
            if report["completed"]:
                report["summary"] = f"The colony completed {report['completed'][0]['name']}."
            elif report["discoveries"]:
                report["summary"] = report["discoveries"][0]["summary"]
            else:
                project = next((p for p in frontier["projects"] if p.get("completed_day") is None), None)
                report["summary"] = (f"Work on {project['name']} reached {project['progress']}/{project['required']}."
                                     if project else "Survey crews continued adding to the frontier archive.")
        project = next((p for p in frontier["projects"] if p.get("completed_day") is None), None)
        frontier["focus"] = f"Build {project['name']}" if project else "Chart the wider frontier"
    frontier["last_report"] = deepcopy(report)
    frontier["timeline"].append({"day": day, **{key: state.get(key, 0) for key in
        ("population", "food", "wood", "morale", "health", "security")},
        "sites": sum(bool(s.get("discovered")) for s in frontier["sites"]),
        "projects": len(_completed_projects(frontier))})
    frontier["timeline"] = frontier["timeline"][-120:]
    frontier["archive"] = frontier["archive"][-120:]
    return report


def _completed_projects(frontier: dict[str, Any]) -> set[str]:
    return {p["id"] for p in frontier.get("projects", []) if p.get("completed_day") is not None}


def _advance_project(state: dict[str, Any], day: int, action: str, report: dict[str, Any]) -> None:
    frontier = state["frontier"]
    project = next((p for p in frontier["projects"] if p.get("completed_day") is None), None)
    if project is None:
        return
    if state.get("food", 0) < state["population"] or state.get("health", 0) <= 2:
        report["summary"] = "Building crews paused their project to concentrate on food and recovery."
        return
    work = min(1 + (action in PROJECT_ACTIONS.get(project["id"], set())),
               max(0, int(state.get("wood", 0))), project["required"] - project["progress"])
    project["progress"] += work
    state["wood"] -= work
    if project["progress"] >= project["required"]:
        project["completed_day"] = day
        completion = {"id": project["id"], "name": project["name"], "day": day}
        report["completed"].append(completion)
        frontier["archive"].append({"day": day, "summary": f"The colony completed {project['name']}."})


def _advance_expedition(
    state: dict[str, Any], day: int, world_event: str, action: str,
    environment: dict[str, Any], report: dict[str, Any],
) -> None:
    frontier = state["frontier"]
    expedition = frontier["expedition"]
    people = living_people(state)
    people_by_id = {p["id"]: p for p in people}
    if expedition:
        expedition["crew"] = [p for p in expedition["crew"] if p["id"] in people_by_id]
        if not expedition["crew"]:
            frontier["expedition"] = None
            return
    if state.get("food", 0) < state["population"] * 2 or state.get("health", 0) < 4 or state.get("security", 0) < 3:
        if expedition:
            report["expedition_status"] = "Paused while the settlement recovers."
        return
    if expedition is None:
        site = next((s for s in frontier["sites"] if not s.get("discovered")), None)
        if site is None:
            site = min(frontier["sites"], key=lambda s: (s["survey"], s["id"]))
        available = sorted(people, key=lambda p: (p.get("role") != "scout", p["id"]))
        offset = (frontier["expeditions_completed"] * 2) % len(available)
        crew = (available[offset:] + available[:offset])[:2]
        expedition = {"site_id": site["id"], "progress": 0,
                      "required": site["required"] if not site["discovered"] else 10 + min(site["survey"], 20),
                      "started_day": day, "crew": [{"id": p["id"], "name": p["name"]} for p in crew]}
        frontier["expedition"] = expedition
    weather = environment.get("weather", {})
    if world_event == "storm" or (weather.get("severity", 1) >= 4 and weather.get("condition") in {"winter_storm", "thunderstorm"}):
        report["expedition_status"] = "The expedition sheltered from dangerous weather."
        return
    expedition["progress"] += 3 if action == "send_scouts" else 1
    state["food"] -= max(1, state["population"] // 10)
    if expedition["progress"] < expedition["required"]:
        return
    site = next(s for s in frontier["sites"] if s["id"] == expedition["site_id"])
    first_visit = not site["discovered"]
    site["discovered"] = True
    site["survey"] += 1
    if first_visit:
        site["discovered_day"] = day
    frontier["expeditions_completed"] += 1
    knowledge = 3 if first_visit else 1 + ("observatory" in _completed_projects(frontier))
    frontier["knowledge"] += knowledge
    finding = site["finding"] if first_visit else (
        f"At {site['name']}, the returning crew {RETURN_FINDINGS[(site['survey'] + day) % len(RETURN_FINDINGS)]}."
    )
    discovery = {"id": site["id"], "name": site["name"], "first_visit": first_visit,
                 "day": day, "knowledge": knowledge, "crew": deepcopy(expedition["crew"]),
                 "summary": finding}
    report["discoveries"].append(discovery)
    frontier["archive"].append({"day": day, "summary": finding})
    for ref in expedition["crew"]:
        person = people_by_id[ref["id"]]
        person.setdefault("story", {}).setdefault("notable_events", []).append(
            f"On day {day}, {person['name']} returned from {site['name']}: {finding}"
        )
    frontier["expedition"] = None


def _record_milestones(state: dict[str, Any], day: int, report: dict[str, Any]) -> None:
    frontier = state["frontier"]
    complete = _completed_projects(frontier)
    milestones = (
        ("first_roots", "First roots", "kitchen_gardens" in complete),
        ("first_expedition", "Beyond the palisade", frontier["expeditions_completed"] >= 1),
        ("safe_harbor", "A safe harbor", "watchtower" in complete and state["health"] >= 5),
        ("full_map", "The valley charted", all(s["discovered"] for s in frontier["sites"])),
        ("settlement", "A lasting settlement", len(complete) >= len(PROJECTS)),
        ("archive_25", "Keepers of the archive", frontier["knowledge"] >= 25),
        ("archive_100", "A hundred discoveries", frontier["knowledge"] >= 100),
    )
    achieved = {m["id"] for m in frontier["milestones"]}
    for identifier, name, condition in milestones:
        if condition and identifier not in achieved:
            milestone = {"id": identifier, "name": name, "day": day}
            frontier["milestones"].append(milestone)
            report.setdefault("milestones", []).append(milestone)

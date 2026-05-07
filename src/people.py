"""Individual colonist identity and lifecycle helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

STARVATION_HUNGER_THRESHOLD = 3

FIRST_NAMES = (
    "Ada",
    "Bram",
    "Cora",
    "Dain",
    "Elia",
    "Finn",
    "Galen",
    "Hana",
    "Iris",
    "Jory",
    "Kara",
    "Lio",
    "Mara",
    "Niko",
    "Orin",
    "Pia",
    "Quin",
    "Rhea",
    "Soren",
    "Talia",
    "Una",
    "Vera",
    "Wynn",
    "Xara",
    "Yuri",
    "Zara",
)

LAST_NAMES = (
    "Aster",
    "Bren",
    "Cairn",
    "Dove",
    "Ember",
    "Fenn",
    "Graye",
    "Hale",
    "Ivory",
    "Joss",
    "Kest",
    "Lark",
    "Moss",
    "Nell",
    "Orrow",
    "Pike",
    "Quill",
    "Reed",
    "Stone",
    "Thorne",
    "Umber",
    "Vale",
    "Wick",
    "Yarrow",
    "Zane",
)

ROLES = (
    "farmer",
    "woodcutter",
    "scout",
    "builder",
    "healer",
    "cook",
    "guard",
    "teacher",
    "forager",
    "carpenter",
)

TRAITS = (
    "practical",
    "stubborn",
    "protective",
    "curious",
    "patient",
    "restless",
    "wry",
    "gentle",
    "bold",
    "cautious",
    "generous",
    "skeptical",
    "dutiful",
    "inventive",
    "quiet",
    "warm",
    "ambitious",
    "observant",
)

TEMPERAMENTS = (
    "steady",
    "intense",
    "cheerful",
    "guarded",
    "earnest",
    "dry-humored",
)

FEARS = (
    "winter hunger",
    "wolves at the tree line",
    "being forgotten",
    "sickness in crowded rooms",
    "fire in the stores",
    "the colony losing heart",
)

DESIRES = (
    "to build permanent fields",
    "to see the settlement mapped",
    "to keep their family safe",
    "to earn the colony's trust",
    "to make Blergen feel like home",
    "to leave something useful behind",
)


def ensure_people_exist(state: dict[str, Any]) -> dict[str, Any]:
    """Return a state whose people are the source for population stats."""
    updated = deepcopy(state)
    if "people" not in updated:
        updated["people"] = generate_people(
            updated["population"],
            colony_health=updated.get("health", 5),
            colony_morale=updated.get("morale", 5),
        )

    return sync_derived_colony_stats(updated)


def generate_people(
    count: int,
    *,
    colony_health: int = 5,
    colony_morale: int = 5,
    start_index: int = 0,
) -> list[dict[str, Any]]:
    """Generate a deterministic starter cast with distinct names."""
    return [
        _make_person(
            index,
            colony_health=colony_health,
            colony_morale=colony_morale,
        )
        for index in range(start_index, start_index + count)
    ]


def living_people(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all living colonists in state order."""
    return [
        person
        for person in state.get("people", [])
        if person.get("status", {}).get("alive", True)
    ]


def living_population(state: dict[str, Any]) -> int:
    """Count living colonists when people exist, otherwise use population."""
    if "people" not in state:
        return state["population"]

    return len(living_people(state))


def derived_colony_stats(state: dict[str, Any]) -> dict[str, int]:
    """Return aggregate population, health, and morale from living people."""
    people = living_people(state)
    if not people:
        return {
            "population": 0,
            "health": 0,
            "morale": 0,
        }

    return {
        "population": len(people),
        "health": _average_living_stat(people, "health"),
        "morale": _average_living_stat(people, "morale"),
    }


def sync_derived_colony_stats(state: dict[str, Any]) -> dict[str, Any]:
    """Mutate state so aggregate people stats match living colonists."""
    if "people" not in state:
        return state

    state.update(derived_colony_stats(state))
    return state


def ensure_president(state: dict[str, Any]) -> dict[str, Any]:
    """Ensure the colony's president is a specific living colonist."""
    if "people" not in state:
        return state

    people = living_people(state)
    if not people:
        state.pop("president", None)
        return state

    president = current_president(state)
    if president:
        state["president"]["name"] = president["name"]
        return state

    new_president = _select_president(people)
    state["president"] = {
        "id": new_president["id"],
        "name": new_president["name"],
        "since_day": state.get("day", 1),
    }
    _add_story_note(
        new_president,
        f"{new_president['name']} became president of Blergen on day {state.get('day', 1)}.",
    )
    return state


def current_president(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return the living president record, if one exists."""
    president_id = state.get("president", {}).get("id")
    if not president_id:
        return None

    for person in living_people(state):
        if person.get("id") == president_id:
            return person

    return None


def president_context_for_prompt(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return compact current-president context for selector prompts."""
    president = current_president(state)
    if not president:
        return None

    context = _person_prompt_summary(president)
    context["since_day"] = state.get("president", {}).get("since_day")
    return context


def add_new_people(
    state: dict[str, Any],
    count: int,
    *,
    colony_health: int = 6,
    colony_morale: int = 6,
    story_note: str | None = None,
) -> list[dict[str, Any]]:
    """Append new living colonists without reusing old person IDs."""
    if count <= 0:
        return []

    state.setdefault("people", [])
    start_index = _next_person_index(state["people"])
    new_people = generate_people(
        count,
        colony_health=colony_health,
        colony_morale=colony_morale,
        start_index=start_index,
    )
    if story_note:
        for person in new_people:
            _add_story_note(person, story_note.format(name=person["name"]))

    state["people"].extend(new_people)
    sync_derived_colony_stats(state)
    return new_people


def character_context_for_prompt(
    state: dict[str, Any],
    *,
    world_event: str | None = None,
    max_people: int = 8,
) -> dict[str, Any]:
    """Return a bounded named-cast summary for selector prompts."""
    people = living_people(state)
    if not people:
        return {
            "living_population": state.get("population", 0),
            "role_counts": {},
            "status_summary": {},
            "featured_colonists": [],
            "selection_note": "No individual colonists are available in state.",
        }

    featured_people = _featured_people_for_prompt(
        state,
        world_event=world_event,
        max_people=max_people,
    )
    return {
        "living_population": len(people),
        "role_counts": _role_counts(people),
        "status_summary": _status_summary_for_prompt(people),
        "featured_colonists": [
            _person_prompt_summary(person)
            for person in featured_people[:max(0, max_people)]
        ],
        "selection_note": _character_selection_note(world_event),
    }


def apply_population_loss_to_people(
    state: dict[str, Any],
    *,
    loss_count: int,
    day: int,
    cause: str,
) -> list[dict[str, str]]:
    """Mark named colonists dead and return compact death records."""
    if loss_count <= 0 or "people" not in state:
        return []

    deaths = []
    for person in _select_casualties(state, loss_count):
        deaths.append(_mark_person_dead(person, day=day, cause=cause))

    sync_derived_colony_stats(state)
    return deaths


def apply_daily_food_status(
    state: dict[str, Any],
    *,
    missed_rations: int,
    day: int,
) -> dict[str, list[dict[str, Any]]]:
    """Update personal hunger after daily food is consumed."""
    if "people" not in state:
        return {}

    living = living_people(state)
    if not living:
        return {}

    missed_count = max(0, min(missed_rations, len(living)))
    underfed = _select_people_for_missed_rations(state, missed_count)
    underfed_ids = {person["id"] for person in underfed}
    fed = [person for person in living if person["id"] not in underfed_ids]

    for person in fed:
        status = person.setdefault("status", {})
        status["hunger"] = max(0, status.get("hunger", 0) - 1)

    if not underfed:
        return {}

    deaths = []
    for person in underfed:
        status = person.setdefault("status", {})
        status["hunger"] = min(10, status.get("hunger", 0) + 1)
        _add_story_note(person, f"{person['name']} went without a full ration on day {day}.")
        if status["hunger"] >= STARVATION_HUNGER_THRESHOLD:
            deaths.append(_mark_person_dead(person, day=day, cause="starvation"))

    sync_derived_colony_stats(state)
    event = {
        "type": "missed_rations",
        "missed_rations": missed_count,
        "people": _people_refs(underfed),
        "summary": _missed_rations_summary(underfed),
    }
    result: dict[str, list[dict[str, Any]]] = {"actions": [event]}
    if deaths:
        result["deaths"] = deaths

    return result


def apply_daily_people_events(
    state: dict[str, Any],
    *,
    world_event: str,
    leadership_action: str,
    day: int,
    event_details: dict[str, Any] | None = None,
    discovery_detail: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Apply person-level story effects for the day's event and action."""
    people_events: dict[str, list[dict[str, Any]]] = {
        "illnesses": [],
        "conflicts": [],
        "discoveries": [],
        "actions": [],
    }

    _apply_world_event_to_people(
        state,
        people_events=people_events,
        world_event=world_event,
        day=day,
        event_details=event_details or {},
        discovery_detail=discovery_detail,
    )
    _apply_leadership_action_to_people(
        state,
        people_events=people_events,
        leadership_action=leadership_action,
        day=day,
    )

    return {key: value for key, value in people_events.items() if value}


def _make_person(
    index: int,
    *,
    colony_health: int,
    colony_morale: int,
) -> dict[str, Any]:
    return {
        "id": f"person_{index + 1:03d}",
        "name": _name_for_index(index),
        "age": 18 + ((index * 7) % 51),
        "role": ROLES[index % len(ROLES)],
        "personality": {
            "traits": _traits_for_index(index),
            "temperament": TEMPERAMENTS[index % len(TEMPERAMENTS)],
            "fear": FEARS[(index * 2) % len(FEARS)],
            "desire": DESIRES[(index * 3) % len(DESIRES)],
        },
        "relationships": {
            "friends": [],
            "family": [],
            "rivals": [],
        },
        "status": {
            "alive": True,
            "health": max(1, min(10, colony_health)),
            "morale": max(0, min(10, colony_morale)),
            "hunger": 0,
        },
        "story": {
            "notable_events": [],
        },
    }


def _name_for_index(index: int) -> str:
    first = FIRST_NAMES[index % len(FIRST_NAMES)]
    last = LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]
    generation = index // (len(FIRST_NAMES) * len(LAST_NAMES))
    if generation:
        return f"{first} {last} {generation + 1}"

    return f"{first} {last}"


def _traits_for_index(index: int) -> list[str]:
    trait_indexes = (
        index,
        index + 5,
        (index * 3) + 11,
    )
    traits = []
    for trait_index in trait_indexes:
        trait = TRAITS[trait_index % len(TRAITS)]
        if trait not in traits:
            traits.append(trait)

    return traits


def _next_person_index(people: list[dict[str, Any]]) -> int:
    max_index = 0
    for person in people:
        person_id = person.get("id", "")
        if not person_id.startswith("person_"):
            continue
        try:
            max_index = max(max_index, int(person_id.removeprefix("person_")))
        except ValueError:
            continue

    return max_index


def _select_president(people: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        people,
        key=lambda person: (
            -person.get("status", {}).get("morale", 0),
            -person.get("status", {}).get("health", 0),
            -person.get("age", 0),
            person["id"],
        ),
    )[0]


def _select_casualties(
    state: dict[str, Any],
    loss_count: int,
) -> list[dict[str, Any]]:
    vulnerable_people = sorted(
        living_people(state),
        key=lambda person: (
            person.get("status", {}).get("health", 5),
            -person.get("status", {}).get("hunger", 0),
            -person.get("age", 0),
            person["id"],
        ),
    )
    return vulnerable_people[:loss_count]


def _select_people_for_missed_rations(
    state: dict[str, Any],
    missed_count: int,
) -> list[dict[str, Any]]:
    if missed_count <= 0:
        return []

    return sorted(
        living_people(state),
        key=lambda person: (
            person.get("status", {}).get("hunger", 0),
            -person.get("status", {}).get("health", 5),
            -person.get("status", {}).get("morale", 5),
            person["id"],
        ),
    )[:missed_count]


def _average_living_stat(people: list[dict[str, Any]], stat: str) -> int:
    total = sum(person.get("status", {}).get(stat, 0) for person in people)
    return max(0, min(10, total // len(people)))


def _featured_people_for_prompt(
    state: dict[str, Any],
    *,
    world_event: str | None,
    max_people: int,
) -> list[dict[str, Any]]:
    if max_people <= 0:
        return []

    selected: list[dict[str, Any]] = []
    if world_event == "illness":
        selected.extend(_select_vulnerable_people(state, max_people))
    elif world_event == "dispute":
        rivals = _find_rival_pair(state)
        if rivals:
            selected.extend(rivals)
        selected.extend(_lowest_stat_people(state, "morale", max_people))
    elif world_event == "discovery":
        selected.extend(
            _select_people_by_role(
                state,
                ("scout", "forager"),
                max_people,
                day=state.get("day", 0),
            )
        )
    elif world_event == "wolf_attack":
        selected.extend(
            _select_people_by_role(
                state,
                ("guard", "scout", "builder"),
                max_people,
                day=state.get("day", 0),
            )
        )
    elif world_event == "storm":
        selected.extend(_select_vulnerable_people(state, max_people))
    elif world_event == "poor_harvest":
        selected.extend(_hungriest_people(state, max_people))
    elif world_event == "good_harvest":
        selected.extend(
            _select_people_by_role(
                state,
                ("farmer", "forager", "cook"),
                max_people,
                day=state.get("day", 0),
            )
        )
    else:
        selected.extend(_people_with_recent_story(state, max_people))
        selected.extend(_select_vulnerable_people(state, max(1, max_people // 2)))

    selected.extend(_role_representatives(state))
    return _dedupe_people(selected)[:max_people]


def _person_prompt_summary(person: dict[str, Any]) -> dict[str, Any]:
    personality = person.get("personality", {})
    status = person.get("status", {})
    story_notes = person.get("story", {}).get("notable_events", [])
    relationships = person.get("relationships", {})
    return {
        "id": person.get("id"),
        "name": person.get("name"),
        "age": person.get("age"),
        "role": person.get("role"),
        "traits": personality.get("traits", [])[:3],
        "temperament": personality.get("temperament"),
        "fear": personality.get("fear"),
        "desire": personality.get("desire"),
        "status": {
            "health": status.get("health"),
            "morale": status.get("morale"),
            "hunger": status.get("hunger"),
        },
        "relationship_counts": {
            "friends": len(relationships.get("friends", [])),
            "family": len(relationships.get("family", [])),
            "rivals": len(relationships.get("rivals", [])),
        },
        "recent_story": story_notes[-2:],
    }


def _role_counts(people: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for person in people:
        role = person.get("role", "unknown")
        counts[role] = counts.get(role, 0) + 1

    return dict(sorted(counts.items()))


def _status_summary_for_prompt(people: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "average_health": _average_living_stat(people, "health"),
        "average_morale": _average_living_stat(people, "morale"),
        "sick_or_fragile_count": sum(
            1 for person in people if person.get("status", {}).get("health", 0) <= 3
        ),
        "low_morale_count": sum(
            1 for person in people if person.get("status", {}).get("morale", 0) <= 3
        ),
        "hungry_count": sum(
            1 for person in people if person.get("status", {}).get("hunger", 0) >= 3
        ),
        "rivalry_count": sum(
            len(person.get("relationships", {}).get("rivals", []))
            for person in people
        )
        // 2,
    }


def _character_selection_note(world_event: str | None) -> str:
    if world_event:
        return (
            "Featured colonists are selected for relevance to "
            f"the {world_event} event and current colony risks."
        )

    return "Featured colonists emphasize current vulnerabilities and recent stories."


def _lowest_stat_people(
    state: dict[str, Any],
    stat: str,
    count: int,
) -> list[dict[str, Any]]:
    return sorted(
        living_people(state),
        key=lambda person: (
            person.get("status", {}).get(stat, 0),
            person["id"],
        ),
    )[:count]


def _hungriest_people(state: dict[str, Any], count: int) -> list[dict[str, Any]]:
    return sorted(
        living_people(state),
        key=lambda person: (
            -person.get("status", {}).get("hunger", 0),
            person.get("status", {}).get("health", 5),
            person["id"],
        ),
    )[:count]


def _people_with_recent_story(
    state: dict[str, Any],
    count: int,
) -> list[dict[str, Any]]:
    return [
        person
        for person in living_people(state)
        if person.get("story", {}).get("notable_events")
    ][-count:]


def _role_representatives(state: dict[str, Any]) -> list[dict[str, Any]]:
    representatives = []
    seen_roles = set()
    for person in living_people(state):
        role = person.get("role")
        if role not in seen_roles:
            representatives.append(person)
            seen_roles.add(role)

    return representatives


def _dedupe_people(people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen_ids = set()
    for person in people:
        person_id = person.get("id")
        if person_id not in seen_ids:
            deduped.append(person)
            seen_ids.add(person_id)

    return deduped


def _apply_world_event_to_people(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    world_event: str,
    day: int,
    event_details: dict[str, Any],
    discovery_detail: str | None,
) -> None:
    if world_event == "illness":
        _apply_illness_to_people(state, people_events=people_events, day=day)
        return

    if world_event == "dispute":
        _apply_dispute_to_people(state, people_events=people_events, day=day)
        return

    if world_event == "discovery":
        _apply_discovery_to_people(
            state,
            people_events=people_events,
            day=day,
            detail=discovery_detail or "something useful beyond camp",
        )
        return

    if world_event == "storm":
        _apply_storm_to_people(
            state,
            people_events=people_events,
            day=day,
            severity=event_details.get("severity", 3),
        )
        return

    if world_event == "wolf_attack":
        _apply_wolf_attack_to_people(
            state,
            people_events=people_events,
            day=day,
            severity=event_details.get("severity", 3),
        )
        return

    if world_event == "good_harvest":
        _record_role_work(
            state,
            people_events=people_events,
            day=day,
            roles=("farmer", "forager"),
            action_type="harvest",
            count=2,
            health_delta=0,
            morale_delta=1,
            note_template="{name} helped bring in the strong harvest on day {day}.",
            summary_template="{names} helped bring in the strong harvest.",
        )
        return

    if world_event == "poor_harvest":
        _record_group_status_shift(
            state,
            people_events=people_events,
            day=day,
            action_type="strained_by_harvest",
            count=3,
            health_delta=0,
            morale_delta=-1,
            hunger_delta=1,
            note_template="{name} felt the poor harvest's strain on day {day}.",
            summary_template="{names} felt the poor harvest most sharply.",
        )
        return

    if world_event == "chaos_gods":
        _record_group_status_shift(
            state,
            people_events=people_events,
            day=day,
            action_type="shaken_by_chaos",
            count=3,
            health_delta=-1,
            morale_delta=-1,
            hunger_delta=0,
            note_template="{name} was shaken when the oracle went silent on day {day}.",
            summary_template="{names} were shaken by the silence of the oracle.",
        )


def _apply_leadership_action_to_people(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    leadership_action: str,
    day: int,
) -> None:
    if leadership_action == "ration_food":
        _record_group_status_shift(
            state,
            people_events=people_events,
            day=day,
            action_type="rationed_food",
            count=4,
            health_delta=0,
            morale_delta=-1,
            hunger_delta=1,
            note_template="{name} endured tighter rations on day {day}.",
            summary_template="{names} felt the tighter rations first.",
        )
        return

    if leadership_action == "gather_wood":
        _record_role_work(
            state,
            people_events=people_events,
            day=day,
            roles=("woodcutter", "carpenter"),
            action_type="gathered_wood",
            count=2,
            health_delta=0,
            morale_delta=0,
            note_template="{name} joined the wood crews on day {day}.",
            summary_template="{names} joined the wood crews.",
        )
        return

    if leadership_action == "expand_fields":
        _record_role_work(
            state,
            people_events=people_events,
            day=day,
            roles=("farmer", "forager"),
            action_type="expanded_fields",
            count=2,
            health_delta=0,
            morale_delta=0,
            note_template="{name} worked the field expansion on day {day}.",
            summary_template="{names} worked the field expansion.",
        )
        return

    if leadership_action == "strengthen_defenses":
        _record_role_work(
            state,
            people_events=people_events,
            day=day,
            roles=("guard", "builder", "carpenter"),
            action_type="strengthened_defenses",
            count=2,
            health_delta=0,
            morale_delta=1,
            note_template="{name} helped strengthen the settlement on day {day}.",
            summary_template="{names} helped strengthen the settlement.",
        )
        return

    if leadership_action == "tend_the_sick":
        _apply_tend_the_sick_to_people(state, people_events=people_events, day=day)
        return

    if leadership_action == "mediate_dispute":
        _apply_mediation_to_people(state, people_events=people_events, day=day)
        return

    if leadership_action == "send_scouts":
        _record_role_work(
            state,
            people_events=people_events,
            day=day,
            roles=("scout", "forager"),
            action_type="sent_scouts",
            count=2,
            health_delta=0,
            morale_delta=1,
            note_template="{name} scouted beyond the settlement on day {day}.",
            summary_template="{names} scouted beyond the settlement.",
        )
        return

    if leadership_action == "hold_festival":
        _record_group_status_shift(
            state,
            people_events=people_events,
            day=day,
            action_type="festival",
            count=5,
            health_delta=0,
            morale_delta=2,
            hunger_delta=0,
            note_template="{name} found a little relief at the festival on day {day}.",
            summary_template="{names} found a little relief at the festival.",
        )


def _apply_illness_to_people(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    day: int,
) -> None:
    sick_people = _select_vulnerable_people(
        state,
        max(1, min(4, (living_population(state) + 24) // 25)),
    )
    if not sick_people:
        return

    for person in sick_people:
        _change_status(person, health_delta=-2, morale_delta=-1)
        _add_story_note(person, f"{person['name']} fell ill on day {day}.")

    people_events["illnesses"].append(
        {
            "type": "illness",
            "people": _people_refs(sick_people),
            "summary": f"{_join_names([person['name'] for person in sick_people])} fell ill.",
        }
    )


def _apply_dispute_to_people(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    day: int,
) -> None:
    disputants = _select_living_people(state, 2, day=day)
    if len(disputants) < 2:
        return

    first, second = disputants
    _add_relationship(first, "rivals", second["id"])
    _add_relationship(second, "rivals", first["id"])
    _change_status(first, morale_delta=-1)
    _change_status(second, morale_delta=-1)
    _add_story_note(first, f"{first['name']} argued with {second['name']} on day {day}.")
    _add_story_note(second, f"{second['name']} argued with {first['name']} on day {day}.")

    people_events["conflicts"].append(
        {
            "type": "dispute",
            "people": _people_refs(disputants),
            "summary": f"{first['name']} and {second['name']} became rivals.",
        }
    )


def _apply_discovery_to_people(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    day: int,
    detail: str,
) -> None:
    discoverers = _select_people_by_role(state, ("scout", "forager"), 1, day=day)
    if not discoverers:
        return

    discoverer = discoverers[0]
    _change_status(discoverer, morale_delta=1)
    _add_story_note(discoverer, f"{discoverer['name']} discovered {detail} on day {day}.")
    people_events["discoveries"].append(
        {
            "type": "discovery",
            "detail": detail,
            "people": _people_refs(discoverers),
            "summary": f"{discoverer['name']} discovered {detail}.",
        }
    )


def _apply_storm_to_people(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    day: int,
    severity: int,
) -> None:
    severity = max(1, min(5, severity))
    affected_people = _select_vulnerable_people(state, max(1, min(5, severity)))
    if not affected_people:
        return

    health_delta = -1 if severity >= 3 else 0
    morale_delta = -1 if severity >= 2 else 0
    hunger_delta = 1 if severity >= 4 else 0
    for person in affected_people:
        _change_status(
            person,
            health_delta=health_delta,
            morale_delta=morale_delta,
            hunger_delta=hunger_delta,
        )
        _add_story_note(
            person,
            f"{person['name']} endured a severity {severity} storm on day {day}.",
        )

    people_events["actions"].append(
        {
            "type": "weathered_storm",
            "severity": severity,
            "people": _people_refs(affected_people),
            "summary": (
                f"{_join_names([person['name'] for person in affected_people])} "
                f"bore the worst of the storm."
            ),
        }
    )


def _apply_wolf_attack_to_people(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    day: int,
    severity: int,
) -> None:
    severity = max(1, min(5, severity))
    defenders = _select_people_by_role(
        state,
        ("guard", "scout", "builder"),
        max(1, min(5, severity)),
        day=day,
    )
    if not defenders:
        return

    health_delta = -1 if severity >= 3 else 0
    morale_delta = -1 if severity >= 2 else 0
    for person in defenders:
        _change_status(person, health_delta=health_delta, morale_delta=morale_delta)
        _add_story_note(
            person,
            f"{person['name']} faced a severity {severity} wolf attack on day {day}.",
        )

    people_events["actions"].append(
        {
            "type": "defended_wolf_attack",
            "severity": severity,
            "people": _people_refs(defenders),
            "summary": (
                f"{_join_names([person['name'] for person in defenders])} "
                f"met the wolf attack at the edge of camp."
            ),
        }
    )


def _apply_tend_the_sick_to_people(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    day: int,
) -> None:
    patients = _select_vulnerable_people(
        state,
        max(3, min(6, (living_population(state) + 24) // 25)),
    )
    if not patients:
        return

    for person in patients:
        _change_status(person, health_delta=2, morale_delta=1)
        _add_story_note(person, f"{person['name']} received care from the sick ward on day {day}.")

    people_events["actions"].append(
        {
            "type": "tended_the_sick",
            "people": _people_refs(patients),
            "summary": f"{_join_names([person['name'] for person in patients])} received care.",
        }
    )


def _apply_mediation_to_people(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    day: int,
) -> None:
    rivals = _find_rival_pair(state)
    if not rivals:
        _record_group_status_shift(
            state,
            people_events=people_events,
            day=day,
            action_type="mediated_tensions",
            count=2,
            health_delta=0,
            morale_delta=1,
            hunger_delta=0,
            note_template="{name} joined the mediation circle on day {day}.",
            summary_template="{names} joined the mediation circle.",
        )
        return

    first, second = rivals
    _remove_relationship(first, "rivals", second["id"])
    _remove_relationship(second, "rivals", first["id"])
    _change_status(first, morale_delta=1)
    _change_status(second, morale_delta=1)
    _add_story_note(first, f"{first['name']} reconciled with {second['name']} on day {day}.")
    _add_story_note(second, f"{second['name']} reconciled with {first['name']} on day {day}.")

    people_events["actions"].append(
        {
            "type": "mediated_dispute",
            "people": _people_refs([first, second]),
            "summary": f"{first['name']} and {second['name']} stepped back from rivalry.",
        }
    )


def _record_role_work(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    day: int,
    roles: tuple[str, ...],
    action_type: str,
    count: int,
    health_delta: int,
    morale_delta: int,
    note_template: str,
    summary_template: str,
) -> None:
    workers = _select_people_by_role(state, roles, count, day=day)
    if not workers:
        return

    for person in workers:
        _change_status(person, health_delta=health_delta, morale_delta=morale_delta)
        _add_story_note(person, note_template.format(name=person["name"], day=day))

    names = _join_names([person["name"] for person in workers])
    people_events["actions"].append(
        {
            "type": action_type,
            "people": _people_refs(workers),
            "summary": summary_template.format(names=names),
        }
    )


def _record_group_status_shift(
    state: dict[str, Any],
    *,
    people_events: dict[str, list[dict[str, Any]]],
    day: int,
    action_type: str,
    count: int,
    health_delta: int,
    morale_delta: int,
    hunger_delta: int,
    note_template: str,
    summary_template: str,
) -> None:
    people = _select_living_people(state, count, day=day)
    if not people:
        return

    for person in people:
        _change_status(
            person,
            health_delta=health_delta,
            morale_delta=morale_delta,
            hunger_delta=hunger_delta,
        )
        _add_story_note(person, note_template.format(name=person["name"], day=day))

    names = _join_names([person["name"] for person in people])
    people_events["actions"].append(
        {
            "type": action_type,
            "people": _people_refs(people),
            "summary": summary_template.format(names=names),
        }
    )


def _select_people_by_role(
    state: dict[str, Any],
    roles: tuple[str, ...],
    count: int,
    *,
    day: int,
) -> list[dict[str, Any]]:
    role_matches = [
        person
        for person in _rotated_living_people(state, day)
        if person.get("role") in roles
    ]
    selected = role_matches[:count]
    selected_ids = {person["id"] for person in selected}

    if len(selected) < count:
        selected.extend(
            person
            for person in _rotated_living_people(state, day)
            if person["id"] not in selected_ids
        )

    return selected[:count]


def _select_living_people(
    state: dict[str, Any],
    count: int,
    *,
    day: int,
) -> list[dict[str, Any]]:
    return _rotated_living_people(state, day)[:count]


def _select_vulnerable_people(
    state: dict[str, Any],
    count: int,
) -> list[dict[str, Any]]:
    return sorted(
        living_people(state),
        key=lambda person: (
            person.get("status", {}).get("health", 5),
            -person.get("status", {}).get("hunger", 0),
            -person.get("age", 0),
            person["id"],
        ),
    )[:count]


def _rotated_living_people(state: dict[str, Any], day: int) -> list[dict[str, Any]]:
    people = living_people(state)
    if not people:
        return []

    offset = day % len(people)
    return people[offset:] + people[:offset]


def _find_rival_pair(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    people_by_id = {person["id"]: person for person in living_people(state)}
    for person in living_people(state):
        for rival_id in person.get("relationships", {}).get("rivals", []):
            rival = people_by_id.get(rival_id)
            if rival:
                return person, rival

    return None


def _people_refs(people: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "id": person["id"],
            "name": person["name"],
        }
        for person in people
    ]


def _change_status(
    person: dict[str, Any],
    *,
    health_delta: int = 0,
    morale_delta: int = 0,
    hunger_delta: int = 0,
) -> None:
    status = person.setdefault("status", {})
    if "health" in status:
        status["health"] = max(1, min(10, status["health"] + health_delta))
    if "morale" in status:
        status["morale"] = max(0, min(10, status["morale"] + morale_delta))
    if "hunger" in status:
        status["hunger"] = max(0, min(10, status["hunger"] + hunger_delta))


def _add_story_note(person: dict[str, Any], note: str) -> None:
    person.setdefault("story", {}).setdefault("notable_events", []).append(note)


def _add_relationship(person: dict[str, Any], relationship_type: str, person_id: str) -> None:
    relationships = person.setdefault("relationships", {})
    related_ids = relationships.setdefault(relationship_type, [])
    if person_id not in related_ids:
        related_ids.append(person_id)


def _remove_relationship(
    person: dict[str, Any],
    relationship_type: str,
    person_id: str,
) -> None:
    related_ids = person.setdefault("relationships", {}).setdefault(relationship_type, [])
    if person_id in related_ids:
        related_ids.remove(person_id)


def _join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]

    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _missed_rations_summary(people: list[dict[str, Any]]) -> str:
    names = [person["name"] for person in people]
    if len(names) <= 4:
        return f"{_join_names(names)} went without full rations."

    shown_names = _join_names(names[:3])
    remaining = len(names) - 3
    return f"{shown_names}, and {remaining} others went without full rations."


def _mark_person_dead(person: dict[str, Any], *, day: int, cause: str) -> dict[str, str]:
    person["status"]["alive"] = False
    person["status"]["health"] = 0

    note = _death_note(person["name"], day, cause)
    person.setdefault("story", {}).setdefault("notable_events", []).append(note)
    return {
        "id": person["id"],
        "name": person["name"],
        "cause": cause,
        "summary": note,
    }


def _death_note(name: str, day: int, cause: str) -> str:
    if cause == "starvation":
        return f"{name} died of starvation on day {day}."

    if cause == "illness":
        return f"{name} died during an illness on day {day}."

    if cause == "wolf_attack":
        return f"{name} died during a wolf attack on day {day}."

    if cause == "storm":
        return f"{name} died during a storm on day {day}."

    return f"{name} died during colony hardship on day {day}."

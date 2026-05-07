"""Narrative text for daily colony history."""

from __future__ import annotations

from typing import Any

EVENT_OPENINGS = {
    "good_harvest": "A good harvest lifted the colony's spirits",
    "poor_harvest": "A poor harvest strained the colony's stores",
    "illness": "Illness moved through the colony",
    "dispute": "A dispute unsettled the day's work",
    "discovery": "A discovery gave the colony something new to discuss",
    "storm": "A storm tested the colony",
    "wolf_attack": "Wolves came against the colony",
    "undead_rising": "The dead rose against the colony",
    "quiet_day": "No major world event overtook Blergen",
    "chaos_gods": "The chaos gods struck the colony",
    "empty_colony": "No colonists remained in Blergen",
}

ACTION_PHRASES = {
    "preserve_resources": "{president} told the colonists to preserve resources",
    "ration_food": "{president} ordered tighter food rationing",
    "gather_wood": "{president} sent crews out to gather wood",
    "expand_fields": "{president} directed labor toward the fields",
    "strengthen_defenses": "{president} spent wood to strengthen the settlement",
    "failed_strengthen_defenses": (
        "{president} tried to strengthen the settlement, but there was not enough wood"
    ),
    "tend_the_sick": "{president} organized care for the sick",
    "mediate_dispute": "{president} worked to mediate the tension",
    "send_scouts": "{president} sent scouts beyond the settlement",
    "hold_festival": "{president} called a festival to steady morale",
    "fight_undead": "{president} ordered the undead destroyed",
    "contain_undead": "{president} ordered the undead contained",
    "no_action": "no one remained to give orders or carry them out",
}


def write_daily_entry(
    state_before: dict[str, Any],
    event_record: dict[str, Any],
    state_after: dict[str, Any],
) -> str:
    """Return one restrained paragraph for history.md."""
    colony_name = state_before["colony_name"]
    day = event_record["day"]
    date_text = _date_text(event_record.get("date"))
    world_event = event_record["world_event"]
    leadership_action = event_record["leadership_action"]
    effects_text = _describe_effects(event_record["effects"])
    company_text = _describe_company_interventions(
        event_record.get("company_interventions", [])
    )

    weather_text = _weather_text(event_record.get("weather"))
    if state_before["population"] <= 0:
        body = _empty_colony_body(weather_text, effects_text)
        if company_text:
            body = f"{company_text} {body}"
        closing = _closing_sentence(state_after)
        return f"Day {day}{date_text} - {colony_name}:\n{body} {closing}\n"

    body = (
        f"{_event_opening(world_event, event_record.get('event_details', {}))}, and "
        f"{_action_phrase(leadership_action, event_record)}"
    )
    if weather_text:
        body = f"{weather_text} {body}"

    if effects_text:
        body = f"{body}; the day's changes {effects_text}."
    else:
        body = f"{body}."

    people_text = _describe_people_events(event_record.get("people_events", {}))
    if people_text:
        body = f"{body} {people_text}"

    if company_text:
        body = f"{company_text} {body}"

    closing = _closing_sentence(state_after)
    return f"Day {day}{date_text} - {colony_name}:\n{body} {closing}\n"


def write_personal_history_entry(
    state_before: dict[str, Any],
    event_record: dict[str, Any],
    state_after: dict[str, Any],
) -> str:
    """Return a character-focused markdown entry for people_history.md."""
    lines = _personal_history_lines(
        state_before=state_before,
        event_record=event_record,
        state_after=state_after,
    )
    if not lines:
        return ""

    day = event_record["day"]
    colony_name = state_before["colony_name"]
    body = "\n".join(f"- {line}" for line in lines)
    return f"Day {day} - {colony_name} Personal Stories:\n{body}\n"


def _describe_effects(effects: dict[str, int]) -> str:
    if not effects:
        return ""

    pieces = []
    for stat, amount in effects.items():
        direction = "increased" if amount > 0 else "reduced"
        pieces.append(f"{direction} {stat} by {abs(amount)}")

    if len(pieces) == 1:
        return pieces[0]

    return ", ".join(pieces[:-1]) + f", and {pieces[-1]}"


def _describe_people_events(people_events: dict[str, Any]) -> str:
    pieces = []
    for event_type in ("illnesses", "conflicts", "discoveries", "actions"):
        pieces.extend(
            event["summary"]
            for event in people_events.get(event_type, [])[:2]
            if event.get("summary")
        )

    deaths = people_events.get("deaths", [])
    if deaths:
        names = [death["name"] for death in deaths]
        if len(names) == 1:
            pieces.append(f"{names[0]} died.")
        elif len(names) <= 3:
            pieces.append(f"{_join_names(names)} died.")
        else:
            shown_names = _join_names(names[:3])
            remaining = len(names) - 3
            pieces.append(f"{shown_names}, and {remaining} others died.")

    return " ".join(pieces)


def _describe_company_interventions(interventions: list[dict[str, Any]]) -> str:
    summaries = [
        intervention["summary"]
        for intervention in interventions
        if intervention.get("summary")
    ]
    return " ".join(summaries)


def _action_phrase(leadership_action: str, event_record: dict[str, Any]) -> str:
    template = ACTION_PHRASES[leadership_action]
    return template.format(president=_president_name(event_record))


def _president_name(event_record: dict[str, Any]) -> str:
    president = event_record.get("president") or {}
    return president.get("name") or "the president"


def _empty_colony_body(weather_text: str, effects_text: str) -> str:
    weather_prefix = f"{weather_text} " if weather_text else ""
    body = (
        f"{weather_prefix}No colonists remained to give orders, work the fields, "
        "or answer the day's dangers"
    )
    if effects_text:
        return f"{body}; the abandoned settlement's state {effects_text}."

    return f"{body}."


def _personal_history_lines(
    *,
    state_before: dict[str, Any],
    event_record: dict[str, Any],
    state_after: dict[str, Any],
) -> list[str]:
    people_events = event_record.get("people_events", {})
    lines = []

    for illness in people_events.get("illnesses", []):
        for person_ref in illness.get("people", []):
            lines.append(
                _personal_line(
                    person_ref,
                    state_before=state_before,
                    state_after=state_after,
                    event_summary="fell ill",
                )
            )

    for conflict in people_events.get("conflicts", []):
        people = conflict.get("people", [])
        if len(people) >= 2:
            first, second = people[:2]
            lines.append(
                _relationship_line(
                    first,
                    second,
                    state_before=state_before,
                    state_after=state_after,
                    event_summary="became rivals",
                )
            )

    for discovery in people_events.get("discoveries", []):
        detail = discovery.get("detail", "something useful")
        for person_ref in discovery.get("people", []):
            lines.append(
                _personal_line(
                    person_ref,
                    state_before=state_before,
                    state_after=state_after,
                    event_summary=f"discovered {detail}",
                )
            )

    for action in people_events.get("actions", []):
        action_summary = _action_history_summary(action.get("type", "acted"))
        for person_ref in action.get("people", []):
            lines.append(
                _personal_line(
                    person_ref,
                    state_before=state_before,
                    state_after=state_after,
                    event_summary=action_summary,
                )
            )

    for death in people_events.get("deaths", []):
        lines.append(
            _personal_line(
                death,
                state_before=state_before,
                state_after=state_after,
                event_summary=f"died of {_cause_phrase(death.get('cause', 'hardship'))}",
            )
        )

    return lines


def _personal_line(
    person_ref: dict[str, Any],
    *,
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    event_summary: str,
) -> str:
    person_after = _person_by_id(state_after, person_ref["id"])
    person_before = _person_by_id(state_before, person_ref["id"])
    name = person_ref["name"]
    role = person_after.get("role") or person_before.get("role") or "colonist"
    status = _status_change_text(person_before, person_after)
    return f"{name} ({role}) {event_summary}. {status}"


def _relationship_line(
    first_ref: dict[str, Any],
    second_ref: dict[str, Any],
    *,
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    event_summary: str,
) -> str:
    first_after = _person_by_id(state_after, first_ref["id"])
    second_after = _person_by_id(state_after, second_ref["id"])
    first_role = first_after.get("role", "colonist")
    second_role = second_after.get("role", "colonist")
    first_status = _status_change_text(
        _person_by_id(state_before, first_ref["id"]),
        first_after,
    )
    second_status = _status_change_text(
        _person_by_id(state_before, second_ref["id"]),
        second_after,
    )
    return (
        f"{first_ref['name']} ({first_role}) and "
        f"{second_ref['name']} ({second_role}) {event_summary}. "
        f"{first_ref['name']}: {first_status} "
        f"{second_ref['name']}: {second_status}"
    )


def _status_change_text(
    person_before: dict[str, Any],
    person_after: dict[str, Any],
) -> str:
    before_status = person_before.get("status", {})
    after_status = person_after.get("status", {})
    pieces = []
    for stat in ("health", "morale", "hunger"):
        before_value = before_status.get(stat)
        after_value = after_status.get(stat)
        if before_value is None or after_value is None:
            continue
        if before_value != after_value:
            pieces.append(f"{stat} {before_value}->{after_value}")

    alive_before = before_status.get("alive")
    alive_after = after_status.get("alive")
    if alive_before is True and alive_after is False:
        pieces.append("died")

    if pieces:
        return "; ".join(pieces) + "."

    return "Status unchanged."


def _action_history_summary(action_type: str) -> str:
    summaries = {
        "harvest": "helped bring in the harvest",
        "strained_by_harvest": "felt the harvest strain",
        "shaken_by_chaos": "was shaken by the silent oracle",
        "weathered_storm": "bore the worst of the storm",
        "defended_wolf_attack": "defended the camp from wolves",
        "undead_rose": "rose as undead",
        "undead_destroyed": "was destroyed as undead",
        "undead_contained": "was contained as undead",
        "rationed_food": "endured tighter rations",
        "gathered_wood": "joined the wood crews",
        "expanded_fields": "worked the field expansion",
        "strengthened_defenses": "helped strengthen the settlement",
        "tended_the_sick": "received care",
        "mediated_dispute": "stepped back from rivalry",
        "mediated_tensions": "joined the mediation circle",
        "sent_scouts": "scouted beyond the settlement",
        "festival": "found relief at the festival",
        "missed_rations": "went without a full ration",
    }
    return summaries.get(action_type, "took part in the day's work")


def _event_opening(world_event: str, event_details: dict[str, Any]) -> str:
    if world_event == "storm":
        return f"A severity {event_details.get('severity', 3)} storm tested the colony"

    if world_event == "wolf_attack":
        return f"A severity {event_details.get('severity', 3)} wolf attack hit the colony"

    if world_event == "undead_rising":
        return f"A severity {event_details.get('severity', 3)} undead rising threatened the colony"

    return EVENT_OPENINGS[world_event]


def _date_text(date: dict[str, Any] | None) -> str:
    if not date:
        return ""

    if "year" in date:
        return f" (Year {date['year']}, {date['month']} {date['day_of_month']})"

    return f" ({date['month']} {date['day_of_month']})"


def _weather_text(weather: dict[str, Any] | None) -> str:
    if not weather:
        return ""

    return f"{weather['summary']}"


def _cause_phrase(cause: str) -> str:
    return cause.replace("_", " ")


def _person_by_id(state: dict[str, Any], person_id: str) -> dict[str, Any]:
    for person in state.get("people", []):
        if person.get("id") == person_id:
            return person

    return {}


def _join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]

    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _closing_sentence(state: dict[str, Any]) -> str:
    if state["population"] <= 0:
        return "No colonists remain in Blergen."

    if state["population"] < 80:
        return "The loss of people is beginning to define the settlement's future."

    if state["food"] <= 0:
        return "With the stores empty, hunger is now the colony's ruling fact."

    if state["food"] < 30:
        return "Hunger is becoming the settlement's most urgent worry."

    if state["health"] < 4:
        return "The settlement survives, but sickness is wearing people down."

    if state["morale"] < 4:
        return "The settlement survives, though confidence is thinning."

    return "The settlement endures into another morning."

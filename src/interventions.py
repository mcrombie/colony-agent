"""Blergen Company intervention helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.people import add_new_people

COMPANY_INTERVENTIONS_FIELD = "company_interventions"
COMPANY_NAME = "Blergen Company"

DEFAULT_SETTLER_COUNT = 100
DEFAULT_FOOD_AMOUNT = 100
DEFAULT_SUPPLY_WOOD = 50
DEFAULT_SUPPLY_SECURITY = 2


def apply_company_interventions(
    state: dict[str, Any],
    additional_interventions: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Consume queued Blergen Company interventions and return applied records."""
    updated = deepcopy(state)
    queued_interventions = updated.pop(COMPANY_INTERVENTIONS_FIELD, [])
    if additional_interventions:
        queued_interventions = [*queued_interventions, *additional_interventions]

    if not queued_interventions:
        return updated, []

    if not isinstance(queued_interventions, list):
        raise ValueError(f"{COMPANY_INTERVENTIONS_FIELD} must be a list")

    records = []
    for intervention in queued_interventions:
        records.append(_apply_one_intervention(updated, _normalize_intervention(intervention)))

    return updated, records


def _normalize_intervention(intervention: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(intervention, str):
        return {"type": intervention}

    return deepcopy(intervention)


def _apply_one_intervention(
    state: dict[str, Any],
    intervention: dict[str, Any],
) -> dict[str, Any]:
    intervention_type = intervention.get("type")

    if intervention_type == "send_settlers":
        count = _non_negative_int(intervention.get("count"), default=DEFAULT_SETTLER_COUNT)
        new_people = add_new_people(
            state,
            count,
            story_note="{name} arrived with a Blergen Company settler convoy.",
        )
        return {
            "type": intervention_type,
            "source": COMPANY_NAME,
            "effects": {"population": len(new_people)} if new_people else {},
            "summary": f"{COMPANY_NAME} sent {len(new_people)} new settlers to Blergen.",
        }

    if intervention_type == "send_food":
        amount = _non_negative_int(intervention.get("amount"), default=DEFAULT_FOOD_AMOUNT)
        state["food"] = state.get("food", 0) + amount
        return {
            "type": intervention_type,
            "source": COMPANY_NAME,
            "effects": {"food": amount} if amount else {},
            "summary": f"{COMPANY_NAME} sent {amount} food to Blergen.",
        }

    if intervention_type == "send_supplies":
        wood = _non_negative_int(intervention.get("wood"), default=DEFAULT_SUPPLY_WOOD)
        security = _non_negative_int(
            intervention.get("security"),
            default=DEFAULT_SUPPLY_SECURITY,
        )
        security_before = state.get("security", 0)
        state["wood"] = state.get("wood", 0) + wood
        state["security"] = max(0, min(10, security_before + security))
        effects = {}
        if wood:
            effects["wood"] = wood
        actual_security = state["security"] - security_before
        if actual_security:
            effects["security"] = actual_security

        return {
            "type": intervention_type,
            "source": COMPANY_NAME,
            "effects": effects,
            "summary": (
                f"{COMPANY_NAME} sent supplies to Blergen: "
                f"{wood} wood and {actual_security} security."
            ),
        }

    raise ValueError(f"Unknown Blergen Company intervention: {intervention_type}")


def _non_negative_int(value: Any, *, default: int) -> int:
    if value is None:
        return default

    return max(0, int(value))

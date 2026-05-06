"""Calendar and weather helpers for the colony simulation."""

from __future__ import annotations

from typing import Any

MONTHS = (
    ("January", 31),
    ("February", 28),
    ("March", 31),
    ("April", 30),
    ("May", 31),
    ("June", 30),
    ("July", 31),
    ("August", 31),
    ("September", 30),
    ("October", 31),
    ("November", 30),
    ("December", 31),
)

SEASON_BY_MONTH = {
    "December": "winter",
    "January": "winter",
    "February": "winter",
    "March": "spring",
    "April": "spring",
    "May": "spring",
    "June": "summer",
    "July": "summer",
    "August": "summer",
    "September": "autumn",
    "October": "autumn",
    "November": "autumn",
}

WEATHER_TABLES = {
    "winter": (
        ("clear_cold", 1),
        ("overcast", 1),
        ("snow", 2),
        ("hard_freeze", 3),
        ("snow", 2),
        ("clear_cold", 1),
        ("winter_storm", 4),
        ("sleet", 3),
        ("overcast", 1),
        ("winter_storm", 5),
    ),
    "spring": (
        ("clear", 1),
        ("rain", 2),
        ("mud", 2),
        ("wind", 2),
        ("thunderstorm", 3),
        ("mild", 1),
        ("rain", 2),
        ("clear", 1),
    ),
    "summer": (
        ("clear", 1),
        ("hot", 2),
        ("dry_heat", 3),
        ("thunderstorm", 3),
        ("clear", 1),
        ("rain", 2),
        ("hot", 2),
        ("clear", 1),
    ),
    "autumn": (
        ("clear", 1),
        ("rain", 2),
        ("cold_rain", 3),
        ("wind", 2),
        ("early_frost", 3),
        ("overcast", 1),
        ("rain", 2),
        ("clear", 1),
    ),
}

WEATHER_SUMMARIES = {
    "clear": "Clear skies left the day's work mostly to the colony.",
    "clear_cold": "Cold clear air settled over the camp.",
    "overcast": "A gray sky pressed low over Blergen.",
    "snow": "Snow made paths and work crews slower.",
    "hard_freeze": "A hard freeze bit at stores, tools, and exposed hands.",
    "sleet": "Sleet made the paths slick and miserable.",
    "winter_storm": "A winter storm threatened the colony's shelters and stores.",
    "rain": "Rain softened the paths and soaked the outer work sites.",
    "mud": "Mud slowed carts, boots, and field work.",
    "wind": "Strong wind worried the roofs and watch posts.",
    "thunderstorm": "A thunderstorm rolled over the settlement.",
    "mild": "Mild weather gave the colony a little breathing room.",
    "hot": "Heat made the day's work tiring.",
    "dry_heat": "Dry heat pulled moisture from fields and people alike.",
    "cold_rain": "Cold rain left the settlement raw and tired.",
    "early_frost": "An early frost warned the fields to hurry.",
}


def date_for_day(day: int) -> dict[str, Any]:
    """Return the calendar date for a simulation day where day 1 is Jan 1."""
    if day < 1:
        raise ValueError("day must be at least 1")

    day_of_year = ((day - 1) % 365) + 1
    year = ((day - 1) // 365) + 1
    remaining = day_of_year
    for month_index, (month, days_in_month) in enumerate(MONTHS, start=1):
        if remaining <= days_in_month:
            return {
                "year": year,
                "day_of_year": day_of_year,
                "month": month,
                "month_number": month_index,
                "day_of_month": remaining,
                "season": SEASON_BY_MONTH[month],
            }
        remaining -= days_in_month

    raise RuntimeError("calendar calculation fell outside a 365-day year")


def weather_for_day(day: int) -> dict[str, Any]:
    """Return deterministic daily weather for the given simulation day."""
    date = date_for_day(day)
    season = date["season"]
    table = WEATHER_TABLES[season]
    condition, severity = table[((day * 7) + date["day_of_year"]) % len(table)]
    return {
        "season": season,
        "condition": condition,
        "severity": severity,
        "summary": WEATHER_SUMMARIES[condition],
    }


def environment_for_day(day: int) -> dict[str, Any]:
    """Return derived calendar and weather context for a simulation day."""
    return {
        "date": date_for_day(day),
        "weather": weather_for_day(day),
    }

from src.environment import (
    date_for_day,
    environment_for_day,
    sync_calendar_state,
    weather_for_day,
    year_for_day,
)


def test_day_one_is_january_first():
    date = date_for_day(1)

    assert date["month"] == "January"
    assert date["day_of_month"] == 1
    assert date["year"] == 1
    assert date["season"] == "winter"


def test_day_fifty_is_february_nineteenth():
    date = date_for_day(50)

    assert date["month"] == "February"
    assert date["day_of_month"] == 19
    assert date["year"] == 1
    assert date["season"] == "winter"


def test_year_starts_at_one_and_rolls_after_day_365():
    assert year_for_day(1) == 1
    assert year_for_day(365) == 1
    assert year_for_day(366) == 2
    assert date_for_day(366)["month"] == "January"
    assert date_for_day(366)["day_of_month"] == 1


def test_calendar_state_tracks_year_from_day():
    state = {"day": 366, "year": 99}

    synced = sync_calendar_state(state)

    assert synced["year"] == 2


def test_weather_is_deterministic_and_seasonal():
    weather = weather_for_day(50)

    assert weather == weather_for_day(50)
    assert weather["season"] == "winter"
    assert 1 <= weather["severity"] <= 5
    assert weather["summary"]


def test_environment_includes_date_and_weather():
    environment = environment_for_day(50)

    assert environment["date"]["month"] == "February"
    assert environment["weather"]["season"] == "winter"

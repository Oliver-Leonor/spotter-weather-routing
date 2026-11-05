"""Scripted demo weather: deterministic, complete, and clearly not a forecast."""

from datetime import UTC, datetime

from weather.scenario import ScenarioWeatherProvider

DAY = datetime(2026, 11, 6, tzinfo=UTC)
I70_CENTRAL_KANSAS = (38.87, -98.5)
US36_NORTHERN_KANSAS = (39.8, -96.8)


def series_for(point, start_hour=0, end_hour=47):
    start = DAY.replace(hour=start_hour % 24, day=DAY.day + start_hour // 24)
    end = DAY.replace(hour=end_hour % 24, day=DAY.day + end_hour // 24)
    series = ScenarioWeatherProvider().fetch_hourly([point], start, end)
    return series[(round(point[0], 3), round(point[1], 3))]


def value_at(series, column: str, hour: int):
    index = series.nearest_index(DAY.replace(hour=hour).timestamp())
    return getattr(series, column)[index]


def test_same_place_and_time_always_get_the_same_weather():
    assert series_for(I70_CENTRAL_KANSAS) == series_for(I70_CENTRAL_KANSAS)


def test_series_covers_the_requested_window_on_whole_hours():
    start = datetime(2026, 11, 6, 15, 20, tzinfo=UTC)
    end = datetime(2026, 11, 6, 18, 10, tzinfo=UTC)
    series = ScenarioWeatherProvider().fetch_hourly([I70_CENTRAL_KANSAS], start, end)[
        (38.87, -98.5)
    ]
    hours = [datetime.fromtimestamp(t, UTC).strftime("%H:%M") for t in series.times]
    assert hours == ["15:00", "16:00", "17:00", "18:00", "19:00"]


def test_afternoon_storm_brings_severe_wind_and_heavy_snow_to_i70():
    series = series_for(I70_CENTRAL_KANSAS)
    assert 45 <= value_at(series, "wind_mph", 21) < 55  # Severe band, where the load rule applies
    assert value_at(series, "snow_in_per_hr", 21) >= 1.0


def test_storm_has_cleared_by_the_next_morning():
    series = series_for(I70_CENTRAL_KANSAS)
    assert value_at(series, "wind_mph", 9) < 25
    assert value_at(series, "snow_in_per_hr", 9) == 0.0
    assert value_at(series, "rain_in_per_hr", 9) == 0.0


def test_second_system_brings_high_wind_to_the_northern_route():
    series = series_for(US36_NORTHERN_KANSAS)
    # High band, where the 40,000 lb load rule applies.
    assert 35 <= value_at(series, "wind_mph", 23) < 45


def test_northern_route_is_clear_of_the_i70_storm():
    assert value_at(series_for(US36_NORTHERN_KANSAS), "wind_mph", 19) < 25


def test_weather_repeats_every_day_so_the_demo_is_repeatable():
    series = series_for(I70_CENTRAL_KANSAS)
    first_day, second_day = series.wind_mph[:24], series.wind_mph[24:48]
    assert first_day == second_day


def test_every_hour_has_complete_non_negative_measurements():
    series = series_for(I70_CENTRAL_KANSAS)
    for column in ("wind_mph", "wind_gust_mph", "rain_in_per_hr", "snow_in_per_hr"):
        values = getattr(series, column)
        assert len(values) == len(series.times) == 48
        assert all(value is not None and value >= 0 for value in values)


def test_timezone_follows_the_corridor():
    assert series_for((39.74, -104.99)).timezone == "America/Denver"
    assert series_for((39.1, -94.58)).timezone == "America/Chicago"

"""Forecast hour selection: nearest hour to the ETA, ties to the earlier hour (spec section 9)."""

from datetime import UTC, datetime, timedelta

import pytest

from weather.models import HourlySeries

FIRST_HOUR = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)


def make_series(hours: int = 5) -> HourlySeries:
    first = int(FIRST_HOUR.timestamp())
    return HourlySeries(
        times=tuple(first + 3600 * i for i in range(hours)),
        wind_mph=tuple(10.0 + i for i in range(hours)),
        wind_gust_mph=tuple(20.0 + i for i in range(hours)),
        rain_in_per_hr=tuple(0.01 * i for i in range(hours)),
        snow_in_per_hr=tuple(0.0 for _ in range(hours)),
        temperature_f=tuple(40.0 for _ in range(hours)),
        weather_code=tuple(3 for _ in range(hours)),
        timezone="America/Denver",
        utc_offset_seconds=-25200,
        fetched_at=FIRST_HOUR,
    )


def at(hour: int, minute: int = 0, second: int = 0) -> float:
    return (
        FIRST_HOUR.replace(hour=0) + timedelta(hours=hour, minutes=minute, seconds=second)
    ).timestamp()


@pytest.mark.parametrize(
    "eta, expected_index",
    [
        (at(15), 0),  # exactly on the hour
        (at(15, 29, 59), 0),  # nearer the earlier hour
        (at(15, 30), 0),  # exactly halfway: ties go to the earlier hour
        (at(15, 30, 1), 1),  # nearer the later hour
        (at(17, 45), 3),
        (at(19), 4),  # last hour in the series
    ],
)
def test_nearest_hour_is_selected(eta, expected_index):
    assert make_series().nearest_index(eta) == expected_index


@pytest.mark.parametrize(
    "eta, expected_index",
    [
        (at(14, 30), 0),  # 30 minutes before the first hour is still covered
        (at(14, 29, 59), None),  # more than 30 minutes before coverage starts
        (at(19, 30), 4),  # 30 minutes after the last hour is still covered
        (at(19, 30, 1), None),  # more than 30 minutes after coverage ends
        (at(23), None),
    ],
)
def test_eta_outside_forecast_coverage_has_no_forecast_hour(eta, expected_index):
    assert make_series().nearest_index(eta) == expected_index


def test_empty_series_has_no_forecast_hour():
    assert make_series(hours=0).nearest_index(at(15)) is None


def test_observation_reports_the_selected_hour_and_its_measurements():
    observation = make_series().observation(2)
    assert observation.forecast_time == datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
    assert (observation.wind_mph, observation.wind_gust_mph) == (12.0, 22.0)
    assert (observation.rain_in_per_hr, observation.snow_in_per_hr) == (0.02, 0.0)
    assert (observation.temperature_f, observation.weather_code) == (40.0, 3)

"""Open-Meteo forecast client: request, unit validation, batching, caching (HTTP mocked)."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from common.errors import UpstreamError
from risk.classification import classify_rain, classify_snow, classify_wind
from risk.levels import RiskLevel
from tests.helpers import open_meteo_location
from weather.open_meteo import OpenMeteoProvider

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
START = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
END = datetime(2026, 11, 7, 1, 0, tzinfo=UTC)
SERIES_START = datetime(2026, 11, 5, 7, 0, tzinfo=UTC)  # local midnight in Denver
DENVER = (39.73921, -104.99034)
KANSAS_CITY = (39.1, -94.579)


def locations(**location_kwargs):
    """Answer every request with one location object per requested coordinate."""

    def responder(request: httpx.Request) -> httpx.Response:
        count = len(request.url.params["latitude"].split(","))
        body = [open_meteo_location(SERIES_START, 96, **location_kwargs) for _ in range(count)]
        return httpx.Response(200, json=body if count > 1 else body[0])

    return responder


def fetch(points=(DENVER, KANSAS_CITY), start=START, end=END):
    return OpenMeteoProvider().fetch_hourly(points, start, end)


def test_series_are_keyed_by_the_requested_point_rounded_to_three_decimals(respx_mock):
    respx_mock.get(FORECAST_URL).mock(side_effect=locations(wind=12.34))

    series = fetch()

    assert set(series) == {(39.739, -104.99), (39.1, -94.579)}
    denver = series[(39.739, -104.99)]
    assert len(denver.times) == 96
    assert denver.times[0] == int(SERIES_START.timestamp())
    assert denver.wind_mph[0] == 12.34
    assert (denver.timezone, denver.utc_offset_seconds) == ("America/Denver", -25200)


def test_single_location_response_is_an_object_not_a_list(respx_mock):
    respx_mock.get(FORECAST_URL).mock(side_effect=locations(wind=7.0))
    assert fetch(points=[DENVER])[(39.739, -104.99)].wind_mph[0] == 7.0


def test_request_asks_for_imperial_units_utc_epochs_and_a_padded_date_window(respx_mock):
    route = respx_mock.get(FORECAST_URL).mock(side_effect=locations())

    fetch()

    assert dict(route.calls.last.request.url.params) == {
        "latitude": "39.739,39.100",
        "longitude": "-104.990,-94.579",
        "hourly": "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall,temperature_2m,weather_code",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "temperature_unit": "fahrenheit",
        "timeformat": "unixtime",
        "timezone": "auto",
        # One day of padding on each side: with timezone=auto the dates are local calendar days.
        "start_date": "2026-11-05",
        "end_date": "2026-11-08",
    }


def test_end_date_never_exceeds_the_forecast_horizon(respx_mock):
    route = respx_mock.get(FORECAST_URL).mock(side_effect=locations())
    now = datetime.now(UTC)

    fetch(start=now + timedelta(days=13), end=now + timedelta(days=20))

    horizon = (now.date() + timedelta(days=15)).isoformat()
    assert route.calls.last.request.url.params["end_date"] == horizon


def test_points_that_round_to_the_same_place_are_requested_once(respx_mock):
    route = respx_mock.get(FORECAST_URL).mock(side_effect=locations())

    series = fetch(points=[(39.73921, -104.99034), (39.73939, -104.98961)])

    assert route.calls.last.request.url.params["latitude"] == "39.739"
    assert list(series) == [(39.739, -104.99)]


def test_many_points_are_split_into_batches_of_fifty(respx_mock):
    route = respx_mock.get(FORECAST_URL).mock(side_effect=locations())
    points = [(30.0 + i * 0.1, -100.0) for i in range(120)]

    series = fetch(points=points)

    batch_sizes = sorted(
        len(call.request.url.params["latitude"].split(",")) for call in route.calls
    )
    assert batch_sizes == [20, 50, 50]
    assert len(series) == 120


def test_rain_rate_is_rain_plus_showers(respx_mock):
    respx_mock.get(FORECAST_URL).mock(side_effect=locations(rain=0.12, showers=0.2))
    assert fetch(points=[DENVER])[(39.739, -104.99)].rain_in_per_hr[0] == 0.32


def test_rain_rate_is_rounded_so_float_noise_cannot_cross_a_threshold(respx_mock):
    assert 0.01 + 0.09 < 0.10  # the raw float sum is 0.09999999999999999: Low, not Moderate
    respx_mock.get(FORECAST_URL).mock(side_effect=locations(rain=0.01, showers=0.09))

    rate = fetch(points=[DENVER])[(39.739, -104.99)].rain_in_per_hr[0]

    assert rate == 0.1
    assert classify_rain(rate) is RiskLevel.MODERATE


def test_snow_rate_is_the_hourly_snowfall(respx_mock):
    respx_mock.get(FORECAST_URL).mock(side_effect=locations(snowfall=1.25))
    assert fetch(points=[DENVER])[(39.739, -104.99)].snow_in_per_hr[0] == 1.25


def test_metric_units_are_converted_when_the_provider_ignores_the_requested_units(respx_mock):
    respx_mock.get(FORECAST_URL).mock(
        side_effect=locations(
            wind=100.0,
            gusts=50.0,
            rain=25.4,
            showers=0.0,
            snowfall=2.54,
            temperature=0.0,
            units={
                "wind_speed_10m": "km/h",
                "wind_gusts_10m": "km/h",
                "rain": "mm",
                "showers": "mm",
                "snowfall": "cm",
                "temperature_2m": "°C",
            },
        )
    )

    series = fetch(points=[DENVER])[(39.739, -104.99)]

    assert series.wind_mph[0] == pytest.approx(62.137, abs=0.001)
    assert series.wind_gust_mph[0] == pytest.approx(31.069, abs=0.001)
    assert series.rain_in_per_hr[0] == pytest.approx(1.0)
    assert series.snow_in_per_hr[0] == pytest.approx(1.0)
    assert series.temperature_f[0] == pytest.approx(32.0)


@pytest.mark.parametrize("variable", ["wind_speed_10m", "rain", "showers", "snowfall"])
def test_unrecognised_unit_on_a_risk_measurement_is_rejected(respx_mock, variable):
    respx_mock.get(FORECAST_URL).mock(side_effect=locations(units={variable: "furlongs"}))
    with pytest.raises(UpstreamError) as excinfo:
        fetch(points=[DENVER])
    assert (excinfo.value.status_code, excinfo.value.code) == (502, "WEATHER_UNAVAILABLE")


def test_unrecognised_unit_on_a_display_only_value_leaves_it_empty(respx_mock):
    respx_mock.get(FORECAST_URL).mock(
        side_effect=locations(wind=9.0, units={"wind_gusts_10m": "furlongs"})
    )
    series = fetch(points=[DENVER])[(39.739, -104.99)]
    assert series.wind_gust_mph[0] is None
    assert series.wind_mph[0] == 9.0


def test_missing_values_stay_missing_and_are_never_zero(respx_mock):
    respx_mock.get(FORECAST_URL).mock(
        side_effect=locations(wind=None, rain=0.1, showers=None, snowfall=None)
    )
    series = fetch(points=[DENVER])[(39.739, -104.99)]
    assert series.wind_mph[0] is None
    assert series.rain_in_per_hr[0] is None  # showers unknown, so the rain rate is unknown
    assert series.snow_in_per_hr[0] is None


def test_wrong_number_of_locations_in_the_response_is_rejected(respx_mock):
    respx_mock.get(FORECAST_URL).respond(json=open_meteo_location(SERIES_START, 96))
    with pytest.raises(UpstreamError) as excinfo:
        fetch()  # two points requested, one location returned
    assert excinfo.value.code == "WEATHER_UNAVAILABLE"


@pytest.mark.parametrize("status", [400, 500, 503])
def test_provider_failure_is_a_502(respx_mock, status):
    respx_mock.get(FORECAST_URL).respond(status, json={"error": True, "reason": "boom"})
    with pytest.raises(UpstreamError) as excinfo:
        fetch()
    assert (excinfo.value.status_code, excinfo.value.code) == (502, "WEATHER_UNAVAILABLE")
    assert excinfo.value.provider == "open-meteo"


def test_rate_limit_is_a_502_that_says_to_wait(respx_mock):
    respx_mock.get(FORECAST_URL).respond(429, json={"error": True, "reason": "limit exceeded"})
    with pytest.raises(UpstreamError) as excinfo:
        fetch()
    assert excinfo.value.status_code == 502
    assert "minute" in excinfo.value.message


def test_timeout_is_a_504(respx_mock):
    respx_mock.get(FORECAST_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(UpstreamError) as excinfo:
        fetch()
    assert (excinfo.value.status_code, excinfo.value.code) == (504, "WEATHER_TIMEOUT")


def test_repeat_request_is_served_from_the_cache(respx_mock):
    route = respx_mock.get(FORECAST_URL).mock(side_effect=locations())
    first = fetch()
    second = fetch()
    assert route.call_count == 1
    assert second == first


def test_only_points_missing_from_the_cache_are_requested(respx_mock):
    route = respx_mock.get(FORECAST_URL).mock(side_effect=locations())
    fetch(points=[DENVER])

    series = fetch(points=[DENVER, KANSAS_CITY])

    assert route.call_count == 2
    assert route.calls.last.request.url.params["latitude"] == "39.100"
    assert set(series) == {(39.739, -104.99), (39.1, -94.579)}


def test_a_different_window_is_not_served_from_the_cache(respx_mock):
    route = respx_mock.get(FORECAST_URL).mock(side_effect=locations())
    fetch(points=[DENVER])
    fetch(points=[DENVER], start=START + timedelta(days=3), end=END + timedelta(days=3))
    assert route.call_count == 2


# ------------------------------------------ precision at the thresholds ------
# Review finding (PR #2): rounding to three decimals before classification hid real threshold
# crossings when values arrive in metric units. 25.41 mm is 1.000394 in/h, which is No Travel.
def first_hour():
    return fetch(points=[DENVER])[(39.739, -104.99)]


@pytest.mark.parametrize(
    "rain_mm, showers_mm, level",
    [
        (25.4, 0.0, RiskLevel.SEVERE),  # exactly 1.00 in/h: "0.50 through 1.00" is Severe
        (25.41, 0.0, RiskLevel.NO_TRAVEL),  # 1.000394 in/h: above 1.00
        (12.7, 12.7, RiskLevel.SEVERE),  # the sum is exactly 1.00 in/h
        (12.7, 12.71, RiskLevel.NO_TRAVEL),  # the sum is 1.000394 in/h
    ],
)
def test_metric_rain_just_above_one_inch_per_hour_is_no_travel(
    respx_mock, rain_mm, showers_mm, level
):
    respx_mock.get(FORECAST_URL).mock(
        side_effect=locations(
            rain=rain_mm, showers=showers_mm, units={"rain": "mm", "showers": "mm"}
        )
    )
    assert classify_rain(first_hour().rain_in_per_hr[0]) is level


def test_metric_rain_of_exactly_one_inch_normalizes_to_one(respx_mock):
    assert 25.4 * (1 / 25.4) != 1.0  # the raw conversion is 0.9999999999999999
    respx_mock.get(FORECAST_URL).mock(
        side_effect=locations(rain=25.4, showers=0.0, units={"rain": "mm", "showers": "mm"})
    )
    assert first_hour().rain_in_per_hr[0] == 1.0


@pytest.mark.parametrize(
    "snow_cm, level",
    [
        (7.62, RiskLevel.SEVERE),  # exactly 3.0 in/h: "2.0 through 3.0" is Severe
        (7.63, RiskLevel.NO_TRAVEL),  # 3.003937 in/h: above 3.0
    ],
)
def test_metric_snow_just_above_three_inches_per_hour_is_no_travel(respx_mock, snow_cm, level):
    respx_mock.get(FORECAST_URL).mock(
        side_effect=locations(snowfall=snow_cm, units={"snowfall": "cm"})
    )
    assert classify_snow(first_hour().snow_in_per_hr[0]) is level


@pytest.mark.parametrize(
    "wind_kmh, level",
    [
        (88.5, RiskLevel.SEVERE),  # 54.991 mph
        (88.5139, RiskLevel.SEVERE),  # 54.99997 mph: still below 55, must not round up
        (88.6, RiskLevel.NO_TRAVEL),  # 55.054 mph
    ],
)
def test_metric_wind_is_not_rounded_across_the_55_mph_threshold(respx_mock, wind_kmh, level):
    respx_mock.get(FORECAST_URL).mock(
        side_effect=locations(wind=wind_kmh, units={"wind_speed_10m": "km/h"})
    )
    assert classify_wind(first_hour().wind_mph[0]) is level


@pytest.mark.parametrize(
    "rain_in, snow_in, rain_level, snow_level",
    [
        (1.0, 3.0, RiskLevel.SEVERE, RiskLevel.SEVERE),
        (1.0004, 3.0004, RiskLevel.NO_TRAVEL, RiskLevel.NO_TRAVEL),
    ],
)
def test_values_with_more_than_three_decimals_keep_their_precision(
    respx_mock, rain_in, snow_in, rain_level, snow_level
):
    respx_mock.get(FORECAST_URL).mock(side_effect=locations(rain=rain_in, snowfall=snow_in))
    series = first_hour()
    assert classify_rain(series.rain_in_per_hr[0]) is rain_level
    assert classify_snow(series.snow_in_per_hr[0]) is snow_level

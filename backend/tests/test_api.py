"""HTTP API: request validation, the response contract and provider failure mapping.

Live mode runs against mocked provider HTTP. Demo (fixture) mode needs no network at all, so it is
used wherever a test only cares about validation or the response shape.
"""

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from analysis.views import AnalyzeRateThrottle
from tests.helpers import meridian_line, open_meteo_location, valhalla_response, valhalla_trip

ANALYZE_URL = "/api/routes/analyze/"
GEOCODE_URL = "/api/geocode/"
VALHALLA_URL = "https://valhalla1.openstreetmap.de/route"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SEARCH_URL = "https://geocoding-api.open-meteo.com/v1/search"


@pytest.fixture
def client():
    return APIClient()


def tomorrow(hour: int = 15) -> datetime:
    return (datetime.now(UTC) + timedelta(days=1)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def trip(**overrides) -> dict:
    body = {
        "origin": {"lat": 39.0, "lon": -100.0, "label": "Start"},
        "destination": {"lat": 40.447, "lon": -100.0, "label": "End"},
        "departure_time": tomorrow().isoformat(),
        "load_weight_lb": 42_000,
        "checkpoint_interval_miles": 25,
    }
    body.update(overrides)
    return body


def demo(**overrides) -> dict:
    return trip(**{"mode": "fixture", **overrides})


def mock_routing(respx_mock):
    return respx_mock.post(VALHALLA_URL).respond(
        json=valhalla_response(
            valhalla_trip(meridian_line(100.0, points=21), seconds=7200.0, miles=100.1),
            valhalla_trip(meridian_line(110.0, points=23, lon=-99.5), seconds=9000.0, miles=110.2),
            valhalla_trip(meridian_line(125.0, points=26, lon=-99.0), seconds=10800.0, miles=125.3),
        )
    )


def mock_forecast(respx_mock, **weather):
    """Answer every forecast request with the same weather for each requested place and day."""

    def responder(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        first_day = date.fromisoformat(params["start_date"])
        days = (date.fromisoformat(params["end_date"]) - first_day).days + 1
        start = datetime(first_day.year, first_day.month, first_day.day, tzinfo=UTC)
        count = len(params["latitude"].split(","))
        body = [open_meteo_location(start, days * 24, **weather) for _ in range(count)]
        return httpx.Response(200, json=body if count > 1 else body[0])

    return respx_mock.get(FORECAST_URL).mock(side_effect=responder)


def error(response) -> dict:
    return response.json()["error"]


# -------------------------------------------------------------- live mode ------
def test_live_analysis_returns_three_routes_with_a_recommendation(client, respx_mock):
    routing = mock_routing(respx_mock)
    forecast = mock_forecast(respx_mock)

    response = client.post(ANALYZE_URL, trip(), format="json")

    assert response.status_code == 200
    body = response.json()
    assert body["provenance"]["mode"] == "live"
    assert [r["name"] for r in body["routes"]] == ["Route A", "Route B", "Route C"]
    assert [r["status"] for r in body["routes"]] == ["ok", "ok", "ok"]
    assert body["recommendation"]["route_id"] == "route-1"  # calm weather: the fastest route
    assert body["warnings"] == []
    assert routing.call_count == 1
    assert forecast.call_count >= 2  # checkpoints, then the heatmap grid


def test_response_follows_the_documented_contract(client):
    body = client.post(ANALYZE_URL, demo(), format="json").json()

    assert set(body) == {"request", "provenance", "routes", "recommendation", "warnings", "heatmap"}
    route = body["routes"][0]
    assert set(route) == {
        "id",
        "name",
        "geometry",
        "distance_miles",
        "provider_distance_miles",
        "duration_seconds",
        "departure_time",
        "arrival_time",
        "status",
        "checkpoints",
        "summary",
    }
    assert set(route["checkpoints"][0]) == {
        "index",
        "id",
        "kind",
        "lat",
        "lon",
        "distance_miles",
        "eta",
        "timezone",
        "utc_offset_seconds",
        "attributed_miles",
        "weather",
        "risk",
    }
    assert set(route["summary"]) == {
        "no_travel_miles",
        "severe_miles",
        "high_miles",
        "moderate_miles",
        "low_miles",
        "unknown_miles",
        "average_risk",
        "coverage_complete",
        "max_level",
    }
    assert set(body["recommendation"]) == {
        "route_id",
        "explanation",
        "ranking",
        "blocked_route_ids",
        "unverified_route_ids",
    }
    assert set(body["heatmap"]) == {
        "base_time",
        "hours",
        "cell_size_miles",
        "lat_step",
        "lon_step",
        "cells",
    }
    assert set(body["heatmap"]["cells"][0]) == {"lat", "lon", "risk", "wind", "rain", "snow"}
    assert set(body["provenance"]) == {"mode", "routing", "weather", "notes"}


def test_live_weather_reaches_the_risk_classification(client, respx_mock):
    mock_routing(respx_mock)
    mock_forecast(respx_mock, wind=47.0)  # Severe band; No Travel above 30,000 lb

    heavy = client.post(ANALYZE_URL, trip(load_weight_lb=30_001), format="json").json()
    light = client.post(ANALYZE_URL, trip(load_weight_lb=30_000), format="json").json()

    assert {r["status"] for r in heavy["routes"]} == {"blocked"}
    assert heavy["recommendation"]["route_id"] is None
    assert heavy["recommendation"]["explanation"].startswith(
        "No safe route is currently recommended."
    )
    assert {r["status"] for r in light["routes"]} == {"ok"}
    assert light["routes"][0]["summary"]["severe_miles"] == 100.0


def test_changing_the_interval_changes_the_checkpoints(client):
    def checkpoint_count(interval):
        body = client.post(ANALYZE_URL, demo(checkpoint_interval_miles=interval), format="json")
        return len(body.json()["routes"][0]["checkpoints"])

    # Route A is 604.07 miles. At 50 miles the 600-mile checkpoint is under 5 miles (10 % of the
    # interval) from the destination, so the destination takes its place.
    assert (checkpoint_count(10), checkpoint_count(25), checkpoint_count(50)) == (62, 26, 13)


def test_demo_mode_is_served_without_any_provider_call_and_is_labeled(client):
    response = client.post(ANALYZE_URL, demo(), format="json")  # no HTTP mocked: none may happen
    assert response.status_code == 200
    body = response.json()
    assert body["provenance"]["mode"] == "fixture"
    assert body["warnings"][0]["code"] == "DEMO_MODE"
    assert len(body["routes"]) == 3


# -------------------------------------------------------------- validation ------
def test_interval_defaults_to_25_miles_and_mode_to_live(client, respx_mock):
    mock_routing(respx_mock)
    mock_forecast(respx_mock)
    body = trip()
    del body["checkpoint_interval_miles"]

    request = client.post(ANALYZE_URL, body, format="json").json()["request"]

    assert (request["checkpoint_interval_miles"], request["mode"]) == (25, "live")


@pytest.mark.parametrize(
    "overrides",
    [
        {"departure_time": (datetime.now(UTC) - timedelta(minutes=45)).isoformat()},
        {"departure_time": (datetime.now(UTC) + timedelta(days=13, hours=23)).isoformat()},
        {"departure_time": tomorrow().isoformat().replace("+00:00", "Z")},
        {"departure_time": tomorrow().astimezone(None).isoformat()},
        {"load_weight_lb": 0},
        {"load_weight_lb": 200_000},
        {"checkpoint_interval_miles": 10},
        {"checkpoint_interval_miles": 50},
    ],
)
def test_values_at_the_edges_of_the_allowed_ranges_are_accepted(client, overrides):
    assert client.post(ANALYZE_URL, demo(**overrides), format="json").status_code == 200


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"origin": None}, "origin"),
        ({"origin": {"lat": 91, "lon": -100.0}}, "origin"),
        ({"origin": {"lat": 39.0, "lon": -180.5}}, "origin"),
        ({"origin": {"lat": "nan", "lon": -100.0}}, "origin"),
        ({"destination": {"lat": 39.0}}, "destination"),
        ({"destination": {"lat": 39.0, "lon": -100.0}}, "destination"),  # same place as origin
        ({"departure_time": "tomorrow morning"}, "departure_time"),
        ({"departure_time": "2026-11-06T08:00:00"}, "departure_time"),  # no UTC offset
        (
            {"departure_time": (datetime.now(UTC) - timedelta(hours=2)).isoformat()},
            "departure_time",
        ),
        (
            {"departure_time": (datetime.now(UTC) + timedelta(days=14, hours=1)).isoformat()},
            "departure_time",
        ),
        ({"load_weight_lb": -1}, "load_weight_lb"),
        ({"load_weight_lb": 200_001}, "load_weight_lb"),
        ({"load_weight_lb": 42_000.5}, "load_weight_lb"),
        ({"load_weight_lb": "heavy"}, "load_weight_lb"),
        ({"checkpoint_interval_miles": 30}, "checkpoint_interval_miles"),
        ({"mode": "turbo"}, "mode"),
    ],
)
def test_invalid_input_is_a_400_that_names_the_field(client, overrides, field):
    response = client.post(ANALYZE_URL, demo(**overrides), format="json")

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert field in error(response)["details"]


def test_missing_fields_are_all_reported(client):
    response = client.post(ANALYZE_URL, {}, format="json")
    assert response.status_code == 400
    assert set(error(response)["details"]) == {
        "origin",
        "destination",
        "departure_time",
        "load_weight_lb",
    }


@override_settings(ALLOW_FIXTURE_MODE=False)
def test_demo_mode_is_rejected_when_the_server_disables_it(client):
    response = client.post(ANALYZE_URL, demo(), format="json")
    assert response.status_code == 400
    assert "mode" in error(response)["details"]


def test_malformed_json_is_a_400(client):
    response = client.post(ANALYZE_URL, "{not json", content_type="application/json")
    assert response.status_code == 400
    assert error(response)["code"] == "PARSEERROR"


def test_analyze_only_accepts_post(client):
    response = client.get(ANALYZE_URL)
    assert response.status_code == 405
    assert error(response)["code"] == "METHODNOTALLOWED"


# ------------------------------------------------------- provider failures ------
def test_no_route_between_the_places_is_a_422(client, respx_mock):
    respx_mock.post(VALHALLA_URL).respond(400, json={"error_code": 442, "error": "No path"})

    response = client.post(ANALYZE_URL, trip(), format="json")

    assert response.status_code == 422
    assert error(response)["code"] == "NO_ROUTE"
    assert "provider" not in error(response)


def test_routing_failure_is_a_502(client, respx_mock):
    respx_mock.post(VALHALLA_URL).respond(503)
    response = client.post(ANALYZE_URL, trip(), format="json")
    assert response.status_code == 502
    assert (error(response)["code"], error(response)["provider"]) == (
        "ROUTING_UNAVAILABLE",
        "valhalla",
    )
    assert error(response)["message"]


def test_routing_timeout_is_a_504(client, respx_mock):
    respx_mock.post(VALHALLA_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    response = client.post(ANALYZE_URL, trip(), format="json")
    assert response.status_code == 504
    assert error(response)["code"] == "ROUTING_TIMEOUT"


def test_weather_failure_is_a_502(client, respx_mock):
    mock_routing(respx_mock)
    respx_mock.get(FORECAST_URL).respond(500)
    response = client.post(ANALYZE_URL, trip(), format="json")
    assert response.status_code == 502
    assert (error(response)["code"], error(response)["provider"]) == (
        "WEATHER_UNAVAILABLE",
        "open-meteo",
    )


def test_weather_timeout_is_a_504(client, respx_mock):
    mock_routing(respx_mock)
    respx_mock.get(FORECAST_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    response = client.post(ANALYZE_URL, trip(), format="json")
    assert response.status_code == 504
    assert error(response)["code"] == "WEATHER_TIMEOUT"


def test_analysis_requests_are_rate_limited(client, monkeypatch):
    cache.clear()
    monkeypatch.setattr(AnalyzeRateThrottle, "THROTTLE_RATES", {"analyze": "2/min"})

    statuses = [client.post(ANALYZE_URL, demo(), format="json").status_code for _ in range(3)]

    cache.clear()
    assert statuses == [200, 200, 429]


# ----------------------------------------------------------------- geocode ------
def test_geocode_returns_matching_places(client, respx_mock):
    respx_mock.get(SEARCH_URL).respond(
        json={
            "results": [
                {
                    "name": "Denver",
                    "latitude": 39.73915,
                    "longitude": -104.9847,
                    "country_code": "US",
                    "admin1": "Colorado",
                }
            ]
        }
    )

    response = client.get(GEOCODE_URL, {"q": "Denver"})

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "name": "Denver",
                "admin1": "Colorado",
                "country_code": "US",
                "lat": 39.73915,
                "lon": -104.9847,
                "label": "Denver, Colorado, US",
            }
        ]
    }


def test_geocode_passes_the_limit_to_the_provider(client, respx_mock):
    route = respx_mock.get(SEARCH_URL).respond(json={})
    assert client.get(GEOCODE_URL, {"q": "Den", "limit": 3}).json() == {"results": []}
    assert route.calls.last.request.url.params["count"] == "3"


@pytest.mark.parametrize(
    "params, field",
    [
        ({}, "q"),
        ({"q": "D"}, "q"),
        ({"q": "  "}, "q"),
        ({"q": "Denver", "limit": 0}, "limit"),
        ({"q": "Denver", "limit": 11}, "limit"),
    ],
)
def test_geocode_rejects_a_short_query_or_bad_limit(client, params, field):
    response = client.get(GEOCODE_URL, params)
    assert response.status_code == 400
    assert field in error(response)["details"]


def test_geocode_provider_failure_is_a_502(client, respx_mock):
    respx_mock.get(SEARCH_URL).respond(500)
    response = client.get(GEOCODE_URL, {"q": "Denver"})
    assert response.status_code == 502
    assert error(response)["code"] == "GEOCODING_UNAVAILABLE"


def test_metric_rain_just_above_the_no_travel_threshold_blocks_every_route(client, respx_mock):
    mock_routing(respx_mock)
    mock_forecast(respx_mock, rain=25.41, units={"rain": "mm", "showers": "mm"})  # 1.000394 in/h

    body = client.post(ANALYZE_URL, trip(), format="json").json()

    assert {r["status"] for r in body["routes"]} == {"blocked"}
    assert body["recommendation"]["route_id"] is None
    assert "(rain 1.0004 in/h)" in body["recommendation"]["explanation"]

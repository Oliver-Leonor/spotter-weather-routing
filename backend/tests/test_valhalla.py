"""Valhalla routing client: request shape, parsing and failure mapping (HTTP mocked)."""

import json

import httpx
import pytest

from common.errors import NoRouteError, UpstreamError
from routing.eta import elapsed_at, elapsed_profile
from routing.geometry import cumulative_miles
from routing.providers.base import Maneuver
from routing.providers.recorded import RecordedRouteProvider
from routing.providers.valhalla import ValhallaProvider
from tests.helpers import meridian_line, valhalla_response, valhalla_trip

ROUTE_URL = "https://valhalla1.openstreetmap.de/route"
ORIGIN = (39.0, -100.0)
DESTINATION = (40.447, -100.0)

LINE_A = meridian_line(100.0, points=5)
LINE_B = meridian_line(110.0, points=6, lon=-99.5)
LINE_C = meridian_line(125.0, points=7, lon=-99.0)


def three_route_payload():
    return valhalla_response(
        valhalla_trip(LINE_A, seconds=6000.0, miles=100.2),
        valhalla_trip(LINE_B, seconds=6600.0, miles=110.3),
        valhalla_trip(LINE_C, seconds=7500.0, miles=125.4),
    )


def test_returns_every_route_with_geometry_duration_and_distance(respx_mock):
    respx_mock.post(ROUTE_URL).respond(json=three_route_payload())

    result = ValhallaProvider().get_routes(ORIGIN, DESTINATION)

    assert [route.duration_seconds for route in result.routes] == [6000.0, 6600.0, 7500.0]
    assert [route.provider_distance_miles for route in result.routes] == [100.2, 110.3, 125.4]
    decoded = result.routes[0].points
    assert [lat for lat, _ in decoded] == pytest.approx([lat for lat, _ in LINE_A], abs=1e-6)
    assert [lon for _, lon in decoded] == [-100.0] * 5
    assert result.routes[0].maneuvers == (
        Maneuver(seconds=6000.0, begin_index=0, end_index=4),
        Maneuver(seconds=0.0, begin_index=4, end_index=4),
    )
    assert (result.provider, result.endpoint, result.costing) == (
        "valhalla",
        "valhalla1.openstreetmap.de",
        "auto",
    )


def test_asks_for_two_alternates_in_miles_with_an_identifying_user_agent(respx_mock):
    route = respx_mock.post(ROUTE_URL).respond(json=three_route_payload())

    ValhallaProvider().get_routes(ORIGIN, DESTINATION)

    request = route.calls.last.request
    assert json.loads(request.content) == {
        "locations": [{"lat": 39.0, "lon": -100.0}, {"lat": 40.447, "lon": -100.0}],
        "costing": "auto",
        "alternates": 2,
        "units": "miles",
        "directions_type": "maneuvers",
    }
    assert request.headers["user-agent"].startswith("StormRoute/")
    assert "github.com/Oliver-Leonor/spotter-weather-routing" in request.headers["user-agent"]


def test_single_route_response_has_no_alternates(respx_mock):
    respx_mock.post(ROUTE_URL).respond(json={"trip": valhalla_trip(LINE_A, seconds=6000.0)})
    assert len(ValhallaProvider().get_routes(ORIGIN, DESTINATION).routes) == 1


def test_distance_reported_in_kilometres_is_converted_to_miles(respx_mock):
    trip = valhalla_trip(LINE_A, seconds=6000.0, miles=160.9344)
    trip["units"] = "kilometers"
    respx_mock.post(ROUTE_URL).respond(json={"trip": trip})

    route = ValhallaProvider().get_routes(ORIGIN, DESTINATION).routes[0]
    assert route.provider_distance_miles == pytest.approx(100.0, abs=0.001)


@pytest.mark.parametrize("error_code", [170, 171, 442])
def test_no_path_between_the_places_is_a_no_route_error(respx_mock, error_code):
    respx_mock.post(ROUTE_URL).respond(
        400, json={"error_code": error_code, "error": "No path could be found for input"}
    )
    with pytest.raises(NoRouteError) as excinfo:
        ValhallaProvider().get_routes(ORIGIN, DESTINATION)
    assert (excinfo.value.status_code, excinfo.value.code) == (422, "NO_ROUTE")


def test_trip_longer_than_the_provider_limit_is_a_no_route_error(respx_mock):
    respx_mock.post(ROUTE_URL).respond(
        400, json={"error_code": 154, "error": "Path distance exceeds the max distance limit"}
    )
    with pytest.raises(NoRouteError) as excinfo:
        ValhallaProvider().get_routes(ORIGIN, DESTINATION)
    assert "too long" in excinfo.value.message


@pytest.mark.parametrize("status", [429, 500, 503])
def test_provider_failure_is_a_502(respx_mock, status):
    respx_mock.post(ROUTE_URL).respond(status, text="upstream trouble")
    with pytest.raises(UpstreamError) as excinfo:
        ValhallaProvider().get_routes(ORIGIN, DESTINATION)
    assert (excinfo.value.status_code, excinfo.value.code) == (502, "ROUTING_UNAVAILABLE")
    assert excinfo.value.provider == "valhalla"


def test_timeout_is_a_504(respx_mock):
    respx_mock.post(ROUTE_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(UpstreamError) as excinfo:
        ValhallaProvider().get_routes(ORIGIN, DESTINATION)
    assert (excinfo.value.status_code, excinfo.value.code) == (504, "ROUTING_TIMEOUT")


def test_connection_error_is_retried_once(respx_mock):
    route = respx_mock.post(ROUTE_URL).mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, json=three_route_payload())]
    )
    assert len(ValhallaProvider().get_routes(ORIGIN, DESTINATION).routes) == 3
    assert route.call_count == 2


def test_repeated_connection_errors_are_a_502(respx_mock):
    route = respx_mock.post(ROUTE_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(UpstreamError) as excinfo:
        ValhallaProvider().get_routes(ORIGIN, DESTINATION)
    assert excinfo.value.status_code == 502
    assert route.call_count == 2


def test_timeouts_are_not_retried(respx_mock):
    route = respx_mock.post(ROUTE_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(UpstreamError):
        ValhallaProvider().get_routes(ORIGIN, DESTINATION)
    assert route.call_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"trip": {"summary": {"time": 10.0, "length": 1.0}, "legs": []}},
        {
            "trip": {
                "summary": {"time": 10.0, "length": 1.0},
                "legs": [{"shape": "", "maneuvers": []}],
            }
        },
        {"trip": valhalla_trip(LINE_A, seconds=0.0)},
    ],
)
def test_unreadable_route_payload_is_a_502(respx_mock, payload):
    respx_mock.post(ROUTE_URL).respond(json=payload)
    with pytest.raises(UpstreamError) as excinfo:
        ValhallaProvider().get_routes(ORIGIN, DESTINATION)
    assert (excinfo.value.status_code, excinfo.value.code) == (502, "ROUTING_UNAVAILABLE")


def test_non_json_body_is_a_502(respx_mock):
    respx_mock.post(ROUTE_URL).respond(200, text="<html>gateway</html>")
    with pytest.raises(UpstreamError):
        ValhallaProvider().get_routes(ORIGIN, DESTINATION)


def test_same_trip_is_served_from_the_cache(respx_mock):
    route = respx_mock.post(ROUTE_URL).respond(json=three_route_payload())
    provider = ValhallaProvider()

    first = provider.get_routes(ORIGIN, DESTINATION)
    second = provider.get_routes(ORIGIN, DESTINATION)

    assert route.call_count == 1
    assert second is first


def test_different_destination_is_not_served_from_the_cache(respx_mock):
    route = respx_mock.post(ROUTE_URL).respond(json=three_route_payload())
    provider = ValhallaProvider()

    provider.get_routes(ORIGIN, DESTINATION)
    provider.get_routes(ORIGIN, (41.0, -100.0))

    assert route.call_count == 2


def test_failures_are_not_cached(respx_mock):
    route = respx_mock.post(ROUTE_URL).mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=three_route_payload())]
    )
    provider = ValhallaProvider()
    with pytest.raises(UpstreamError):
        provider.get_routes(ORIGIN, DESTINATION)
    assert len(provider.get_routes(ORIGIN, DESTINATION).routes) == 3
    assert route.call_count == 2


# ------------------------------------------------- recorded real response ------
def test_recorded_denver_to_kansas_city_response_has_three_real_routes():
    result = RecordedRouteProvider().get_routes(ORIGIN, DESTINATION)

    lengths = [cumulative_miles(route.points)[-1] for route in result.routes]
    assert lengths == pytest.approx([604.07, 613.53, 634.83], abs=0.05)
    # Great-circle length of the decoded shape agrees with the provider's own total within 0.2 %.
    for length, route in zip(lengths, result.routes, strict=True):
        assert length == pytest.approx(route.provider_distance_miles, rel=0.002)
    assert [round(route.duration_seconds / 3600, 2) for route in result.routes] == [
        8.78,
        9.53,
        9.84,
    ]


def test_recorded_maneuvers_drive_the_eta_profile():
    route = RecordedRouteProvider().get_routes(ORIGIN, DESTINATION).routes[1]
    cumulative = cumulative_miles(route.points)
    profile = elapsed_profile(cumulative, route.maneuvers, route.duration_seconds)

    assert profile[-1] == pytest.approx(route.duration_seconds)
    assert profile == sorted(profile)
    # Route B mixes interstate and slower US highways, so the halfway point in miles is not the
    # halfway point in time. A purely proportional profile would make these equal.
    halfway = elapsed_at(cumulative, profile, cumulative[-1] / 2)
    assert abs(halfway - route.duration_seconds / 2) > 60


def test_recorded_provider_describes_its_trip():
    provider = RecordedRouteProvider()
    assert provider.origin == (39.7392, -104.9903)
    assert provider.destination == (39.0997, -94.5786)
    assert provider.origin_label == "Denver, Colorado, US"
    assert provider.destination_label == "Kansas City, Missouri, US"
    assert provider.recorded_at.isoformat() == "2026-11-05T02:10:00+00:00"

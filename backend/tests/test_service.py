"""Analysis service: routes, checkpoints, ETAs, weather, risk and recommendation together.

Uses in-memory providers (tests/fakes.py) so every number below is derived from known inputs.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from analysis.service import Place, TripRequest, analyze
from common.errors import TripTooLargeError, UpstreamError
from tests.fakes import FakeRouting, FakeWeather, straight_route

DEPARTURE = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
ROUTE_A = straight_route(100.0, hours=2.0, lon=-100.0)  # 50 mph: a checkpoint every 30 minutes
ROUTE_B = straight_route(110.0, hours=2.5, lon=-99.5)
ROUTE_C = straight_route(125.0, hours=3.0, lon=-99.0)


def trip(departure=DEPARTURE, load=20_000, interval=25, mode="live") -> TripRequest:
    return TripRequest(
        origin=Place(39.0, -100.0, "Start"),
        destination=Place(40.45, -100.0, "End"),
        departure=departure,
        load_weight_lb=load,
        interval_miles=interval,
        mode=mode,
    )


def run(*routes, weather=None, **trip_kwargs) -> dict:
    return analyze(
        trip(**trip_kwargs),
        routing=FakeRouting(*(routes or (ROUTE_A, ROUTE_B, ROUTE_C))),
        weather=weather or FakeWeather(),
    )


def on_route_a(lon: float) -> bool:
    return abs(lon - -100.0) < 0.01


def checkpoint_values(route: dict, key: str) -> list:
    return [checkpoint[key] for checkpoint in route["checkpoints"]]


def levels(route: dict) -> list[str]:
    return [checkpoint["risk"]["level"] for checkpoint in route["checkpoints"]]


# ------------------------------------------------------------------ routes ------
def test_routes_are_named_in_provider_order():
    result = run()
    assert [(r["id"], r["name"]) for r in result["routes"]] == [
        ("route-1", "Route A"),
        ("route-2", "Route B"),
        ("route-3", "Route C"),
    ]
    assert [r["status"] for r in result["routes"]] == ["ok", "ok", "ok"]
    assert result["warnings"] == []


def test_route_reports_measured_and_provider_distance_and_times():
    route = run()["routes"][0]
    assert route["distance_miles"] == 100.0
    assert route["provider_distance_miles"] == 100.0
    assert route["duration_seconds"] == 7200
    assert route["departure_time"] == "2026-11-06T15:00:00Z"
    assert route["arrival_time"] == "2026-11-06T17:00:00Z"


def test_geometry_is_geojson_lon_lat_simplified_for_display():
    geometry = run()["routes"][0]["geometry"]
    assert geometry["type"] == "LineString"
    # The 21 collinear shape points collapse to the two ends; order is [lon, lat].
    assert geometry["coordinates"] == [[-100.0, 39.0], [-100.0, pytest.approx(40.44732, abs=1e-5)]]


def test_duplicate_route_from_the_provider_is_removed_with_warnings():
    same_road_denser = straight_route(100.0, hours=2.1, lon=-100.0, points=51)
    result = run(ROUTE_A, same_road_denser, ROUTE_C)

    assert [r["name"] for r in result["routes"]] == ["Route A", "Route B"]
    assert result["routes"][1]["distance_miles"] == 125.0  # the distinct third option
    assert {w["code"]: w["message"] for w in result["warnings"]} == {
        "DUPLICATE_ROUTES_REMOVED": (
            "The routing provider returned 1 route that duplicates another option. It was removed."
        ),
        "FEWER_ROUTES": "The routing provider returned 2 distinct routes for this trip.",
    }


def test_single_route_is_reported_not_padded():
    result = run(ROUTE_A)
    assert len(result["routes"]) == 1
    assert result["warnings"] == [
        {
            "code": "FEWER_ROUTES",
            "message": "The routing provider returned 1 distinct route for this trip.",
        }
    ]


def test_at_most_three_routes_are_analyzed():
    fourth = straight_route(140.0, hours=3.5, lon=-98.5)
    assert len(run(ROUTE_A, ROUTE_B, ROUTE_C, fourth)["routes"]) == 3


# ------------------------------------------------------- checkpoints, ETAs ------
@pytest.mark.parametrize(
    "interval, distances",
    [
        (10, [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]),
        (25, [0.0, 25.0, 50.0, 75.0, 100.0]),
        (50, [0.0, 50.0, 100.0]),
    ],
)
def test_checkpoints_are_sampled_at_the_selected_interval(interval, distances):
    route = run(interval=interval)["routes"][0]
    assert checkpoint_values(route, "distance_miles") == distances
    assert checkpoint_values(route, "index") == list(range(len(distances)))
    kinds = checkpoint_values(route, "kind")
    assert (kinds[0], kinds[-1]) == ("origin", "destination")
    assert set(kinds[1:-1]) == {"checkpoint"}
    assert route["checkpoints"][1]["id"] == "route-1-cp-1"


def test_checkpoint_etas_follow_the_driving_time():
    route = run()["routes"][0]
    assert checkpoint_values(route, "eta") == [
        "2026-11-06T15:00:00Z",
        "2026-11-06T15:30:00Z",
        "2026-11-06T16:00:00Z",
        "2026-11-06T16:30:00Z",
        "2026-11-06T17:00:00Z",
    ]


def test_departure_with_a_utc_offset_is_converted_to_utc():
    mountain = timezone(timedelta(hours=-7))
    result = run(departure=datetime(2026, 11, 6, 8, 0, tzinfo=mountain))
    assert result["request"]["departure_time"] == "2026-11-06T08:00:00-07:00"
    assert result["request"]["departure_time_utc"] == "2026-11-06T15:00:00Z"
    assert result["routes"][0]["checkpoints"][0]["eta"] == "2026-11-06T15:00:00Z"


def test_forecast_hour_is_the_nearest_hour_and_ties_go_to_the_earlier_hour():
    route = run()["routes"][0]
    assert [c["weather"]["forecast_time"] for c in route["checkpoints"]] == [
        "2026-11-06T15:00:00Z",  # ETA 15:00
        "2026-11-06T15:00:00Z",  # ETA 15:30, tie
        "2026-11-06T16:00:00Z",  # ETA 16:00
        "2026-11-06T16:00:00Z",  # ETA 16:30, tie
        "2026-11-06T17:00:00Z",  # ETA 17:00
    ]


def test_later_departure_moves_etas_onto_a_different_forecast_hour_and_changes_risk():
    def gale_at_17(lat, lon, hour):
        return {"wind": 50.0} if hour.hour == 17 else {}

    on_time = run(weather=FakeWeather(gale_at_17))["routes"][0]
    one_hour_later = run(weather=FakeWeather(gale_at_17), departure=DEPARTURE + timedelta(hours=1))[
        "routes"
    ][0]

    # Leaving at 15:00 only the arrival (17:00) meets the gale. Leaving at 16:00 the checkpoints
    # reached at 17:00 and 17:30 meet it instead.
    assert levels(on_time) == ["low", "low", "low", "low", "severe"]
    assert levels(one_hour_later) == ["low", "low", "severe", "severe", "low"]
    assert checkpoint_values(one_hour_later, "eta")[0] == "2026-11-06T16:00:00Z"
    assert (on_time["summary"]["severe_miles"], one_hour_later["summary"]["severe_miles"]) == (
        12.5,
        50.0,
    )


def test_checkpoint_local_offset_changes_when_daylight_saving_time_ends():
    # US daylight saving time ends at 2026-11-01 08:00 UTC (02:00 MDT becomes 01:00 MST).
    departure = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)
    weather = FakeWeather(
        first_hour=datetime(2026, 11, 1, 0, 0, tzinfo=UTC), timezone="America/Denver"
    )
    route = run(weather=weather, departure=departure)["routes"][0]

    assert checkpoint_values(route, "eta") == [
        "2026-11-01T07:00:00Z",
        "2026-11-01T07:30:00Z",
        "2026-11-01T08:00:00Z",
        "2026-11-01T08:30:00Z",
        "2026-11-01T09:00:00Z",
    ]
    assert checkpoint_values(route, "timezone") == ["America/Denver"] * 5
    assert checkpoint_values(route, "utc_offset_seconds") == [
        -21600,
        -21600,
        -25200,
        -25200,
        -25200,
    ]


# ------------------------------------------------------- weather and risk ------
def test_checkpoint_reports_the_measurements_behind_its_risk():
    def weather(lat, lon, hour):
        return {
            "wind": 28.4,
            "gust": 41.0,
            "rain": 0.12,
            "snow": 0.0,
            "temperature": 35.5,
            "code": 61,
        }

    checkpoint = run(weather=FakeWeather(weather))["routes"][0]["checkpoints"][0]
    assert checkpoint["weather"] == {
        "forecast_time": "2026-11-06T15:00:00Z",
        "wind_mph": 28.4,
        "wind_gust_mph": 41.0,
        "rain_in_per_hr": 0.12,
        "snow_in_per_hr": 0.0,
        "temperature_f": 35.5,
        "weather_code": 61,
    }
    assert checkpoint["risk"] == {
        "level": "moderate",
        "value": 1,
        "drivers": ["wind", "rain"],
        "wind_level": "moderate",
        "rain_level": "moderate",
        "snow_level": "low",
        "load_rule_applied": None,
        "missing": [],
    }


def test_eta_beyond_forecast_coverage_is_unknown_and_the_route_is_unverified():
    # The forecast ends at 16:00, so the arrival at 17:00 has no forecast hour within 30 minutes.
    short_forecast = FakeWeather(first_hour=datetime(2026, 11, 6, 14, 0, tzinfo=UTC), hours=3)
    result = run(ROUTE_A, weather=short_forecast)
    route = result["routes"][0]

    assert levels(route) == ["low", "low", "low", "low", "unknown"]
    arrival = route["checkpoints"][-1]
    assert arrival["weather"] is None
    assert arrival["risk"]["value"] is None
    assert arrival["risk"]["missing"] == ["wind", "rain", "snow"]
    assert route["status"] == "unverified"
    assert route["summary"]["unknown_miles"] == 12.5
    assert route["summary"]["low_miles"] == 87.5
    assert route["summary"]["coverage_complete"] is False
    assert result["recommendation"]["route_id"] is None
    assert result["recommendation"]["unverified_route_ids"] == ["route-1"]
    assert result["recommendation"]["explanation"] == (
        "No safe route is currently recommended. "
        "Route A could not be verified: forecast unavailable for 1 checkpoint."
    )


def test_missing_measurement_is_unknown_never_low_and_the_rest_is_still_shown():
    result = run(ROUTE_A, weather=FakeWeather(lambda lat, lon, hour: {"rain": None, "wind": 12.0}))
    checkpoint = result["routes"][0]["checkpoints"][0]

    assert checkpoint["risk"]["level"] == "unknown"
    assert checkpoint["risk"]["missing"] == ["rain"]
    assert checkpoint["weather"]["wind_mph"] == 12.0
    assert checkpoint["weather"]["rain_in_per_hr"] is None
    assert result["routes"][0]["status"] == "unverified"
    assert result["routes"][0]["summary"]["low_miles"] == 0.0


def test_no_travel_checkpoint_blocks_the_route_and_it_is_not_recommended():
    def storm_on_a(lat, lon, hour):
        return {"wind": 58.0} if on_route_a(lon) and hour.hour == 16 else {}

    result = run(weather=FakeWeather(storm_on_a))
    route_a = result["routes"][0]

    assert levels(route_a) == ["low", "low", "no_travel", "no_travel", "low"]
    assert route_a["status"] == "blocked"
    assert route_a["summary"]["no_travel_miles"] == 50.0
    recommendation = result["recommendation"]
    assert recommendation["route_id"] == "route-2"
    assert recommendation["ranking"] == ["route-2", "route-3"]
    assert recommendation["blocked_route_ids"] == ["route-1"]
    assert recommendation["explanation"] == (
        "Route B is recommended because it is 30 minutes faster than Route C. "
        "Severe miles, high-risk miles and average risk are tied. "
        "Route A: No Travel at checkpoint 2 near 39.72, -100.00 at 10:00 CST (wind 58.0 mph), "
        "and at 1 more checkpoint."
    )


def test_no_route_is_recommended_when_every_route_is_blocked():
    result = run(weather=FakeWeather(lambda lat, lon, hour: {"rain": 1.2}))
    recommendation = result["recommendation"]

    assert [r["status"] for r in result["routes"]] == ["blocked"] * 3
    assert recommendation["route_id"] is None
    assert recommendation["ranking"] == []
    assert recommendation["blocked_route_ids"] == ["route-1", "route-2", "route-3"]
    assert recommendation["explanation"].startswith(
        "No safe route is currently recommended. "
        "Route A: No Travel at checkpoint 0 near 39.00, -100.00 at 09:00 CST (rain 1.20 in/h), "
        "and at 4 more checkpoints."
    )


def test_no_travel_with_another_measurement_missing_still_blocks_the_route():
    result = run(ROUTE_A, weather=FakeWeather(lambda lat, lon, hour: {"wind": 60.0, "snow": None}))
    checkpoint = result["routes"][0]["checkpoints"][0]
    assert (checkpoint["risk"]["level"], checkpoint["risk"]["missing"]) == ("no_travel", ["snow"])
    assert result["routes"][0]["status"] == "blocked"


@pytest.mark.parametrize(
    "wind, load, level, status",
    [
        (47.0, 30_000, "severe", "ok"),  # at the limit: the rule needs more than 30,000 lb
        (47.0, 30_001, "no_travel", "blocked"),
        (38.0, 40_000, "high", "ok"),  # at the limit: the rule needs more than 40,000 lb
        (38.0, 40_001, "severe", "ok"),
    ],
)
def test_load_weight_changes_the_wind_risk(wind, load, level, status):
    result = run(ROUTE_A, weather=FakeWeather(lambda lat, lon, hour: {"wind": wind}), load=load)
    assert set(levels(result["routes"][0])) == {level}
    assert result["routes"][0]["status"] == status


def test_load_rule_is_named_in_the_blocking_reason():
    result = run(ROUTE_A, weather=FakeWeather(lambda lat, lon, hour: {"wind": 47.0}), load=42_000)
    assert "(wind 47.0 mph with a load over 30,000 lb)" in result["recommendation"]["explanation"]


def test_recommendation_prefers_fewer_severe_miles_over_the_fastest_route():
    def severe_on_a(lat, lon, hour):
        return {"snow": 2.5} if on_route_a(lon) and hour.hour == 16 else {}

    recommendation = run(weather=FakeWeather(severe_on_a))["recommendation"]
    assert recommendation["route_id"] == "route-2"
    assert recommendation["ranking"] == ["route-2", "route-3", "route-1"]
    assert recommendation["explanation"] == (
        "Route B is recommended because it is 30 minutes faster than Route C. "
        "Severe miles, high-risk miles and average risk are tied. "
        "It also has 50.0 fewer miles of severe weather than Route A."
    )


def test_risk_miles_add_up_to_the_route_length():
    def mixed(lat, lon, hour):
        return {"wind": 5.0 + 10.0 * (hour.hour - 15)}  # 5, 15, 25 mph at 15:00, 16:00, 17:00

    route = run(ROUTE_A, weather=FakeWeather(mixed))["routes"][0]
    summary = route["summary"]
    assert sum(checkpoint_values(route, "attributed_miles")) == pytest.approx(100.0)
    assert (summary["low_miles"], summary["moderate_miles"]) == (87.5, 12.5)
    assert summary["average_risk"] == 0.125
    assert summary["max_level"] == "moderate"


# ----------------------------------------------------------------- heatmap ------
def test_heatmap_covers_49_hours_from_the_departure_hour():
    heatmap = run(departure=DEPARTURE + timedelta(minutes=20))["heatmap"]
    assert heatmap["base_time"] == "2026-11-06T15:00:00Z"
    assert len(heatmap["hours"]) == 49
    assert 0 < len(heatmap["cells"]) <= 144
    assert all(len(cell["risk"]) == 49 for cell in heatmap["cells"])
    assert {value for cell in heatmap["cells"] for value in cell["risk"]} == {0}


def test_heatmap_uses_the_request_load_weight():
    def windy(lat, lon, hour):
        return {"wind": 47.0}

    light = run(weather=FakeWeather(windy), load=20_000)["heatmap"]["cells"][0]["risk"][0]
    heavy = run(weather=FakeWeather(windy), load=35_000)["heatmap"]["cells"][0]["risk"][0]
    assert (light, heavy) == (3, 4)


def test_heatmap_failure_keeps_the_route_results_and_adds_a_warning():
    result = run(weather=FakeWeather(fail_on_calls=(2,)))  # the second fetch is the heatmap grid

    assert [r["status"] for r in result["routes"]] == ["ok", "ok", "ok"]
    assert result["recommendation"]["route_id"] == "route-1"
    assert result["heatmap"]["cells"] == []
    assert len(result["heatmap"]["hours"]) == 49
    assert [w["code"] for w in result["warnings"]] == ["HEATMAP_UNAVAILABLE"]


def test_checkpoint_weather_failure_fails_the_analysis():
    with pytest.raises(UpstreamError) as excinfo:
        run(weather=FakeWeather(fail_on_calls=(1,)))
    assert excinfo.value.code == "WEATHER_UNAVAILABLE"


# -------------------------------------------------------------- provenance ------
def test_weather_is_requested_for_the_trip_and_the_48_hour_heatmap_window():
    weather = FakeWeather()
    result = run(weather=weather, departure=DEPARTURE + timedelta(minutes=20))

    assert weather.calls[0]["start"] == datetime(2026, 11, 6, 14, 0, tzinfo=UTC)
    assert weather.calls[0]["end"] == datetime(2026, 11, 8, 15, 0, tzinfo=UTC)
    assert result["provenance"]["weather"]["forecast_window"] == {
        "start": "2026-11-06T14:00:00Z",
        "end": "2026-11-08T15:00:00Z",
    }


def test_provenance_names_the_providers_and_discloses_the_routing_limitation():
    provenance = run()["provenance"]
    assert provenance["mode"] == "live"
    assert provenance["routing"] == {
        "provider": "valhalla",
        "endpoint": "routing.test",
        "costing": "auto",
        "fetched_at": "2026-11-06T14:59:00Z",
    }
    assert provenance["weather"]["provider"] == "open-meteo"
    assert provenance["weather"]["model"] == "best_match"
    assert provenance["weather"]["fetched_at"] == "2026-11-06T14:58:00Z"
    assert any("Truck restrictions" in note for note in provenance["notes"])


def test_request_is_echoed_with_the_validated_inputs():
    request = run(load=42_000, interval=50)["request"]
    assert request == {
        "origin": {"lat": 39.0, "lon": -100.0, "label": "Start"},
        "destination": {"lat": 40.45, "lon": -100.0, "label": "End"},
        "departure_time": "2026-11-06T15:00:00+00:00",
        "departure_time_utc": "2026-11-06T15:00:00Z",
        "load_weight_lb": 42_000,
        "checkpoint_interval_miles": 50,
        "mode": "live",
    }


# ------------------------------------------------------------- demo mode ------
def demo(departure_hour_utc=15, load=42_000, interval=25) -> dict:
    departure = datetime(2026, 11, 6, departure_hour_utc, 0, tzinfo=UTC)
    return analyze(trip(departure=departure, load=load, interval=interval, mode="fixture"))


def test_demo_mode_is_labeled_and_never_presented_as_live_data():
    result = demo()
    provenance = result["provenance"]

    assert provenance["mode"] == "fixture"
    assert provenance["weather"]["provider"] == "demo-scenario"
    assert "not a forecast" in provenance["weather"]["model"]
    assert provenance["routing"]["fetched_at"] == "2026-11-05T02:10:00Z"  # when it was recorded
    assert any("not a real forecast" in note for note in provenance["notes"])
    assert result["warnings"][0]["code"] == "DEMO_MODE"


def test_demo_mode_replays_the_recorded_denver_to_kansas_city_trip():
    result = demo()
    assert result["request"]["origin"] == {
        "lat": 39.7392,
        "lon": -104.9903,
        "label": "Denver, Colorado, US",
    }
    assert result["request"]["destination"]["label"] == "Kansas City, Missouri, US"
    assert [r["distance_miles"] for r in result["routes"]] == [604.1, 613.5, 634.8]
    assert [r["provider_distance_miles"] for r in result["routes"]] == [604.7, 614.2, 635.5]
    assert [len(r["checkpoints"]) for r in result["routes"]] == [26, 26, 27]


def test_demo_heavy_load_is_blocked_on_i70_and_the_northern_route_is_recommended():
    result = demo(load=42_000)
    assert [r["status"] for r in result["routes"]] == ["blocked", "blocked", "ok"]
    assert result["recommendation"]["route_id"] == "route-3"
    assert result["recommendation"]["blocked_route_ids"] == ["route-1", "route-2"]
    assert "with a load over 30,000 lb" in result["recommendation"]["explanation"]
    assert result["routes"][2]["summary"]["severe_miles"] > 0  # 35 to 45 mph with over 40,000 lb


def test_demo_light_load_is_not_blocked_and_avoids_the_severe_miles():
    result = demo(load=28_000)
    assert [r["status"] for r in result["routes"]] == ["ok", "ok", "ok"]
    severe = [r["summary"]["severe_miles"] for r in result["routes"]]
    assert severe[0] > 0 and severe[1] > 0 and severe[2] == 0
    assert result["recommendation"]["route_id"] == "route-3"
    assert "miles of severe weather encountered on" in result["recommendation"]["explanation"]


def test_demo_overnight_departure_misses_the_storm_and_the_fastest_route_wins():
    result = demo(departure_hour_utc=3)
    assert {level for r in result["routes"] for level in levels(r)} == {"low"}
    assert result["recommendation"]["route_id"] == "route-1"
    assert "faster than Route B" in result["recommendation"]["explanation"]


# ------------------------------------------------------------- trip size ------
def long_routes():
    return [straight_route(1600.0, hours=24.0, lon=lon) for lon in (-100.0, -99.5, -99.0)]


def test_trip_needing_too_many_forecast_points_is_rejected_before_any_weather_request():
    weather = FakeWeather()
    with pytest.raises(TripTooLargeError) as excinfo:
        run(*long_routes(), weather=weather, interval=10)  # 3 routes x 161 checkpoints

    assert (excinfo.value.status_code, excinfo.value.code) == (422, "TRIP_TOO_LARGE")
    assert excinfo.value.message == (
        "This trip needs 483 checkpoint forecasts at a 10-mile interval, and the limit is 450. "
        "Choose a larger checkpoint interval or a shorter trip."
    )
    assert weather.calls == []


def test_the_same_long_trip_is_analyzed_at_a_larger_interval():
    result = run(*long_routes(), interval=25)
    assert [len(r["checkpoints"]) for r in result["routes"]] == [65, 65, 65]

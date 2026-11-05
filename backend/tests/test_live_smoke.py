"""Live smoke test against the real Valhalla and Open-Meteo services.

Deselected by default (see `addopts` in pyproject.toml) so the normal suite never touches the
network. Run it by hand, sparingly, with:

    pytest -m live -s
"""

import json
import time
from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.live

DENVER = {"lat": 39.7392, "lon": -104.9903, "label": "Denver, Colorado, US"}
KANSAS_CITY = {"lat": 39.0997, "lon": -94.5786, "label": "Kansas City, Missouri, US"}


def analyze(departure: datetime, interval: int = 25) -> tuple[dict, float, int]:
    started = time.perf_counter()
    response = APIClient().post(
        "/api/routes/analyze/",
        {
            "origin": DENVER,
            "destination": KANSAS_CITY,
            "departure_time": departure.isoformat(),
            "load_weight_lb": 42_000,
            "checkpoint_interval_miles": interval,
        },
        format="json",
    )
    seconds = time.perf_counter() - started
    assert response.status_code == 200, response.content
    return response.json(), seconds, len(response.content)


def test_denver_to_kansas_city_against_the_real_providers():
    departure = (datetime.now(UTC) + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    body, seconds, size = analyze(departure)

    assert body["provenance"]["mode"] == "live"
    assert body["provenance"]["routing"]["provider"] == "valhalla"
    assert body["provenance"]["weather"]["provider"] == "open-meteo"

    routes = body["routes"]
    assert len(routes) == 3, body["warnings"]
    assert len({route["distance_miles"] for route in routes}) == 3
    for route in routes:
        assert 550 < route["distance_miles"] < 700
        etas = [checkpoint["eta"] for checkpoint in route["checkpoints"]]
        assert etas == sorted(etas)
        assert etas[0] == route["departure_time"] and etas[-1] == route["arrival_time"]
        attributed = sum(checkpoint["attributed_miles"] for checkpoint in route["checkpoints"])
        assert attributed == pytest.approx(route["distance_miles"], abs=0.5)
        for checkpoint in route["checkpoints"]:
            assert checkpoint["weather"] is not None
            assert checkpoint["weather"]["wind_mph"] is not None
            assert checkpoint["risk"]["level"] != "unknown"
            assert checkpoint["timezone"] in {"America/Denver", "America/Chicago"}
        assert route["summary"]["coverage_complete"] is True

    heatmap = body["heatmap"]
    assert len(heatmap["hours"]) == 49
    assert 0 < len(heatmap["cells"]) <= 144
    assert all(value is not None for cell in heatmap["cells"] for value in cell["risk"])

    # Leaving six hours later must move every ETA and select later forecast hours.
    later, later_seconds, _ = analyze(departure + timedelta(hours=6))
    first, first_later = routes[0]["checkpoints"][5], later["routes"][0]["checkpoints"][5]
    shift = datetime.fromisoformat(first_later["eta"]) - datetime.fromisoformat(first["eta"])
    assert shift == timedelta(hours=6)
    forecast_shift = datetime.fromisoformat(
        first_later["weather"]["forecast_time"]
    ) - datetime.fromisoformat(first["weather"]["forecast_time"])
    assert forecast_shift == timedelta(hours=6)

    print("\n--- live smoke summary ---")
    print(
        f"departure {departure.isoformat()}  first call {seconds:.2f}s  "
        f"second call {later_seconds:.2f}s  response {size / 1024:.0f} KB"
    )
    for route in routes:
        summary = route["summary"]
        print(
            f"{route['name']}: {route['distance_miles']} mi, "
            f"{route['duration_seconds'] / 3600:.2f} h, status {route['status']}, "
            f"{len(route['checkpoints'])} checkpoints, "
            f"{len(route['geometry']['coordinates'])} map points, max {summary['max_level']}, "
            f"avg {summary['average_risk']}"
        )
    print("recommendation:", json.dumps(body["recommendation"], indent=2))
    print("warnings:", body["warnings"])
    print(f"heatmap: {len(heatmap['cells'])} cells of {heatmap['cell_size_miles']} mi")
    sample = routes[0]["checkpoints"][5]
    print(
        "sample checkpoint:",
        json.dumps(
            {k: sample[k] for k in ("id", "eta", "timezone", "utc_offset_seconds", "weather")}
        ),
    )

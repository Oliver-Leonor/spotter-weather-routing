"""Place search through the Open-Meteo geocoding API (HTTP mocked)."""

import httpx
import pytest

from common.errors import UpstreamError
from weather.geocoding import search_places

SEARCH_URL = "https://geocoding-api.open-meteo.com/v1/search"
DENVER = {
    "id": 5419384,
    "name": "Denver",
    "latitude": 39.73915,
    "longitude": -104.9847,
    "country_code": "US",
    "country": "United States",
    "admin1": "Colorado",
    "timezone": "America/Denver",
}


def test_results_are_mapped_to_places_with_a_readable_label(respx_mock):
    respx_mock.get(SEARCH_URL).respond(json={"results": [DENVER]})
    assert search_places("Denver") == [
        {
            "name": "Denver",
            "admin1": "Colorado",
            "country_code": "US",
            "lat": 39.73915,
            "lon": -104.9847,
            "label": "Denver, Colorado, US",
        }
    ]


def test_request_passes_the_query_and_limit(respx_mock):
    route = respx_mock.get(SEARCH_URL).respond(json={"results": [DENVER]})
    search_places("Denver", limit=3)
    assert dict(route.calls.last.request.url.params) == {
        "name": "Denver",
        "count": "3",
        "language": "en",
        "format": "json",
    }


def test_no_match_is_an_empty_list(respx_mock):
    respx_mock.get(SEARCH_URL).respond(json={"generationtime_ms": 0.5})  # no "results" key
    assert search_places("Zzzzzz") == []


def test_label_skips_a_missing_region(respx_mock):
    respx_mock.get(SEARCH_URL).respond(
        json={
            "results": [
                {"name": "Monaco", "latitude": 43.73, "longitude": 7.42, "country_code": "MC"}
            ]
        }
    )
    place = search_places("Monaco")[0]
    assert (place["label"], place["admin1"]) == ("Monaco, MC", None)


def test_repeat_queries_are_served_from_the_cache_ignoring_case_and_spacing(respx_mock):
    route = respx_mock.get(SEARCH_URL).respond(json={"results": [DENVER]})
    first = search_places("Denver")
    second = search_places("  denver ")
    assert route.call_count == 1
    assert second == first


def test_provider_failure_is_a_502(respx_mock):
    respx_mock.get(SEARCH_URL).respond(500)
    with pytest.raises(UpstreamError) as excinfo:
        search_places("Denver")
    assert (excinfo.value.status_code, excinfo.value.code) == (502, "GEOCODING_UNAVAILABLE")


def test_timeout_is_a_504(respx_mock):
    respx_mock.get(SEARCH_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(UpstreamError) as excinfo:
        search_places("Denver")
    assert (excinfo.value.status_code, excinfo.value.code) == (504, "GEOCODING_TIMEOUT")

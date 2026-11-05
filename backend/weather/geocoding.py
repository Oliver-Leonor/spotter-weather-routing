"""Place search (cities and towns) through the Open-Meteo geocoding API."""

from __future__ import annotations

from django.conf import settings

from common.cache import TTLCache
from common.errors import UpstreamError
from common.http import read_json, send

PROVIDER = "open-meteo-geocoding"
GEOCODE_CACHE = TTLCache(ttl_seconds=3600, max_entries=1024)


def search_places(query: str, limit: int = 5) -> list[dict]:
    """Places matching `query`, best match first. An unknown name gives an empty list."""
    name = " ".join(query.split())
    key = (name.lower(), limit)
    cached = GEOCODE_CACHE.get(key)
    if cached is not None:
        return cached

    response = send(
        "GET",
        f"{settings.OPEN_METEO_GEOCODING_URL.rstrip('/')}/v1/search",
        params={"name": name, "count": limit, "language": "en", "format": "json"},
        provider=PROVIDER,
        unavailable_code="GEOCODING_UNAVAILABLE",
        timeout_code="GEOCODING_TIMEOUT",
    )
    if response.status_code != 200:
        raise UpstreamError(
            "Place search is unavailable right now. Please try again shortly.",
            provider=PROVIDER,
            code="GEOCODING_UNAVAILABLE",
        )
    payload = read_json(response, provider=PROVIDER, unavailable_code="GEOCODING_UNAVAILABLE")
    try:
        places = [_place(result) for result in payload.get("results") or []]
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise UpstreamError(
            "Place search returned a response that could not be read.",
            provider=PROVIDER,
            code="GEOCODING_UNAVAILABLE",
        ) from exc
    GEOCODE_CACHE.set(key, places)
    return places


def _place(result: dict) -> dict:
    name, admin1, country = result["name"], result.get("admin1"), result.get("country_code")
    return {
        "name": name,
        "admin1": admin1,
        "country_code": country,
        "lat": float(result["latitude"]),
        "lon": float(result["longitude"]),
        "label": ", ".join(part for part in (name, admin1, country) if part),
    }

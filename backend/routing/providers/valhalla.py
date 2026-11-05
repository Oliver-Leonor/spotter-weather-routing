"""Valhalla routing client (public FOSSGIS instance by default).

Fair use of the public server: requests carry an identifying User-Agent and X-Client-Id, only one
request is in flight at a time, and identical trips are answered from a short-lived cache.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from urllib.parse import urlsplit

from django.conf import settings

from common.cache import TTLCache
from common.errors import NoRouteError, UpstreamError
from common.http import read_json, send

from ..geometry import Point, decode_polyline
from .base import Maneuver, ProviderRoute, RoutingResult

PROVIDER = "valhalla"
ALTERNATES = 2  # two alternates plus the primary route gives up to three options
KM_TO_MILES = 0.621371

# Valhalla error codes that mean "no drivable route", as opposed to a provider failure.
NO_ROUTE_ERROR_CODES = {170, 171, 442}
DISTANCE_LIMIT_ERROR_CODE = 154

# Each entry holds up to three full route geometries (a few megabytes), so keep it small.
ROUTE_CACHE = TTLCache(ttl_seconds=600, max_entries=32)
_request_lock = threading.Lock()


class ValhallaProvider:
    name = PROVIDER

    def __init__(self, base_url: str | None = None, costing: str | None = None):
        self.base_url = (base_url or settings.VALHALLA_BASE_URL).rstrip("/")
        self.costing = costing or settings.VALHALLA_COSTING

    def get_routes(self, origin: Point, destination: Point) -> RoutingResult:
        key = (self.base_url, self.costing, *_rounded(origin), *_rounded(destination))
        cached = ROUTE_CACHE.get(key)
        if cached is not None:
            return cached

        body = {
            "locations": [
                {"lat": origin[0], "lon": origin[1]},
                {"lat": destination[0], "lon": destination[1]},
            ],
            "costing": self.costing,
            "alternates": ALTERNATES,
            "units": "miles",
            "directions_type": "maneuvers",
        }
        with _request_lock:
            response = send(
                "POST",
                f"{self.base_url}/route",
                json=body,
                headers={"X-Client-Id": settings.VALHALLA_CLIENT_ID},
                provider=PROVIDER,
                unavailable_code="ROUTING_UNAVAILABLE",
                timeout_code="ROUTING_TIMEOUT",
            )
        if response.status_code != 200:
            raise _error_for(response)

        payload = read_json(response, provider=PROVIDER, unavailable_code="ROUTING_UNAVAILABLE")
        result = RoutingResult(
            routes=tuple(parse_routes(payload)),
            provider=PROVIDER,
            endpoint=urlsplit(self.base_url).hostname or self.base_url,
            costing=self.costing,
            fetched_at=datetime.now(UTC),
        )
        ROUTE_CACHE.set(key, result)
        return result


def parse_routes(payload: dict) -> list[ProviderRoute]:
    """Turn a Valhalla `/route` response (primary trip plus alternates) into routes."""
    try:
        trips = [payload["trip"], *(alt["trip"] for alt in payload.get("alternates") or [])]
        return [_parse_trip(trip) for trip in trips]
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamError(
            "The routing service returned a route that could not be read. Please try again.",
            provider=PROVIDER,
            code="ROUTING_UNAVAILABLE",
        ) from exc


def _parse_trip(trip: dict) -> ProviderRoute:
    legs = trip["legs"]
    if len(legs) != 1:  # one origin and one destination always produce a single leg
        raise ValueError(f"Expected one leg, got {len(legs)}.")
    leg = legs[0]
    points = decode_polyline(leg["shape"])
    duration = float(trip["summary"]["time"])
    if len(points) < 2 or duration <= 0:
        raise ValueError("Route has no usable geometry or duration.")
    distance = float(trip["summary"]["length"])
    if trip.get("units") == "kilometers":
        distance *= KM_TO_MILES
    maneuvers = tuple(
        Maneuver(
            seconds=float(maneuver["time"]),
            begin_index=int(maneuver["begin_shape_index"]),
            end_index=int(maneuver["end_shape_index"]),
        )
        for maneuver in leg.get("maneuvers") or []
    )
    return ProviderRoute(
        points=tuple(points),
        duration_seconds=duration,
        provider_distance_miles=distance,
        maneuvers=maneuvers,
    )


def _error_for(response) -> Exception:
    try:
        error_code = response.json().get("error_code")
    except (ValueError, AttributeError):
        error_code = None
    if error_code in NO_ROUTE_ERROR_CODES:
        return NoRouteError(
            "No drivable route was found between these places. Try nearby towns or cities."
        )
    if error_code == DISTANCE_LIMIT_ERROR_CODE:
        return NoRouteError("This trip is too long for the routing service. Try a shorter trip.")
    return UpstreamError(
        "The routing service is unavailable right now. Please try again shortly.",
        provider=PROVIDER,
        code="ROUTING_UNAVAILABLE",
    )


def _rounded(point: Point) -> tuple[float, float]:
    return (round(point[0], 4), round(point[1], 4))

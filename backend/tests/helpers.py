"""Test-only builders: synthetic geometry with known lengths and provider-shaped payloads."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from routing.geometry import EARTH_RADIUS_MILES

MILES_PER_DEGREE = EARTH_RADIUS_MILES * math.pi / 180  # one degree of latitude along a meridian


def encode_polyline(points: list[tuple[float, float]], precision: int = 6) -> str:
    """Encode (lat, lon) pairs the way Valhalla does (Google polyline, 1e6 precision)."""
    factor = 10**precision
    out: list[str] = []
    prev_lat = prev_lon = 0
    for lat, lon in points:
        lat_i, lon_i = round(lat * factor), round(lon * factor)
        for delta in (lat_i - prev_lat, lon_i - prev_lon):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lon = lat_i, lon_i
    return "".join(out)


def meridian_line(
    total_miles: float, points: int = 5, *, start_lat: float = 39.0, lon: float = -100.0
) -> list[tuple[float, float]]:
    """A due-north line of exactly `total_miles` with evenly spaced points."""
    step = total_miles / MILES_PER_DEGREE / (points - 1)
    return [(start_lat + i * step, lon) for i in range(points)]


def valhalla_trip(
    points: list[tuple[float, float]],
    *,
    seconds: float,
    maneuvers: list[dict] | None = None,
    miles: float | None = None,
) -> dict:
    """A Valhalla `trip` object for one leg. Default: one maneuver spanning the whole shape."""
    last = len(points) - 1
    if maneuvers is None:
        maneuvers = [
            {
                "time": seconds,
                "length": miles or 0.0,
                "begin_shape_index": 0,
                "end_shape_index": last,
            },
            {"time": 0.0, "length": 0.0, "begin_shape_index": last, "end_shape_index": last},
        ]
    return {
        "status": 0,
        "units": "miles",
        "summary": {"time": seconds, "length": miles or 0.0},
        "legs": [
            {
                "summary": {"time": seconds, "length": miles or 0.0},
                "maneuvers": maneuvers,
                "shape": encode_polyline(points),
            }
        ],
    }


def valhalla_response(*trips: dict) -> dict:
    return {"trip": trips[0], "alternates": [{"trip": trip} for trip in trips[1:]]}


def open_meteo_location(
    start: datetime,
    hours: int,
    *,
    wind: float | list | None = 5.0,
    gusts: float | list | None = 8.0,
    rain: float | list | None = 0.0,
    showers: float | list | None = 0.0,
    snowfall: float | list | None = 0.0,
    temperature: float | list | None = 40.0,
    weather_code: int | list | None = 1,
    units: dict | None = None,
    timezone: str = "America/Denver",
    utc_offset_seconds: int = -25200,
) -> dict:
    """One Open-Meteo location object with `hours` hourly values starting at `start` (UTC)."""

    def column(value):
        return list(value) if isinstance(value, list) else [value] * hours

    first = int(start.replace(tzinfo=start.tzinfo or UTC).timestamp())
    hourly_units = {
        "time": "unixtime",
        "wind_speed_10m": "mp/h",
        "wind_gusts_10m": "mp/h",
        "rain": "inch",
        "showers": "inch",
        "snowfall": "inch",
        "temperature_2m": "°F",
        "weather_code": "wmo code",
    }
    hourly_units.update(units or {})
    return {
        "latitude": 39.0,
        "longitude": -100.0,
        "utc_offset_seconds": utc_offset_seconds,
        "timezone": timezone,
        "timezone_abbreviation": "GMT-7",
        "hourly_units": hourly_units,
        "hourly": {
            "time": [first + 3600 * i for i in range(hours)],
            "wind_speed_10m": column(wind),
            "wind_gusts_10m": column(gusts),
            "rain": column(rain),
            "showers": column(showers),
            "snowfall": column(snowfall),
            "temperature_2m": column(temperature),
            "weather_code": column(weather_code),
        },
    }

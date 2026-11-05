"""Scripted weather for the labeled demo mode. This is NOT a forecast.

Real weather is often calm, which makes the risk rules impossible to demonstrate on demand. The
demo mode therefore replays a fixed, made-up scenario over the recorded Denver to Kansas City
routes. The weather is a pure function of place and hour of day (UTC), repeating every 24 hours, so
the demo gives the same answer every day and still changes with the departure time:

- An afternoon storm sits on I-70 in central Kansas (shared by Routes A and B) with wind in the
  45 to 55 mph band, heavy snow at its core and a ring of light rain. It peaks at 21:00 UTC.
- A weaker, dry wind system sits on US-36 (Route C) with wind in the 35 to 45 mph band, peaking
  at 23:00 UTC.

Both fade to nothing within six hours of their peak. Every response built from this module is
labeled as demo data by the analysis service.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from routing.geometry import haversine_miles

from .models import HourlySeries, PointKey, point_key

PROVIDER = "demo-scenario"
BACKGROUND_WIND_MPH = 9.0
MOUNTAIN_TIME_EAST_EDGE = -101.5  # approximate Mountain/Central boundary on this corridor


@dataclass(frozen=True)
class Storm:
    lat: float
    lon: float  # centre at the peak hour
    peak_hour_utc: float
    active_hours: float  # fades to zero this many hours either side of the peak
    radius_miles: float
    drift_lon_per_hour: float
    wind_gain_mph: float  # added to the background wind at the core, at the peak
    snow_in_per_hr: float
    rain_in_per_hr: float

    def strength(self, hour_of_day: float) -> float:
        """0 to 1: how developed the storm is at this hour of the (UTC) day."""
        from_peak = (hour_of_day - self.peak_hour_utc + 12) % 24 - 12
        if abs(from_peak) >= self.active_hours:
            return 0.0
        return math.cos(math.pi * from_peak / (2 * self.active_hours)) ** 2

    def distance_miles(self, lat: float, lon: float, hour_of_day: float) -> float:
        from_peak = (hour_of_day - self.peak_hour_utc + 12) % 24 - 12
        centre_lon = self.lon + self.drift_lon_per_hour * from_peak
        return haversine_miles(lat, lon, self.lat, centre_lon)

    def reach(self, distance_miles: float, *, spread: float = 1.0) -> float:
        """0 to 1: Gaussian fall-off with distance from the centre."""
        return math.exp(-((distance_miles / (self.radius_miles * spread)) ** 2) / 2)


STORMS = (
    Storm(38.87, -98.5, 21, 6, 30, 0.12, wind_gain_mph=42, snow_in_per_hr=1.6, rain_in_per_hr=0.14),
    Storm(39.80, -96.8, 23, 6, 25, 0.10, wind_gain_mph=31, snow_in_per_hr=0.0, rain_in_per_hr=0.0),
)


def weather_at(lat: float, lon: float, epoch: int) -> tuple[float, float, float, float, float, int]:
    """(wind mph, gust mph, rain in/h, snow in/h, temperature F, WMO code) at a place and hour."""
    hour_of_day = (epoch / 3600) % 24
    wind_gain = snow = rain = intensity = 0.0
    for storm in STORMS:
        strength = storm.strength(hour_of_day)
        if strength == 0.0:
            continue
        distance = storm.distance_miles(lat, lon, hour_of_day)
        core = strength * storm.reach(distance)
        wind_gain = max(wind_gain, storm.wind_gain_mph * core)
        snow = max(snow, storm.snow_in_per_hr * core)
        rain = max(rain, storm.rain_in_per_hr * strength * storm.reach(distance, spread=2.0))
        intensity = max(intensity, core)

    breeze = 2.0 * math.sin(2 * math.pi * hour_of_day / 24 + lon * 0.8)
    wind = round(BACKGROUND_WIND_MPH + breeze + wind_gain, 1)
    snow, rain = round(snow, 3), round(rain, 3)
    if snow >= 0.1:
        code = 73 if snow >= 0.5 else 71
    elif rain >= 0.1:
        code = 61
    else:
        code = 3 if intensity > 0.1 else 1
    return wind, round(wind * 1.4, 1), rain, snow, round(44.0 - 14.0 * intensity, 1), code


class ScenarioWeatherProvider:
    name = PROVIDER
    model = "scripted demo scenario (not a forecast)"

    def fetch_hourly(
        self, points: Iterable[tuple[float, float]], start: datetime, end: datetime
    ) -> dict[PointKey, HourlySeries]:
        first = int(start.timestamp()) // 3600 * 3600
        last = -(-int(end.timestamp()) // 3600) * 3600
        times = tuple(range(first, last + 1, 3600))
        generated_at = datetime.now(UTC)

        series: dict[PointKey, HourlySeries] = {}
        for key in dict.fromkeys(point_key(lat, lon) for lat, lon in points):
            columns = list(zip(*(weather_at(*key, epoch) for epoch in times), strict=True))
            wind, gust, rain, snow, temperature, code = columns or [()] * 6
            western = key[1] < MOUNTAIN_TIME_EAST_EDGE
            series[key] = HourlySeries(
                times=times,
                wind_mph=wind,
                wind_gust_mph=gust,
                rain_in_per_hr=rain,
                snow_in_per_hr=snow,
                temperature_f=temperature,
                weather_code=code,
                timezone="America/Denver" if western else "America/Chicago",
                utc_offset_seconds=None,
                fetched_at=generated_at,
            )
        return series

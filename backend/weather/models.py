"""Hourly forecast for one place, in the units the risk rules use."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import UTC, datetime

# A forecast hour stands for the 30 minutes either side of it. An ETA further than this from every
# hour in the series has no forecast: it is never extrapolated.
MAX_GAP_SECONDS = 1800

PointKey = tuple[float, float]  # (lat, lon) rounded to three decimals, about 110 m


def point_key(lat: float, lon: float) -> PointKey:
    return (round(lat, 3), round(lon, 3))


@dataclass(frozen=True)
class Observation:
    """The forecast for one hour. A measurement that the provider did not supply is None."""

    forecast_time: datetime
    wind_mph: float | None
    wind_gust_mph: float | None
    rain_in_per_hr: float | None
    snow_in_per_hr: float | None
    temperature_f: float | None
    weather_code: int | None


@dataclass(frozen=True)
class HourlySeries:
    """Columns are aligned with `times` (UTC epoch seconds, ascending, one per hour).

    Wind is the sustained 10 m speed in mph. Rain is rain plus showers and snow is snowfall, both
    as inches in the hour. Values keep the provider's precision (normalized to six decimals), so
    they can be compared with the risk thresholds exactly.
    """

    times: tuple[int, ...]
    wind_mph: tuple[float | None, ...]
    wind_gust_mph: tuple[float | None, ...]
    rain_in_per_hr: tuple[float | None, ...]
    snow_in_per_hr: tuple[float | None, ...]
    temperature_f: tuple[float | None, ...]
    weather_code: tuple[int | None, ...]
    timezone: str | None
    utc_offset_seconds: int | None
    fetched_at: datetime = field(compare=False)

    def nearest_index(self, epoch: float) -> int | None:
        """Index of the forecast hour nearest to `epoch`. A tie goes to the earlier hour."""
        upper = bisect_left(self.times, epoch)
        candidates = [i for i in (upper - 1, upper) if 0 <= i < len(self.times)]
        if not candidates:
            return None
        nearest = min(candidates, key=lambda i: (abs(self.times[i] - epoch), i))
        return nearest if abs(self.times[nearest] - epoch) <= MAX_GAP_SECONDS else None

    def observation(self, index: int) -> Observation:
        return Observation(
            forecast_time=datetime.fromtimestamp(self.times[index], UTC),
            wind_mph=self.wind_mph[index],
            wind_gust_mph=self.wind_gust_mph[index],
            rain_in_per_hr=self.rain_in_per_hr[index],
            snow_in_per_hr=self.snow_in_per_hr[index],
            temperature_f=self.temperature_f[index],
            weather_code=self.weather_code[index],
        )

"""Open-Meteo forecast client.

Points are deduplicated on three decimals, requested in batches with bounded concurrency, and
cached per point so that re-running a trip only asks for places it has not seen.
"""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from django.conf import settings

from common.cache import TTLCache
from common.errors import UpstreamError
from common.http import read_json, send

from .models import HourlySeries, PointKey, point_key
from .units import RAIN_TO_INCHES, SNOW_TO_INCHES, TEMPERATURE_TO_F, WIND_TO_MPH, Converter

PROVIDER = "open-meteo"
HOURLY_VARIABLES = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "rain",
    "showers",
    "snowfall",
    "temperature_2m",
    "weather_code",
)
BATCH_SIZE = 50
MAX_CONCURRENT_REQUESTS = 4
FORECAST_HORIZON_DAYS = 15  # the API accepts dates up to today (UTC) plus 15 days
RISK_DECIMALS = 3

# About four full-size analyses. Each entry is one place's hourly series (tens of kilobytes).
FORECAST_CACHE = TTLCache(ttl_seconds=600, max_entries=2048)


class OpenMeteoProvider:
    name = PROVIDER
    model = "best_match"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.OPEN_METEO_BASE_URL).rstrip("/")

    def fetch_hourly(
        self, points: Iterable[tuple[float, float]], start: datetime, end: datetime
    ) -> dict[PointKey, HourlySeries]:
        """Hourly forecast covering `start` to `end` for every point, keyed by rounded point.

        Hours beyond the provider's forecast horizon are simply absent from the series.
        """
        window = _date_window(start, end)
        keys = list(dict.fromkeys(point_key(lat, lon) for lat, lon in points))

        series: dict[PointKey, HourlySeries] = {}
        missing: list[PointKey] = []
        for key in keys:
            cached = FORECAST_CACHE.get((self.base_url, key, window))
            if cached is None:
                missing.append(key)
            else:
                series[key] = cached

        batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        if batches:
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as pool:
                fetched = pool.map(lambda batch: self._fetch_batch(batch, window), batches)
                for batch, batch_series in zip(batches, fetched, strict=True):
                    for key, point_series in zip(batch, batch_series, strict=True):
                        FORECAST_CACHE.set((self.base_url, key, window), point_series)
                        series[key] = point_series
        return {key: series[key] for key in keys}

    def _fetch_batch(self, batch: list[PointKey], window: tuple[str, str]) -> list[HourlySeries]:
        response = send(
            "GET",
            f"{self.base_url}/v1/forecast",
            params={
                "latitude": ",".join(f"{lat:.3f}" for lat, _ in batch),
                "longitude": ",".join(f"{lon:.3f}" for _, lon in batch),
                "hourly": ",".join(HOURLY_VARIABLES),
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "temperature_unit": "fahrenheit",
                "timeformat": "unixtime",
                "timezone": "auto",
                "start_date": window[0],
                "end_date": window[1],
            },
            provider=PROVIDER,
            unavailable_code="WEATHER_UNAVAILABLE",
            timeout_code="WEATHER_TIMEOUT",
        )
        if response.status_code == 429:
            raise _unavailable("is busy. Please wait a minute and try again.")
        if response.status_code != 200:
            raise _unavailable("is unavailable right now. Please try again shortly.")

        payload = read_json(response, provider=PROVIDER, unavailable_code="WEATHER_UNAVAILABLE")
        locations = payload if isinstance(payload, list) else [payload]
        fetched_at = datetime.now(UTC)
        try:
            if len(locations) != len(batch):
                raise ValueError(f"Expected {len(batch)} locations, got {len(locations)}.")
            return [parse_location(location, fetched_at) for location in locations]
        except (KeyError, TypeError, ValueError) as exc:
            raise _unavailable("returned a forecast that could not be read.") from exc


def parse_location(location: dict, fetched_at: datetime) -> HourlySeries:
    """Validate units and convert one Open-Meteo location object into an `HourlySeries`."""
    hourly, units = location["hourly"], location["hourly_units"]
    if units.get("time") != "unixtime":
        raise ValueError(f"Unexpected time format {units.get('time')!r}.")
    times = tuple(int(value) for value in hourly["time"])

    def column(name: str, converters: dict[str, Converter], *, required: bool):
        convert = converters.get(units.get(name))
        values = hourly[name]
        if len(values) != len(times):
            raise ValueError(f"{name} has {len(values)} values for {len(times)} hours.")
        if convert is None:
            if required:
                raise ValueError(f"Unexpected unit {units.get(name)!r} for {name}.")
            return (None,) * len(times)
        return tuple(
            None if value is None else round(convert(float(value)), RISK_DECIMALS)
            for value in values
        )

    rain = column("rain", RAIN_TO_INCHES, required=True)
    showers = column("showers", RAIN_TO_INCHES, required=True)
    codes = hourly["weather_code"]
    return HourlySeries(
        times=times,
        wind_mph=column("wind_speed_10m", WIND_TO_MPH, required=True),
        wind_gust_mph=column("wind_gusts_10m", WIND_TO_MPH, required=False),
        # Rain rate is rain plus showers. If either is unknown the rate is unknown, never partial.
        rain_in_per_hr=tuple(
            None if r is None or s is None else round(r + s, RISK_DECIMALS)
            for r, s in zip(rain, showers, strict=True)
        ),
        snow_in_per_hr=column("snowfall", SNOW_TO_INCHES, required=True),
        temperature_f=column("temperature_2m", TEMPERATURE_TO_F, required=False),
        weather_code=tuple(None if code is None else int(code) for code in codes),
        timezone=location.get("timezone"),
        utc_offset_seconds=location.get("utc_offset_seconds"),
        fetched_at=fetched_at,
    )


def _date_window(start: datetime, end: datetime) -> tuple[str, str]:
    """Calendar dates to request. With `timezone=auto` the dates are local to each place, so one
    day of padding on each side guarantees the UTC window is covered in every time zone."""
    first = start.astimezone(UTC).date() - timedelta(days=1)
    horizon = datetime.now(UTC).date() + timedelta(days=FORECAST_HORIZON_DAYS)
    last = min(end.astimezone(UTC).date() + timedelta(days=1), horizon)
    return (first.isoformat(), last.isoformat())


def _unavailable(problem: str) -> UpstreamError:
    return UpstreamError(
        f"The weather service {problem}", provider=PROVIDER, code="WEATHER_UNAVAILABLE"
    )

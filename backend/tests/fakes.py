"""In-memory routing and weather providers for service tests. They implement the same interface
as the real clients, so the analysis service runs its real code against known inputs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from common.errors import UpstreamError
from routing.providers.base import ProviderRoute, RoutingResult
from tests.helpers import meridian_line
from weather.models import HourlySeries, point_key

CALM = {"wind": 5.0, "gust": 9.0, "rain": 0.0, "snow": 0.0, "temperature": 40.0, "code": 1}


def straight_route(
    miles: float, *, hours: float, lon: float = -100.0, points: int | None = None
) -> ProviderRoute:
    """A due-north route of exactly `miles`, driven at constant speed in `hours`."""
    line = meridian_line(miles, points=points or int(miles // 5) + 1, lon=lon)
    return ProviderRoute(
        points=tuple(line),
        duration_seconds=hours * 3600,
        provider_distance_miles=miles,
        maneuvers=(),
    )


class FakeRouting:
    name = "valhalla"

    def __init__(self, *routes: ProviderRoute):
        self.routes = routes
        self.requests: list[tuple] = []

    def get_routes(self, origin, destination) -> RoutingResult:
        self.requests.append((origin, destination))
        return RoutingResult(
            routes=self.routes,
            provider="valhalla",
            endpoint="routing.test",
            costing="auto",
            fetched_at=datetime(2026, 11, 6, 14, 59, tzinfo=UTC),
        )


class FakeWeather:
    """Hourly weather from `conditions(lat, lon, hour)`, which returns overrides of `CALM`."""

    name = "open-meteo"
    model = "best_match"

    def __init__(
        self,
        conditions: Callable[[float, float, datetime], dict] | None = None,
        *,
        first_hour: datetime = datetime(2026, 11, 6, 12, 0, tzinfo=UTC),
        hours: int = 96,
        timezone: str = "America/Chicago",
        fail_on_calls: tuple[int, ...] = (),
    ):
        self.conditions = conditions or (lambda lat, lon, hour: {})
        self.first_hour = first_hour
        self.hours = hours
        self.timezone = timezone
        self.fail_on_calls = fail_on_calls
        self.calls: list[dict] = []

    def fetch_hourly(self, points, start, end) -> dict:
        points = list(points)
        self.calls.append({"points": points, "start": start, "end": end})
        if len(self.calls) in self.fail_on_calls:
            raise UpstreamError(
                "The weather service is unavailable right now.",
                provider="open-meteo",
                code="WEATHER_UNAVAILABLE",
            )
        first = int(self.first_hour.timestamp())
        times = tuple(first + 3600 * i for i in range(self.hours))
        series = {}
        for lat, lon in points:
            rows = [
                {**CALM, **self.conditions(lat, lon, datetime.fromtimestamp(epoch, UTC))}
                for epoch in times
            ]
            series[point_key(lat, lon)] = HourlySeries(
                times=times,
                wind_mph=tuple(row["wind"] for row in rows),
                wind_gust_mph=tuple(row["gust"] for row in rows),
                rain_in_per_hr=tuple(row["rain"] for row in rows),
                snow_in_per_hr=tuple(row["snow"] for row in rows),
                temperature_f=tuple(row["temperature"] for row in rows),
                weather_code=tuple(row["code"] for row in rows),
                timezone=self.timezone,
                utc_offset_seconds=-21600,
                fetched_at=datetime(2026, 11, 6, 14, 58, tzinfo=UTC),
            )
        return series

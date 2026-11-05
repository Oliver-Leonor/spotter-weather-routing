"""Routing provider contract. Valhalla is the implementation; another router only needs this."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ..geometry import Point


@dataclass(frozen=True)
class Maneuver:
    """Driving time for a run of shape points (`begin_index` to `end_index`, inclusive)."""

    seconds: float
    begin_index: int
    end_index: int


@dataclass(frozen=True)
class ProviderRoute:
    points: tuple[Point, ...]
    duration_seconds: float
    provider_distance_miles: float
    maneuvers: tuple[Maneuver, ...]


@dataclass(frozen=True)
class RoutingResult:
    routes: tuple[ProviderRoute, ...]
    provider: str
    endpoint: str
    costing: str
    fetched_at: datetime


class RouteProvider(Protocol):
    def get_routes(self, origin: Point, destination: Point) -> RoutingResult:
        """Route options, best first. Raises `NoRouteError` or `UpstreamError`."""
        ...

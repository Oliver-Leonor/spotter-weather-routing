"""Routes replayed from a recorded Valhalla response. Used only by the labeled demo mode.

The recording is a real response for one trip (Denver to Kansas City), trimmed to the fields the
parser reads. It goes through the same parser as live responses.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import cached_property
from pathlib import Path

from ..geometry import Point
from .base import RoutingResult
from .valhalla import PROVIDER, parse_routes

RECORDING_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "denver_kansas_city.json"


class RecordedRouteProvider:
    name = PROVIDER

    def __init__(self, path: Path = RECORDING_PATH):
        self._path = path

    @cached_property
    def _payload(self) -> dict:
        return json.loads(self._path.read_text())

    @property
    def _recording(self) -> dict:
        return self._payload["_recording"]

    @property
    def origin(self) -> Point:
        return (self._recording["origin"]["lat"], self._recording["origin"]["lon"])

    @property
    def destination(self) -> Point:
        return (self._recording["destination"]["lat"], self._recording["destination"]["lon"])

    @property
    def origin_label(self) -> str:
        return self._recording["origin"]["label"]

    @property
    def destination_label(self) -> str:
        return self._recording["destination"]["label"]

    @property
    def recorded_at(self) -> datetime:
        return datetime.fromisoformat(self._recording["recorded_at"])

    def get_routes(self, origin: Point, destination: Point) -> RoutingResult:
        """Always the recorded trip; the requested places are not used."""
        return RoutingResult(
            routes=tuple(parse_routes(self._payload)),
            provider=PROVIDER,
            endpoint=self._recording["endpoint"],
            costing=self._recording["request"]["costing"],
            fetched_at=self.recorded_at,
        )

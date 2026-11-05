"""Checkpoint placement and mileage attribution (spec section 8.1). Pure functions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .geometry import Point, point_at

# A checkpoint closer to the destination than this share of the interval is dropped in favour of
# the destination itself, so the route never ends with two samples on top of each other.
MIN_FINAL_GAP_FRACTION = 0.10


@dataclass(frozen=True)
class SamplePoint:
    index: int
    kind: str  # "origin" | "checkpoint" | "destination"
    lat: float
    lon: float
    distance_miles: float
    attributed_miles: float


def checkpoint_distances(total_miles: float, interval_miles: float) -> list[float]:
    """Miles along the route of every sample: origin, each multiple of the interval, destination."""
    if total_miles <= 0:
        raise ValueError("A route must have a positive length.")
    min_final_gap = interval_miles * MIN_FINAL_GAP_FRACTION
    distances = [0.0]
    multiple = 1
    while total_miles - multiple * interval_miles >= min_final_gap:
        distances.append(float(multiple * interval_miles))
        multiple += 1
    distances.append(total_miles)
    return distances


def attribute_miles(distances: Sequence[float]) -> list[float]:
    """Miles owned by each sample: every mile belongs to its nearest sample along the route.

    Segments are split at their midpoint, so the origin and destination own half of their only
    segment and the attributed miles always add up to the route length.
    """
    midpoints = [(a + b) / 2 for a, b in zip(distances, distances[1:], strict=False)]
    bounds = [distances[0], *midpoints, distances[-1]]
    return [upper - lower for lower, upper in zip(bounds, bounds[1:], strict=False)]


def sample_route(
    points: Sequence[Point], cumulative: Sequence[float], interval_miles: float
) -> list[SamplePoint]:
    distances = checkpoint_distances(cumulative[-1], interval_miles)
    attributed = attribute_miles(distances)
    last = len(distances) - 1
    samples = []
    for index, (distance, miles) in enumerate(zip(distances, attributed, strict=True)):
        lat, lon = point_at(points, cumulative, distance)
        kind = "origin" if index == 0 else "destination" if index == last else "checkpoint"
        samples.append(SamplePoint(index, kind, lat, lon, distance, miles))
    return samples

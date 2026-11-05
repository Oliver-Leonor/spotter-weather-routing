"""Route geometry: polyline decoding, great-circle distances, interpolation and simplification.

Pure functions. A point is a `(lat, lon)` pair in degrees; distances are statute miles.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence

EARTH_RADIUS_MILES = 3958.7613  # mean Earth radius (6371.0088 km)
MILES_PER_DEGREE = EARTH_RADIUS_MILES * math.pi / 180

Point = tuple[float, float]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    half_dphi = (phi2 - phi1) / 2
    half_dlambda = math.radians(lon2 - lon1) / 2
    h = math.sin(half_dphi) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(half_dlambda) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(h)))


def decode_polyline(encoded: str, precision: int = 6) -> list[Point]:
    """Decode a Google-style encoded polyline. Valhalla uses six decimal places."""
    factor = 10**precision
    points: list[Point] = []
    lat = lon = 0
    position, length = 0, len(encoded)
    try:
        while position < length:
            deltas = []
            for _ in range(2):
                shift = result = 0
                while True:
                    chunk = ord(encoded[position]) - 63
                    position += 1
                    result |= (chunk & 0x1F) << shift
                    shift += 5
                    if chunk < 0x20:
                        break
                deltas.append(~(result >> 1) if result & 1 else result >> 1)
            lat += deltas[0]
            lon += deltas[1]
            points.append((lat / factor, lon / factor))
    except IndexError as exc:
        raise ValueError("Encoded polyline is truncated.") from exc
    return points


def cumulative_miles(points: Sequence[Point]) -> list[float]:
    """Distance from the first point to every point, summed segment by segment."""
    distances = [0.0]
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:], strict=False):
        distances.append(distances[-1] + haversine_miles(lat1, lon1, lat2, lon2))
    return distances


def point_at(points: Sequence[Point], cumulative: Sequence[float], miles: float) -> Point:
    """The position `miles` along the line, interpolated inside the containing segment."""
    if miles <= 0:
        return points[0]
    if miles >= cumulative[-1]:
        return points[-1]
    upper = bisect_right(cumulative, miles)
    lower = upper - 1
    span = cumulative[upper] - cumulative[lower]
    fraction = (miles - cumulative[lower]) / span if span > 0 else 0.0
    (lat1, lon1), (lat2, lon2) = points[lower], points[upper]
    return (lat1 + (lat2 - lat1) * fraction, lon1 + (lon2 - lon1) * fraction)


def simplify(points: Sequence[Point], tolerance_miles: float) -> list[Point]:
    """Douglas-Peucker simplification for display. Endpoints are always kept."""
    if len(points) <= 2:
        return list(points)
    mid_latitude = math.radians((points[0][0] + points[-1][0]) / 2)
    x_scale = MILES_PER_DEGREE * math.cos(mid_latitude)
    flat = [(lon * x_scale, lat * MILES_PER_DEGREE) for lat, lon in points]
    tolerance_sq = tolerance_miles**2

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        ax, ay = flat[first]
        dx, dy = flat[last][0] - ax, flat[last][1] - ay
        segment_sq = dx * dx + dy * dy
        farthest, farthest_sq = -1, tolerance_sq
        for i in range(first + 1, last):
            px, py = flat[i][0] - ax, flat[i][1] - ay
            t = 0.0 if segment_sq == 0 else max(0.0, min(1.0, (px * dx + py * dy) / segment_sq))
            distance_sq = (px - t * dx) ** 2 + (py - t * dy) ** 2
            if distance_sq > farthest_sq:
                farthest, farthest_sq = i, distance_sq
        if farthest != -1:
            keep[farthest] = True
            stack.append((first, farthest))
            stack.append((farthest, last))
    return [point for point, kept in zip(points, keep, strict=True) if kept]


def are_near_identical(
    points_a: Sequence[Point],
    cumulative_a: Sequence[float],
    points_b: Sequence[Point],
    cumulative_b: Sequence[float],
    *,
    samples: int = 50,
    tolerance_miles: float = 0.25,
    length_tolerance: float = 0.01,
) -> bool:
    """True when two routes follow the same roads.

    Routes match when their lengths agree within `length_tolerance` and the positions at the same
    fraction of the way along never differ by more than `tolerance_miles`. Such routes would be
    sampled at the same places and so carry the same weather exposure.
    """
    length_a, length_b = cumulative_a[-1], cumulative_b[-1]
    longer = max(length_a, length_b)
    if longer == 0:
        return True
    if abs(length_a - length_b) > length_tolerance * longer:
        return False
    for step in range(samples + 1):
        fraction = step / samples
        lat_a, lon_a = point_at(points_a, cumulative_a, fraction * length_a)
        lat_b, lon_b = point_at(points_b, cumulative_b, fraction * length_b)
        if haversine_miles(lat_a, lon_a, lat_b, lon_b) > tolerance_miles:
            return False
    return True

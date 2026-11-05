"""Elapsed driving time along a route (spec section 9). Pure functions.

The provider reports a duration per maneuver together with the shape points it covers. Elapsed time
is accumulated maneuver by maneuver and interpolated by distance inside a maneuver. When the
maneuvers cannot be trusted, time falls back to being proportional to distance over the whole route.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence

from .providers.base import Maneuver


def elapsed_profile(
    cumulative: Sequence[float], maneuvers: Sequence[Maneuver], duration_seconds: float
) -> list[float]:
    """Elapsed seconds at every shape point, ending at `duration_seconds`."""
    profile = _profile_from_maneuvers(cumulative, maneuvers, duration_seconds)
    if profile is not None:
        return profile
    total = cumulative[-1]
    return [duration_seconds * (miles / total if total > 0 else 1.0) for miles in cumulative]


def elapsed_at(cumulative: Sequence[float], profile: Sequence[float], miles: float) -> float:
    """Elapsed seconds after driving `miles`, interpolated between shape points."""
    if miles <= 0:
        return profile[0]
    if miles >= cumulative[-1]:
        return profile[-1]
    upper = bisect_right(cumulative, miles)
    lower = upper - 1
    span = cumulative[upper] - cumulative[lower]
    fraction = (miles - cumulative[lower]) / span if span > 0 else 0.0
    return profile[lower] + (profile[upper] - profile[lower]) * fraction


def _profile_from_maneuvers(
    cumulative: Sequence[float], maneuvers: Sequence[Maneuver], duration_seconds: float
) -> list[float] | None:
    last = len(cumulative) - 1
    if not _covers_whole_shape(maneuvers, last):
        return None
    total_seconds = sum(maneuver.seconds for maneuver in maneuvers)
    if total_seconds <= 0:
        return None
    # Keep the profile consistent with the route duration shown to the driver.
    scale = duration_seconds / total_seconds if duration_seconds > 0 else 1.0

    profile = [0.0] * len(cumulative)
    started = 0.0
    for maneuver in maneuvers:
        begin, end = maneuver.begin_index, maneuver.end_index
        seconds = maneuver.seconds * scale
        span = cumulative[end] - cumulative[begin]
        for i in range(begin, end + 1):
            if span > 0:
                fraction = (cumulative[i] - cumulative[begin]) / span
            else:
                fraction = 1.0 if i == end else 0.0
            profile[i] = started + seconds * fraction
        started += seconds
    return profile


def _covers_whole_shape(maneuvers: Sequence[Maneuver], last_index: int) -> bool:
    """Maneuvers must run from the first shape point to the last with no gaps or negative times."""
    if not maneuvers or maneuvers[0].begin_index != 0 or maneuvers[-1].end_index != last_index:
        return False
    previous_end = 0
    for maneuver in maneuvers:
        if maneuver.begin_index != previous_end or maneuver.end_index < maneuver.begin_index:
            return False
        if maneuver.end_index > last_index:
            return False
        if not math.isfinite(maneuver.seconds) or maneuver.seconds < 0:
            return False
        previous_end = maneuver.end_index
    return True

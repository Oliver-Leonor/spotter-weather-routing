"""Route-level risk from per-checkpoint levels (spec sections 7 and 8.1). Pure functions.

Each checkpoint owns the miles nearest to it (see `routing.sampling.attribute_miles`), so a route's
risk mileage is the sum of the miles owned by checkpoints at each level. It is never the number of
checkpoints multiplied by the interval.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .levels import RiskLevel

MILES_DECIMALS = 1
AVERAGE_DECIMALS = 3

STATUS_OK = "ok"
STATUS_BLOCKED = "blocked"  # at least one No Travel checkpoint: never recommended
STATUS_UNVERIFIED = "unverified"  # at least one checkpoint without a usable forecast


@dataclass(frozen=True)
class RouteSummary:
    no_travel_miles: float
    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    unknown_miles: float
    average_risk: float | None  # miles-weighted mean level (0 to 4) over the known miles
    coverage_complete: bool
    max_level: RiskLevel | None
    status: str

    def to_dict(self) -> dict:
        return {
            "no_travel_miles": self.no_travel_miles,
            "severe_miles": self.severe_miles,
            "high_miles": self.high_miles,
            "moderate_miles": self.moderate_miles,
            "low_miles": self.low_miles,
            "unknown_miles": self.unknown_miles,
            "average_risk": self.average_risk,
            "coverage_complete": self.coverage_complete,
            "max_level": self.max_level.slug if self.max_level is not None else "unknown",
        }


def summarize(checkpoints: Sequence[tuple[RiskLevel | None, float]]) -> RouteSummary:
    """Summarize `(level, attributed_miles)` pairs. A level of None is an unknown checkpoint."""
    if not checkpoints:
        raise ValueError("A route needs at least one checkpoint.")

    miles_by_level = dict.fromkeys(RiskLevel, 0.0)
    unknown_miles = 0.0
    for level, miles in checkpoints:
        if level is None:
            unknown_miles += miles
        else:
            miles_by_level[level] += miles

    known_levels = [level for level, _ in checkpoints if level is not None]
    known_miles = sum(miles_by_level.values())
    weighted = sum(int(level) * miles for level, miles in miles_by_level.items())

    # Status is decided by the checkpoint levels themselves, not by rounded mileage, so a No Travel
    # checkpoint that owns a fraction of a mile still blocks the route.
    if RiskLevel.NO_TRAVEL in known_levels:
        status = STATUS_BLOCKED
    elif len(known_levels) < len(checkpoints):
        status = STATUS_UNVERIFIED
    else:
        status = STATUS_OK

    def miles(level: RiskLevel) -> float:
        return round(miles_by_level[level], MILES_DECIMALS)

    return RouteSummary(
        no_travel_miles=miles(RiskLevel.NO_TRAVEL),
        severe_miles=miles(RiskLevel.SEVERE),
        high_miles=miles(RiskLevel.HIGH),
        moderate_miles=miles(RiskLevel.MODERATE),
        low_miles=miles(RiskLevel.LOW),
        unknown_miles=round(unknown_miles, MILES_DECIMALS),
        average_risk=round(weighted / known_miles, AVERAGE_DECIMALS) if known_miles > 0 else None,
        coverage_complete=len(known_levels) == len(checkpoints),
        max_level=max(known_levels) if known_levels else None,
        status=status,
    )

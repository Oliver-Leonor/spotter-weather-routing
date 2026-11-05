"""Spotter weather risk classification.

Pure, deterministic functions. Units: wind in mph (sustained), rain and snow in inches per hour,
load in pounds (cargo weight).

Boundary convention: every "X to below Y" band is the half-open interval [X, Y). A value equal to a
shared boundary belongs to the more severe band. "Above N" thresholds are strict (> N). Load rule
comparisons are strict (> 30,000 lb, > 40,000 lb).

Missing or invalid measurements (None, NaN, negative) never classify as Low. Precedence:

1. If any *available* measurement conclusively establishes No Travel (wind >= 55 mph, the
   45 to 55 mph load rule, rain > 1.00 in/h, snow > 3.0 in/h), the checkpoint is No Travel. Missing
   data cannot make a prohibited condition less dangerous. The gaps are still reported in `missing`.
2. Otherwise, if any measurement is missing, the level is None ("unknown"): a known Severe wind with
   missing rain is not conclusive because the rain could raise the level. `is_unknown` is True.
3. Otherwise the level is the highest severity among wind (after load rules), rain and snow.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .levels import RiskLevel

WIND_BANDS: tuple[tuple[float, RiskLevel], ...] = (
    (55.0, RiskLevel.NO_TRAVEL),
    (45.0, RiskLevel.SEVERE),
    (35.0, RiskLevel.HIGH),
    (25.0, RiskLevel.MODERATE),
)
LOAD_RULE_2_LB = 30_000  # strict >: 45 <= wind < 55 and load > 30,000 lb -> No Travel
LOAD_RULE_3_LB = 40_000  # strict >: 35 <= wind < 45 and load > 40,000 lb -> Severe


def _is_missing(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or value < 0


def classify_wind(mph: float) -> RiskLevel:
    for lower_bound, level in WIND_BANDS:
        if mph >= lower_bound:
            return level
    return RiskLevel.LOW


def classify_rain(inches_per_hour: float) -> RiskLevel:
    if inches_per_hour > 1.00:
        return RiskLevel.NO_TRAVEL
    if inches_per_hour >= 0.50:
        return RiskLevel.SEVERE
    if inches_per_hour >= 0.25:
        return RiskLevel.HIGH
    if inches_per_hour >= 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_snow(inches_per_hour: float) -> RiskLevel:
    if inches_per_hour > 3.0:
        return RiskLevel.NO_TRAVEL
    if inches_per_hour >= 2.0:
        return RiskLevel.SEVERE
    if inches_per_hour >= 1.0:
        return RiskLevel.HIGH
    if inches_per_hour >= 0.5:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def apply_load_rules(
    wind_mph: float, wind_level: RiskLevel, load_lb: float
) -> tuple[RiskLevel, str | None]:
    """Return the wind level after Spotter's load-dependent rules and the rule that fired."""
    if wind_mph >= 55.0:
        return RiskLevel.NO_TRAVEL, "wind_no_travel"
    if 45.0 <= wind_mph < 55.0 and load_lb > LOAD_RULE_2_LB:
        return RiskLevel.NO_TRAVEL, "load_rule_2"
    if 35.0 <= wind_mph < 45.0 and load_lb > LOAD_RULE_3_LB:
        return RiskLevel.SEVERE, "load_rule_3"
    return wind_level, None


@dataclass(frozen=True)
class CheckpointRisk:
    level: RiskLevel | None
    wind_level: RiskLevel | None
    rain_level: RiskLevel | None
    snow_level: RiskLevel | None
    load_rule_applied: str | None
    drivers: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def is_unknown(self) -> bool:
        return self.level is None

    @property
    def is_complete(self) -> bool:
        return not self.missing

    @property
    def value(self) -> int | None:
        return None if self.level is None else int(self.level)

    def to_dict(self) -> dict:
        def slug(level: RiskLevel | None) -> str | None:
            return None if level is None else level.slug

        return {
            "level": slug(self.level) if self.level is not None else "unknown",
            "value": self.value,
            "drivers": list(self.drivers),
            "wind_level": slug(self.wind_level),
            "rain_level": slug(self.rain_level),
            "snow_level": slug(self.snow_level),
            "load_rule_applied": self.load_rule_applied,
            "missing": list(self.missing),
        }


def classify_checkpoint(
    *,
    wind_mph: float | None,
    rain_in_per_hr: float | None,
    snow_in_per_hr: float | None,
    load_lb: float,
) -> CheckpointRisk:
    """Combine wind (with load rules), rain and snow into the final checkpoint risk.

    The final level is the highest severity among the three conditions. `drivers` lists every
    condition that reached the final level, in the order wind, rain, snow, plus the load rule name
    when a load rule set the wind level. See the module docstring for the missing-data precedence.
    """
    wind_missing = _is_missing(wind_mph)
    rain_missing = _is_missing(rain_in_per_hr)
    snow_missing = _is_missing(snow_in_per_hr)
    missing = [
        name
        for name, absent in (("wind", wind_missing), ("rain", rain_missing), ("snow", snow_missing))
        if absent
    ]

    wind_level: RiskLevel | None = None
    load_rule: str | None = None
    if not wind_missing:
        base_wind = classify_wind(wind_mph)
        wind_level, load_rule = apply_load_rules(wind_mph, base_wind, load_lb)
    rain_level = None if rain_missing else classify_rain(rain_in_per_hr)
    snow_level = None if snow_missing else classify_snow(snow_in_per_hr)

    known_levels = [lvl for lvl in (wind_level, rain_level, snow_level) if lvl is not None]
    conclusive_no_travel = RiskLevel.NO_TRAVEL in known_levels

    if missing and not conclusive_no_travel:
        return CheckpointRisk(
            level=None,
            wind_level=wind_level,
            rain_level=rain_level,
            snow_level=snow_level,
            load_rule_applied=load_rule,
            drivers=[],
            missing=missing,
        )

    final = max(known_levels)
    drivers: list[str] = []
    if wind_level == final:
        drivers.append("wind")
        if load_rule in {"load_rule_2", "load_rule_3"}:
            drivers.append(load_rule)
    if rain_level == final:
        drivers.append("rain")
    if snow_level == final:
        drivers.append("snow")
    return CheckpointRisk(
        level=final,
        wind_level=wind_level,
        rain_level=rain_level,
        snow_level=snow_level,
        load_rule_applied=load_rule,
        drivers=drivers,
        missing=missing,
    )

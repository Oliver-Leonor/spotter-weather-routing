"""Route recommendation (spec section 8). Pure functions.

Only routes with status "ok" are eligible: a blocked route (any No Travel checkpoint) or an
unverified one (any checkpoint without a usable forecast) is never recommended. Eligible routes are
ordered by a plain lexicographic comparison, with no weighting:

1. fewest Severe miles
2. fewest High miles
3. lowest average risk
4. shortest duration

Miles are compared at 0.1 and average risk at 0.001 so floating-point noise cannot decide. A
complete tie falls back to the route id, which is the routing provider's own order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .aggregation import AVERAGE_DECIMALS, MILES_DECIMALS, STATUS_BLOCKED, STATUS_OK


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    name: str
    status: str
    severe_miles: float
    high_miles: float
    average_risk: float | None
    duration_seconds: float
    issue: str | None = None  # for excluded routes: what blocks it or why it is unverified


@dataclass(frozen=True)
class Recommendation:
    route_id: str | None
    explanation: str
    ranking: tuple[str, ...]  # eligible routes only, best first
    blocked_route_ids: tuple[str, ...]
    unverified_route_ids: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "route_id": self.route_id,
            "explanation": self.explanation,
            "ranking": list(self.ranking),
            "blocked_route_ids": list(self.blocked_route_ids),
            "unverified_route_ids": list(self.unverified_route_ids),
        }


def recommend(routes: Sequence[RouteCandidate]) -> Recommendation:
    eligible = sorted((r for r in routes if r.status == STATUS_OK), key=_sort_key)
    excluded = [r for r in routes if r.status != STATUS_OK]
    blocked = tuple(r.route_id for r in excluded if r.status == STATUS_BLOCKED)
    unverified = tuple(r.route_id for r in excluded if r.status != STATUS_BLOCKED)
    exclusion_notes = [_exclusion_note(r) for r in excluded]

    if not eligible:
        explanation = " ".join(["No safe route is currently recommended.", *exclusion_notes])
        return Recommendation(None, explanation, (), blocked, unverified)

    winner = eligible[0]
    if len(eligible) > 1:
        # The main reason compares the winner with the runner-up; every other eligible route gets
        # a short sentence, so a faster route that lost on weather is always accounted for.
        also_ahead = [_also_ahead(winner, other) for other in eligible[2:]]
        reason = " ".join([_comparison(winner, eligible[1]), *also_ahead])
    elif excluded:
        reason = (
            f"{winner.name} is recommended because it is the only route that is neither blocked "
            "nor unverified."
        )
    else:
        reason = (
            f"{winner.name} is the only route the routing provider returned, and it has no "
            "No Travel conditions or unverified weather."
        )
    return Recommendation(
        route_id=winner.route_id,
        explanation=" ".join([reason, *exclusion_notes]),
        ranking=tuple(r.route_id for r in eligible),
        blocked_route_ids=blocked,
        unverified_route_ids=unverified,
    )


def _sort_key(route: RouteCandidate) -> tuple:
    return (
        round(route.severe_miles, MILES_DECIMALS),
        round(route.high_miles, MILES_DECIMALS),
        round(route.average_risk, AVERAGE_DECIMALS),
        round(route.duration_seconds),
        route.route_id,
    )


def _comparison(winner: RouteCandidate, other: RouteCandidate) -> str:
    """Name the first criterion that separates the winner from the next-best eligible route."""
    severe, high, average = _sort_key(winner)[:3]
    other_severe, other_high, other_average = _sort_key(other)[:3]
    extra_seconds = round(winner.duration_seconds) - round(other.duration_seconds)
    name = winner.name

    if severe != other_severe:
        fewer = _fewer_miles(severe, other_severe, "severe weather", other.name)
        return f"{name} is recommended because it {fewer}{_time_clause(extra_seconds)}."
    if high != other_high:
        fewer = _fewer_miles(high, other_high, "high-risk weather", other.name)
        return (
            f"{name} is recommended because it {fewer}{_time_clause(extra_seconds)}. "
            f"Severe-weather miles are tied at {severe:.1f}."
        )
    if average != other_average:
        return (
            f"{name} is recommended because it has the lower average weather risk "
            f"({average:.3f} vs {other_average:.3f} for {other.name})"
            f"{_time_clause(extra_seconds)}. Severe and high-risk miles are tied."
        )
    if extra_seconds != 0:
        return (
            f"{name} is recommended because it is {_duration_text(extra_seconds)} faster than "
            f"{other.name}. Severe miles, high-risk miles and average risk are tied."
        )
    return (
        f"{name} is recommended. It ties with {other.name} on weather risk and travel time, "
        "so the routing provider's order decides."
    )


def _also_ahead(winner: RouteCandidate, other: RouteCandidate) -> str:
    """One sentence on the first criterion that puts the winner ahead of a lower-ranked route."""
    severe, high, average = _sort_key(winner)[:3]
    other_severe, other_high, other_average = _sort_key(other)[:3]
    if severe != other_severe:
        fewer = f"{other_severe - severe:.1f} fewer miles of severe weather"
        return f"It also has {fewer} than {other.name}."
    if high != other_high:
        fewer = f"{other_high - high:.1f} fewer miles of high-risk weather"
        return f"It also has {fewer} than {other.name}."
    if average != other_average:
        return (
            f"It also has a lower average weather risk than {other.name} "
            f"({average:.3f} vs {other_average:.3f})."
        )
    saved_seconds = round(other.duration_seconds) - round(winner.duration_seconds)
    if saved_seconds != 0:
        return f"It is also {_duration_text(saved_seconds)} faster than {other.name}."
    return f"It also ties with {other.name}."


def _fewer_miles(mine: float, theirs: float, what: str, other_name: str) -> str:
    if mine == 0:
        return f"avoids {theirs:.1f} miles of {what} encountered on {other_name}"
    return (
        f"has {theirs - mine:.1f} fewer miles of {what} than {other_name} "
        f"({mine:.1f} vs {theirs:.1f} miles)"
    )


def _time_clause(extra_seconds: float) -> str:
    """How the winner's travel time compares with the route it beat on weather."""
    if extra_seconds == 0:
        return ", with the same travel time"
    if round(abs(extra_seconds) / 60) == 0:
        return ", with about the same travel time"
    if extra_seconds > 0:
        return f", despite adding {_duration_text(extra_seconds)} of travel time"
    return f", and it is also {_duration_text(extra_seconds)} faster"


def _duration_text(seconds: float) -> str:
    minutes = round(abs(seconds) / 60)
    if minutes == 0:
        return "less than a minute"
    return "1 minute" if minutes == 1 else f"{minutes} minutes"


def _exclusion_note(route: RouteCandidate) -> str:
    if route.status == STATUS_BLOCKED:
        return f"{route.name}: {route.issue or 'No Travel conditions on the route'}."
    issue = route.issue or "forecast unavailable for part of the route"
    return f"{route.name} could not be verified: {issue}."

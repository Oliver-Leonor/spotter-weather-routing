"""Route risk mileage and status from per-checkpoint levels (spec sections 7 and 8.1)."""

import pytest

from risk.aggregation import summarize
from risk.levels import RiskLevel

LOW, MOD, HIGH, SEV, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


def test_miles_are_summed_by_checkpoint_level():
    summary = summarize(
        [(LOW, 12.5), (LOW, 25.0), (MOD, 25.0), (HIGH, 25.0), (SEV, 17.5), (LOW, 5.0)]
    )
    assert summary.low_miles == 42.5
    assert summary.moderate_miles == 25.0
    assert summary.high_miles == 25.0
    assert summary.severe_miles == 17.5
    assert summary.no_travel_miles == 0.0
    assert summary.unknown_miles == 0.0


def test_fully_known_route_without_no_travel_is_ok():
    summary = summarize([(LOW, 30.0), (HIGH, 10.0)])
    assert (summary.status, summary.coverage_complete) == ("ok", True)
    assert summary.max_level is HIGH


def test_average_risk_is_weighted_by_attributed_miles():
    # (0 * 30 + 3 * 10) / 40
    assert summarize([(LOW, 30.0), (SEV, 10.0)]).average_risk == 0.75


def test_average_risk_ignores_unknown_miles():
    assert summarize([(LOW, 30.0), (SEV, 10.0), (None, 60.0)]).average_risk == 0.75


def test_unknown_checkpoint_makes_the_route_unverified_and_never_low():
    summary = summarize([(LOW, 30.0), (None, 20.0)])
    assert summary.status == "unverified"
    assert summary.coverage_complete is False
    assert (summary.unknown_miles, summary.low_miles) == (20.0, 30.0)


def test_no_travel_checkpoint_blocks_the_route():
    summary = summarize([(LOW, 30.0), (NT, 12.5)])
    assert summary.status == "blocked"
    assert summary.no_travel_miles == 12.5
    assert summary.max_level is NT


def test_no_travel_outranks_missing_forecasts():
    summary = summarize([(NT, 12.5), (None, 20.0)])
    assert summary.status == "blocked"
    assert summary.coverage_complete is False


def test_route_with_no_forecast_at_all_is_unverified_with_no_average():
    summary = summarize([(None, 10.0), (None, 10.0)])
    assert summary.status == "unverified"
    assert summary.average_risk is None
    assert summary.max_level is None
    assert summary.unknown_miles == 20.0


def test_status_comes_from_levels_not_from_rounded_miles():
    # 0.02 miles of No Travel rounds to 0.0 miles, but the route is still blocked.
    summary = summarize([(NT, 0.02), (LOW, 0.02)])
    assert summary.no_travel_miles == 0.0
    assert summary.status == "blocked"


def test_miles_round_to_a_tenth_and_average_to_a_thousandth():
    summary = summarize([(LOW, 10.04), (MOD, 5.02), (HIGH, 2.51)])
    assert (summary.low_miles, summary.moderate_miles, summary.high_miles) == (10.0, 5.0, 2.5)
    # (1 * 5.02 + 2 * 2.51) / 17.57 = 0.571428...
    assert summary.average_risk == 0.571


def test_summary_serializes_to_the_api_contract():
    assert summarize([(LOW, 30.0), (SEV, 10.0)]).to_dict() == {
        "no_travel_miles": 0.0,
        "severe_miles": 10.0,
        "high_miles": 0.0,
        "moderate_miles": 0.0,
        "low_miles": 30.0,
        "unknown_miles": 0.0,
        "average_risk": 0.75,
        "coverage_complete": True,
        "max_level": "severe",
    }


def test_max_level_serializes_as_unknown_when_nothing_is_known():
    assert summarize([(None, 10.0)]).to_dict()["max_level"] == "unknown"


def test_empty_route_is_rejected():
    with pytest.raises(ValueError):
        summarize([])

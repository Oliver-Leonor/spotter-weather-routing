"""Elapsed-time profile used for checkpoint ETAs (spec section 9)."""

import pytest

from routing.eta import elapsed_at, elapsed_profile
from routing.geometry import cumulative_miles
from routing.providers.base import Maneuver
from tests.helpers import meridian_line

LINE = meridian_line(100.0, points=5)  # shape points at 0, 25, 50, 75 and 100 miles
CUMULATIVE = cumulative_miles(LINE)

# First 50 miles in 30 minutes, last 50 miles in 90 minutes, then the zero-length arrival maneuver.
FAST_THEN_SLOW = [
    Maneuver(seconds=1800.0, begin_index=0, end_index=2),
    Maneuver(seconds=5400.0, begin_index=2, end_index=4),
    Maneuver(seconds=0.0, begin_index=4, end_index=4),
]


def elapsed(maneuvers, miles, duration=7200.0):
    return elapsed_at(CUMULATIVE, elapsed_profile(CUMULATIVE, maneuvers, duration), miles)


def test_without_maneuvers_time_is_proportional_to_distance():
    assert elapsed([], 50.0) == pytest.approx(3600.0)
    assert elapsed([], 10.0) == pytest.approx(720.0)


@pytest.mark.parametrize(
    "miles, seconds",
    [(0.0, 0.0), (25.0, 900.0), (50.0, 1800.0), (62.5, 3150.0), (75.0, 4500.0), (100.0, 7200.0)],
)
def test_maneuver_times_shape_the_profile(miles, seconds):
    assert elapsed(FAST_THEN_SLOW, miles) == pytest.approx(seconds)


def test_profile_is_scaled_to_the_reported_route_duration():
    half_speed = [
        Maneuver(seconds=900.0, begin_index=0, end_index=2),
        Maneuver(seconds=2700.0, begin_index=2, end_index=4),
    ]
    assert elapsed(half_speed, 50.0) == pytest.approx(1800.0)
    assert elapsed(half_speed, 100.0) == pytest.approx(7200.0)


@pytest.mark.parametrize(
    "broken",
    [
        [Maneuver(seconds=1800.0, begin_index=0, end_index=2)],  # stops before the end
        [
            Maneuver(seconds=1800.0, begin_index=0, end_index=1),
            Maneuver(seconds=5400.0, begin_index=2, end_index=4),  # gap between maneuvers
        ],
        [Maneuver(seconds=7200.0, begin_index=0, end_index=9)],  # index outside the shape
        [Maneuver(seconds=0.0, begin_index=0, end_index=4)],  # no usable time
        [
            Maneuver(seconds=-5.0, begin_index=0, end_index=2),
            Maneuver(seconds=7205.0, begin_index=2, end_index=4),
        ],
    ],
)
def test_unusable_maneuvers_fall_back_to_proportional_time(broken):
    assert elapsed(broken, 50.0) == pytest.approx(3600.0)
    assert elapsed(broken, 100.0) == pytest.approx(7200.0)


def test_profile_never_decreases():
    profile = elapsed_profile(CUMULATIVE, FAST_THEN_SLOW, 7200.0)
    assert profile == sorted(profile)
    assert profile[0] == 0.0
    assert profile[-1] == pytest.approx(7200.0)


def test_elapsed_is_clamped_to_the_route():
    assert elapsed(FAST_THEN_SLOW, -3.0) == 0.0
    assert elapsed(FAST_THEN_SLOW, 400.0) == pytest.approx(7200.0)

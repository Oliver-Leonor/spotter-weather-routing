"""Polyline decoding, distances and geometry helpers (spec sections 8.1 and 9)."""

import pytest

from routing.geometry import (
    are_near_identical,
    cumulative_miles,
    decode_polyline,
    haversine_miles,
    point_at,
    simplify,
)
from tests.helpers import MILES_PER_DEGREE, encode_polyline, meridian_line


def test_decode_polyline5_reference_example():
    decoded = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@", precision=5)
    assert decoded == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def test_decode_polyline6_round_trips_negative_and_positive_deltas():
    points = [(39.7392, -104.9903), (39.5, -104.0), (39.0997, -94.5786), (39.2, -94.6)]
    assert decode_polyline(encode_polyline(points)) == points


def test_decode_rejects_truncated_input():
    with pytest.raises(ValueError):
        decode_polyline(encode_polyline([(39.0, -104.0), (39.5, -103.0)])[:-1])


def test_haversine_one_degree_of_latitude():
    assert haversine_miles(39.0, -100.0, 40.0, -100.0) == pytest.approx(MILES_PER_DEGREE, rel=1e-9)


def test_haversine_one_degree_of_longitude_on_the_equator():
    assert haversine_miles(0.0, 10.0, 0.0, 11.0) == pytest.approx(MILES_PER_DEGREE, rel=1e-9)


def test_haversine_is_zero_for_the_same_point_and_symmetric():
    assert haversine_miles(39.0, -100.0, 39.0, -100.0) == 0.0
    there = haversine_miles(39.7392, -104.9903, 39.0997, -94.5786)
    back = haversine_miles(39.0997, -94.5786, 39.7392, -104.9903)
    assert there == pytest.approx(back)
    assert 550 < there < 565  # Denver to Kansas City, straight line


def test_cumulative_miles_sums_consecutive_segments():
    line = meridian_line(100.0, points=5)
    assert cumulative_miles(line) == pytest.approx([0.0, 25.0, 50.0, 75.0, 100.0])


def test_point_at_interpolates_inside_a_segment():
    line = meridian_line(100.0, points=5)
    lat, lon = point_at(line, cumulative_miles(line), 37.5)
    assert lat == pytest.approx(39.0 + 37.5 / MILES_PER_DEGREE)
    assert lon == -100.0


def test_point_at_clamps_to_the_ends():
    line = meridian_line(100.0, points=5)
    cumulative = cumulative_miles(line)
    assert point_at(line, cumulative, -5.0) == line[0]
    assert point_at(line, cumulative, 250.0) == line[-1]


def test_simplify_drops_collinear_points_and_keeps_the_ends():
    line = meridian_line(100.0, points=41)
    assert simplify(line, tolerance_miles=0.02) == [line[0], line[-1]]


def test_simplify_keeps_a_detour_larger_than_the_tolerance():
    line = meridian_line(100.0, points=5)
    bend = (line[2][0], line[2][1] + 0.05)  # about 2.7 miles east of the straight line
    # Tolerance sits between the bend (2.7 mi off) and its neighbours (1.3 mi off the new line).
    assert simplify([line[0], line[1], bend, line[3], line[4]], tolerance_miles=2.0) == [
        line[0],
        bend,
        line[4],
    ]


def test_simplify_drops_a_wiggle_smaller_than_the_tolerance():
    line = meridian_line(100.0, points=5)
    wiggle = (line[2][0], line[2][1] + 0.0001)  # a few metres
    assert simplify([line[0], line[1], wiggle, line[3], line[4]], tolerance_miles=0.02) == [
        line[0],
        line[4],
    ]


def _with_distances(points):
    return points, cumulative_miles(points)


def test_identical_geometries_are_near_identical():
    a = _with_distances(meridian_line(120.0, points=25))
    b = _with_distances(meridian_line(120.0, points=60))  # same road, different point density
    assert are_near_identical(*a, *b)


def test_parallel_route_miles_away_is_distinct():
    a = _with_distances(meridian_line(120.0, points=25))
    b = _with_distances(meridian_line(120.0, points=25, lon=-99.9))  # about 5 miles east
    assert not are_near_identical(*a, *b)


def test_route_with_a_mid_route_detour_is_distinct():
    base = meridian_line(120.0, points=25)
    detour = list(base)
    detour[12] = (base[12][0], base[12][1] + 0.2)  # leaves the road by about 10 miles
    assert not are_near_identical(*_with_distances(base), *_with_distances(detour))


def test_longer_route_on_the_same_bearing_is_distinct():
    a = _with_distances(meridian_line(120.0, points=25))
    b = _with_distances(meridian_line(132.0, points=25))
    assert not are_near_identical(*a, *b)

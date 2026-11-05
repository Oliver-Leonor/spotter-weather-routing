"""Checkpoint sampling and mileage attribution (spec section 8.1)."""

import pytest

from routing.geometry import cumulative_miles
from routing.sampling import attribute_miles, checkpoint_distances, sample_route
from tests.helpers import MILES_PER_DEGREE, meridian_line


@pytest.mark.parametrize(
    "total, interval, expected",
    [
        (100.0, 10, [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]),
        (100.0, 25, [0.0, 25.0, 50.0, 75.0, 100.0]),
        (100.0, 50, [0.0, 50.0, 100.0]),
        (60.0, 25, [0.0, 25.0, 50.0, 60.0]),  # final partial segment of 10 miles
        (8.0, 10, [0.0, 8.0]),  # route shorter than the interval
        (25.0, 25, [0.0, 25.0]),  # the destination replaces a checkpoint on top of it
    ],
)
def test_checkpoint_distances(total, interval, expected):
    assert checkpoint_distances(total, interval) == pytest.approx(expected)


def test_checkpoint_closer_than_ten_percent_of_the_interval_to_the_end_is_dropped():
    assert checkpoint_distances(52.0, 25) == pytest.approx([0.0, 25.0, 52.0])  # 2.0 < 2.5


def test_checkpoint_exactly_ten_percent_of_the_interval_from_the_end_is_kept():
    assert checkpoint_distances(52.5, 25) == pytest.approx([0.0, 25.0, 50.0, 52.5])


def test_checkpoint_distances_rejects_an_empty_route():
    with pytest.raises(ValueError):
        checkpoint_distances(0.0, 25)


def test_attribution_splits_each_segment_at_its_midpoint():
    assert attribute_miles([0.0, 25.0, 50.0, 60.0]) == pytest.approx([12.5, 25.0, 17.5, 5.0])


def test_attribution_of_a_two_point_route_gives_each_end_half():
    assert attribute_miles([0.0, 8.0]) == pytest.approx([4.0, 4.0])


@pytest.mark.parametrize("interval", [10, 25, 50])
@pytest.mark.parametrize("total", [8.0, 52.0, 60.0, 239.4, 604.07])
def test_attributed_miles_always_sum_to_the_route_length(total, interval):
    distances = checkpoint_distances(total, interval)
    attributed = attribute_miles(distances)
    assert sum(attributed) == pytest.approx(total, abs=1e-9)
    assert all(miles > 0 for miles in attributed)


def test_attribution_is_never_count_times_interval():
    distances = checkpoint_distances(60.0, 25)
    assert sum(attribute_miles(distances)) != pytest.approx(len(distances) * 25)


def test_sample_route_places_checkpoints_along_the_geometry():
    line = meridian_line(60.0, points=7)
    samples = sample_route(line, cumulative_miles(line), 25)

    assert [s.kind for s in samples] == ["origin", "checkpoint", "checkpoint", "destination"]
    assert [s.index for s in samples] == [0, 1, 2, 3]
    assert [s.distance_miles for s in samples] == pytest.approx([0.0, 25.0, 50.0, 60.0])
    assert [s.attributed_miles for s in samples] == pytest.approx([12.5, 25.0, 17.5, 5.0])
    assert [s.lat for s in samples] == pytest.approx(
        [39.0 + d / MILES_PER_DEGREE for d in (0.0, 25.0, 50.0, 60.0)]
    )
    assert all(s.lon == -100.0 for s in samples)


def test_sample_route_shorter_than_the_interval_has_only_origin_and_destination():
    line = meridian_line(8.0, points=3)
    samples = sample_route(line, cumulative_miles(line), 50)
    assert [s.kind for s in samples] == ["origin", "destination"]
    assert sum(s.attributed_miles for s in samples) == pytest.approx(8.0)

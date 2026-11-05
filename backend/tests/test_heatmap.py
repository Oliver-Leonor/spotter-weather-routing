"""Corridor heatmap grid and hourly cell risk (spec section 10.2)."""

import math
from datetime import UTC, datetime

import pytest

from analysis.heatmap import (
    CORRIDOR_MILES,
    HOURS,
    MAX_CELLS,
    MIN_CELL_MILES,
    Grid,
    build_grid,
    build_heatmap,
)
from routing.geometry import cumulative_miles, haversine_miles
from tests.helpers import MILES_PER_DEGREE, meridian_line
from weather.models import HourlySeries

EAST_WEST = [(39.0, -105.0 + i * 0.05) for i in range(201)]  # about 540 miles along 39 N
DIAGONAL = [(36.0 + i * 0.03, -105.0 + i * 0.05) for i in range(201)]  # about 680 miles
SHORT = meridian_line(8.0, points=9)


def corridor(points):
    return (points, cumulative_miles(points))


def miles_to_route(cell, points):
    return min(haversine_miles(cell[0], cell[1], lat, lon) for lat, lon in points)


@pytest.mark.parametrize("points", [EAST_WEST, DIAGONAL, SHORT])
def test_grid_stays_within_the_cell_budget(points):
    grid = build_grid([corridor(points)])
    assert 0 < len(grid.cells) <= MAX_CELLS


@pytest.mark.parametrize("points", [EAST_WEST, DIAGONAL, SHORT])
def test_every_cell_centre_is_within_the_corridor_distance_of_a_route(points):
    grid = build_grid([corridor(points)])
    # One mile of slack: the route is measured at reference points a few miles apart.
    assert all(miles_to_route(cell, points) <= CORRIDOR_MILES + 1 for cell in grid.cells)


@pytest.mark.parametrize("points", [EAST_WEST, DIAGONAL, SHORT])
def test_every_part_of_the_route_lies_inside_a_cell(points):
    grid = build_grid([corridor(points)])
    for lat, lon in points:
        assert any(
            abs(lat - cell_lat) <= grid.lat_step / 2 + 1e-9
            and abs(lon - cell_lon) <= grid.lon_step / 2 + 1e-9
            for cell_lat, cell_lon in grid.cells
        )


def test_cells_far_from_a_diagonal_route_are_dropped():
    grid = build_grid([corridor(DIAGONAL)])
    corner_without_road = (42.0, -105.0)
    nearest = min(haversine_miles(*corner_without_road, lat, lon) for lat, lon in grid.cells)
    assert nearest > 100


def test_cell_budget_is_spent_on_the_corridor_not_on_empty_corners():
    # A 12 x 12 grid over the whole bounding box of this route would need cells of about 50 miles.
    # Counting only the cells kept near the route allows a much finer grid within the same budget.
    grid = build_grid([corridor(DIAGONAL)])
    assert grid.cell_size_miles < 35
    assert 100 < len(grid.cells) <= MAX_CELLS


def test_very_long_route_keeps_the_cells_it_passes_through():
    coast_to_coast = [(30.0 + i * 0.05, -120.0 + i * 0.15) for i in range(301)]  # about 2,600 miles
    grid = build_grid([corridor(coast_to_coast)])
    assert len(grid.cells) <= MAX_CELLS
    for lat, lon in coast_to_coast:
        assert any(
            abs(lat - cell_lat) <= grid.lat_step / 2 + 1e-9
            and abs(lon - cell_lon) <= grid.lon_step / 2 + 1e-9
            for cell_lat, cell_lon in grid.cells
        )


def test_cells_are_square_in_miles():
    grid = build_grid([corridor(EAST_WEST)])
    assert grid.lat_step * MILES_PER_DEGREE == pytest.approx(grid.cell_size_miles)
    miles_per_lon_degree = MILES_PER_DEGREE * math.cos(math.radians(39.0))
    assert grid.lon_step * miles_per_lon_degree == pytest.approx(grid.cell_size_miles, rel=0.01)


def test_cells_form_a_regular_grid():
    grid = build_grid([corridor(EAST_WEST)])
    assert len(set(grid.cells)) == len(grid.cells)
    lats = sorted({lat for lat, _ in grid.cells})
    lons = sorted({lon for _, lon in grid.cells})
    assert all(b - a == pytest.approx(grid.lat_step) for a, b in zip(lats, lats[1:], strict=False))
    assert all(b - a == pytest.approx(grid.lon_step) for a, b in zip(lons, lons[1:], strict=False))


def test_short_route_does_not_oversample_the_forecast():
    grid = build_grid([corridor(SHORT)])
    assert grid.cell_size_miles == pytest.approx(MIN_CELL_MILES)


def test_grid_spans_every_route():
    north = meridian_line(100.0, points=21, start_lat=40.0, lon=-100.0)
    south = meridian_line(100.0, points=21, start_lat=37.0, lon=-99.0)
    grid = build_grid([corridor(north), corridor(south)])
    assert min(miles_to_route(cell, north) for cell in grid.cells) < grid.cell_size_miles
    assert min(miles_to_route(cell, south) for cell in grid.cells) < grid.cell_size_miles


# ------------------------------------------------------------ cell values ------
BASE = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
CELL_A, CELL_B = (39.0, -100.0), (39.1, -100.0)
GRID = Grid(cell_size_miles=10.0, lat_step=0.1, lon_step=0.13, cells=(CELL_A, CELL_B))


def make_series(hours=60, wind=10.0, rain=0.0, snow=0.0) -> HourlySeries:
    def column(value):
        return tuple(value) if isinstance(value, list) else (value,) * hours

    first = int(BASE.timestamp())
    return HourlySeries(
        times=tuple(first + 3600 * i for i in range(hours)),
        wind_mph=column(wind),
        wind_gust_mph=(None,) * hours,
        rain_in_per_hr=column(rain),
        snow_in_per_hr=column(snow),
        temperature_f=(None,) * hours,
        weather_code=(None,) * hours,
        timezone="America/Chicago",
        utc_offset_seconds=-21600,
        fetched_at=BASE,
    )


def heatmap_for(series_by_cell, load_lb=20_000):
    return build_heatmap(GRID, series_by_cell, BASE, load_lb=load_lb)


def test_heatmap_covers_49_hours_from_the_base_time():
    heatmap = heatmap_for({CELL_A: make_series(), CELL_B: make_series()})
    assert HOURS == 49
    assert heatmap["base_time"] == "2026-11-06T15:00:00Z"
    assert len(heatmap["hours"]) == 49
    assert (heatmap["hours"][0], heatmap["hours"][1]) == (
        "2026-11-06T15:00:00Z",
        "2026-11-06T16:00:00Z",
    )
    assert heatmap["hours"][48] == "2026-11-08T15:00:00Z"


def test_heatmap_describes_the_grid_so_cells_can_be_drawn():
    heatmap = heatmap_for({CELL_A: make_series(), CELL_B: make_series()})
    assert (heatmap["cell_size_miles"], heatmap["lat_step"], heatmap["lon_step"]) == (
        10.0,
        0.1,
        0.13,
    )
    assert [(cell["lat"], cell["lon"]) for cell in heatmap["cells"]] == [CELL_A, CELL_B]


def test_cell_values_follow_the_hourly_series():
    wind = [10.0 + i for i in range(60)]
    cell = heatmap_for({CELL_A: make_series(wind=wind), CELL_B: make_series()})["cells"][0]
    assert cell["wind"] == wind[:49]
    assert cell["rain"] == [0.0] * 49
    assert cell["snow"] == [0.0] * 49
    # 10 to 24 mph Low, 25 to 34 Moderate, 35 to 44 High, 45 to 54 Severe, then No Travel.
    assert cell["risk"] == [0] * 15 + [1] * 10 + [2] * 10 + [3] * 10 + [4] * 4


def test_cell_risk_uses_the_same_load_rules_as_checkpoints():
    series = {CELL_A: make_series(wind=47.0), CELL_B: make_series(wind=38.0)}
    at_limit = heatmap_for(series, load_lb=30_000)["cells"]
    over_30k = heatmap_for(series, load_lb=30_001)["cells"]
    over_40k = heatmap_for(series, load_lb=40_001)["cells"]
    assert (at_limit[0]["risk"][0], over_30k[0]["risk"][0]) == (3, 4)
    assert (at_limit[1]["risk"][0], over_40k[1]["risk"][0]) == (2, 3)


def test_hours_beyond_the_forecast_are_unknown_not_low():
    cell = heatmap_for({CELL_A: make_series(hours=10), CELL_B: make_series()})["cells"][0]
    assert cell["risk"][:10] == [0] * 10
    assert cell["risk"][10:] == [None] * 39
    assert cell["wind"][10:] == [None] * 39


def test_missing_measurement_makes_the_hour_unknown():
    rain = [0.0, None] + [0.0] * 58
    cell = heatmap_for({CELL_A: make_series(rain=rain), CELL_B: make_series()})["cells"][0]
    assert cell["risk"][:3] == [0, None, 0]
    assert cell["rain"][:3] == [0.0, None, 0.0]


def test_cell_without_a_forecast_is_unknown_for_every_hour():
    cell = heatmap_for({CELL_B: make_series()})["cells"][0]
    assert cell["risk"] == [None] * 49

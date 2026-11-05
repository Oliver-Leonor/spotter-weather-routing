"""Corridor weather heatmap (spec section 10.2): a grid of forecast cells around the routes.

The grid is square in miles. Only cells near a route are kept, and the cell size is the smallest
one whose kept cells fit the budget, so the forecast points are spent on the corridor instead of
on empty corners of the bounding box. Each cell carries 49 hourly values classified with the same
rules and load weight as the checkpoints.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from common.timefmt import iso_utc
from risk.classification import classify_checkpoint
from routing.geometry import MILES_PER_DEGREE, Point, point_at
from weather.models import HourlySeries, PointKey, point_key

MAX_CELLS = 144
MIN_CELL_MILES = 5.0  # finer cells would sample the same forecast grid box twice
CORRIDOR_MILES = 60.0  # cells whose centre is farther than this from every route are dropped
PADDING_FRACTION = 0.10
MIN_PADDING_MILES = 20.0
REFERENCE_SPACING_MILES = 5.0
SIZE_STEP = 1.1
HOURS = 49  # forecast offsets 0 to 48 hours

Route = tuple[Sequence[Point], Sequence[float]]  # (points, cumulative miles)


@dataclass(frozen=True)
class Grid:
    cell_size_miles: float
    lat_step: float
    lon_step: float
    cells: tuple[Point, ...]  # cell centres, row by row from the south-west


def build_grid(routes: Sequence[Route]) -> Grid:
    references = [
        point_at(points, cumulative, miles)
        for points, cumulative in routes
        for miles in _reference_miles(cumulative[-1])
    ]
    box = _padded_box(references)

    # Start from the size at which the whole box fits the budget, then refine against the cells
    # actually kept near the routes.
    size = max(MIN_CELL_MILES, math.sqrt(box.width_miles * box.height_miles / MAX_CELLS))
    cells = _corridor_cells(box, size, references)
    while len(cells) > MAX_CELLS:
        size *= SIZE_STEP
        cells = _corridor_cells(box, size, references)
    while size > MIN_CELL_MILES:
        smaller = max(MIN_CELL_MILES, size / SIZE_STEP)
        candidate = _corridor_cells(box, smaller, references)
        if len(candidate) > MAX_CELLS:
            break
        size, cells = smaller, candidate

    return Grid(
        cell_size_miles=size,
        lat_step=size / MILES_PER_DEGREE,
        lon_step=size / box.miles_per_lon_degree,
        cells=tuple(cells),
    )


def build_heatmap(
    grid: Grid,
    series_by_point: Mapping[PointKey, HourlySeries],
    base_time: datetime,
    *,
    load_lb: float,
) -> dict:
    """The `heatmap` object of the analysis response. Hours without a forecast are null."""
    hours = [base_time + timedelta(hours=offset) for offset in range(HOURS)]
    epochs = [hour.timestamp() for hour in hours]
    cells = []
    for lat, lon in grid.cells:
        series = series_by_point.get(point_key(lat, lon))
        risk, wind, rain, snow = [], [], [], []
        for epoch in epochs:
            index = series.nearest_index(epoch) if series is not None else None
            if index is None:
                measurements = (None, None, None)
            else:
                measurements = (
                    series.wind_mph[index],
                    series.rain_in_per_hr[index],
                    series.snow_in_per_hr[index],
                )
            wind.append(measurements[0])
            rain.append(measurements[1])
            snow.append(measurements[2])
            risk.append(
                classify_checkpoint(
                    wind_mph=measurements[0],
                    rain_in_per_hr=measurements[1],
                    snow_in_per_hr=measurements[2],
                    load_lb=load_lb,
                ).value
            )
        cells.append(
            {
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "risk": risk,
                "wind": wind,
                "rain": rain,
                "snow": snow,
            }
        )
    return {
        "base_time": iso_utc(base_time),
        "hours": [iso_utc(hour) for hour in hours],
        "cell_size_miles": round(grid.cell_size_miles, 2),
        "lat_step": round(grid.lat_step, 5),
        "lon_step": round(grid.lon_step, 5),
        "cells": cells,
    }


@dataclass(frozen=True)
class _Box:
    south: float
    north: float
    west: float
    east: float
    miles_per_lon_degree: float

    @property
    def height_miles(self) -> float:
        return (self.north - self.south) * MILES_PER_DEGREE

    @property
    def width_miles(self) -> float:
        return (self.east - self.west) * self.miles_per_lon_degree


def _reference_miles(total_miles: float) -> list[float]:
    count = max(1, math.ceil(total_miles / REFERENCE_SPACING_MILES))
    return [total_miles * step / count for step in range(count + 1)]


def _padded_box(points: Sequence[Point]) -> _Box:
    lats = [lat for lat, _ in points]
    lons = [lon for _, lon in points]
    south, north, west, east = min(lats), max(lats), min(lons), max(lons)
    miles_per_lon_degree = MILES_PER_DEGREE * math.cos(math.radians((south + north) / 2))
    pad_lat = max((north - south) * MILES_PER_DEGREE * PADDING_FRACTION, MIN_PADDING_MILES)
    pad_lon = max((east - west) * miles_per_lon_degree * PADDING_FRACTION, MIN_PADDING_MILES)
    return _Box(
        south=south - pad_lat / MILES_PER_DEGREE,
        north=north + pad_lat / MILES_PER_DEGREE,
        west=west - pad_lon / miles_per_lon_degree,
        east=east + pad_lon / miles_per_lon_degree,
        miles_per_lon_degree=miles_per_lon_degree,
    )


def _corridor_cells(box: _Box, size: float, references: Sequence[Point]) -> list[Point]:
    """Centres of the cells of a `size`-mile grid over `box` that lie near a route.

    A cell is kept when its centre is within the corridor distance of a route reference point.
    """
    rows = math.ceil(box.height_miles / size)
    cols = math.ceil(box.width_miles / size)
    lat_step = size / MILES_PER_DEGREE
    lon_step = size / box.miles_per_lon_degree
    # Centre the grid on the box, since rows * size overshoots the box height slightly.
    south = (box.south + box.north) / 2 - rows * lat_step / 2
    west = (box.west + box.east) / 2 - cols * lon_step / 2

    reach = math.ceil(CORRIDOR_MILES / size)
    kept: set[tuple[int, int]] = set()
    for ref_lat, ref_lon in references:
        ref_row = int((ref_lat - south) / lat_step)
        ref_col = int((ref_lon - west) / lon_step)
        for row in range(max(0, ref_row - reach), min(rows, ref_row + reach + 1)):
            lat = south + (row + 0.5) * lat_step
            north_miles = (lat - ref_lat) * MILES_PER_DEGREE
            miles_per_lon = MILES_PER_DEGREE * math.cos(math.radians((lat + ref_lat) / 2))
            for col in range(max(0, ref_col - reach), min(cols, ref_col + reach + 1)):
                if (row, col) in kept:
                    continue
                east_miles = (west + (col + 0.5) * lon_step - ref_lon) * miles_per_lon
                if math.hypot(north_miles, east_miles) <= CORRIDOR_MILES:
                    kept.add((row, col))
    return [
        (south + (row + 0.5) * lat_step, west + (col + 0.5) * lon_step) for row, col in sorted(kept)
    ]

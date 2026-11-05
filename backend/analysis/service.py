"""Trip analysis: the one place where routing, weather, risk and recommendation meet.

    routes -> distinct routes -> checkpoints and ETAs -> forecast at each ETA -> risk
           -> route summaries -> recommendation -> corridor heatmap

Every rule lives in a pure module (`routing`, `weather`, `risk`); this module only orchestrates
and shapes the API response (spec section 6.3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from common.errors import NoRouteError, TripTooLargeError, UpstreamError
from common.timefmt import iso_utc
from risk.aggregation import STATUS_BLOCKED, STATUS_OK, RouteSummary, summarize
from risk.classification import LOAD_RULE_2_LB, CheckpointRisk, classify_checkpoint
from risk.levels import RiskLevel
from risk.recommendation import RouteCandidate, recommend
from routing.eta import elapsed_at, elapsed_profile
from routing.geometry import are_near_identical, cumulative_miles, simplify
from routing.providers.base import ProviderRoute, RouteProvider
from routing.providers.recorded import RecordedRouteProvider
from routing.providers.valhalla import ValhallaProvider
from routing.sampling import SamplePoint, sample_route
from weather.models import HourlySeries, Observation, PointKey, point_key
from weather.open_meteo import OpenMeteoProvider
from weather.scenario import ScenarioWeatherProvider

from .heatmap import HOURS as HEATMAP_HOURS
from .heatmap import Grid, build_grid, build_heatmap

MODE_LIVE = "live"
MODE_FIXTURE = "fixture"
ROUTE_LIMIT = 3
# Checkpoint forecasts per analysis. With the heatmap grid (up to 144 cells) this keeps a single
# analysis under the weather provider's 600 calls per minute, counting each place as one call.
MAX_CHECKPOINT_FORECASTS = 450
DISPLAY_TOLERANCE_MILES = 0.02  # about 30 metres: invisible on the map, far fewer points to send

ROUTING_NOTE = (
    "Standard driving routes (Valhalla auto costing). Truck restrictions such as bridge weight "
    "limits, low clearances and hazmat rules are not applied."
)
LOAD_NOTE = "Load weight is cargo weight and is used only for the weather risk rules."
DEMO_NOTE = (
    "Demo mode: the routes are a recorded Valhalla response for Denver to Kansas City and the "
    "weather is a scripted scenario, not a real forecast."
)
DEMO_WARNING = (
    "Demo data: recorded Denver to Kansas City routes with scripted weather. "
    "This is not a live forecast."
)


@dataclass(frozen=True)
class Place:
    lat: float
    lon: float
    label: str = ""


@dataclass(frozen=True)
class TripRequest:
    origin: Place
    destination: Place
    departure: datetime  # timezone-aware
    load_weight_lb: int
    interval_miles: int = 25
    mode: str = MODE_LIVE


@dataclass(frozen=True)
class _RoutePlan:
    """A route with its checkpoints placed and timed, before any weather is known."""

    route_id: str
    name: str
    route: ProviderRoute
    cumulative: list[float]
    samples: list[SamplePoint]
    etas: list[datetime]
    departure: datetime
    arrival: datetime


def analyze(trip: TripRequest, *, routing: RouteProvider | None = None, weather=None) -> dict:
    """Analyze a trip. Providers default to the live clients, or to the demo in fixture mode."""
    origin, destination = trip.origin, trip.destination
    warnings: list[dict] = []
    notes = [ROUTING_NOTE, LOAD_NOTE]
    if trip.mode == MODE_FIXTURE:
        recorded = RecordedRouteProvider()
        routing = routing or recorded
        weather = weather or ScenarioWeatherProvider()
        origin = Place(*recorded.origin, recorded.origin_label)
        destination = Place(*recorded.destination, recorded.destination_label)
        notes.append(DEMO_NOTE)
        warnings.append({"code": "DEMO_MODE", "message": DEMO_WARNING})
    else:
        routing = routing or ValhallaProvider()
        weather = weather or OpenMeteoProvider()

    departure = trip.departure.astimezone(UTC).replace(microsecond=0)
    routing_result = routing.get_routes(
        (origin.lat, origin.lon), (destination.lat, destination.lon)
    )
    plans = _plan_routes(routing_result.routes, departure, trip.interval_miles, warnings)
    _check_trip_size(plans, trip.interval_miles)

    # One forecast window serves the checkpoints and the 0 to 48 hour heatmap.
    base_time = departure.replace(minute=0, second=0)
    window_start = base_time - timedelta(hours=1)
    window_end = max(
        _ceil_hour(max(plan.arrival for plan in plans)) + timedelta(hours=1),
        base_time + timedelta(hours=HEATMAP_HOURS - 1),
    )

    checkpoint_points = [(s.lat, s.lon) for plan in plans for s in plan.samples]
    series = weather.fetch_hourly(checkpoint_points, window_start, window_end)

    routes, candidates = [], []
    for plan in plans:
        payload, candidate = _assess_route(plan, series, trip.load_weight_lb)
        routes.append(payload)
        candidates.append(candidate)

    heatmap = _heatmap(
        plans, weather, window_start, window_end, base_time, trip.load_weight_lb, warnings
    )

    return {
        "request": {
            "origin": {"lat": origin.lat, "lon": origin.lon, "label": origin.label},
            "destination": {
                "lat": destination.lat,
                "lon": destination.lon,
                "label": destination.label,
            },
            "departure_time": trip.departure.isoformat(),
            "departure_time_utc": iso_utc(departure),
            "load_weight_lb": trip.load_weight_lb,
            "checkpoint_interval_miles": trip.interval_miles,
            "mode": trip.mode,
        },
        "provenance": {
            "mode": trip.mode,
            "routing": {
                "provider": routing_result.provider,
                "endpoint": routing_result.endpoint,
                "costing": routing_result.costing,
                "fetched_at": iso_utc(routing_result.fetched_at),
            },
            "weather": {
                "provider": weather.name,
                "model": weather.model,
                "fetched_at": iso_utc(min(s.fetched_at for s in series.values())),
                "forecast_window": {"start": iso_utc(window_start), "end": iso_utc(window_end)},
            },
            "notes": notes,
        },
        "routes": routes,
        "recommendation": recommend(candidates).to_dict(),
        "warnings": warnings,
        "heatmap": heatmap,
    }


# ------------------------------------------------------------------ routes ------
def _plan_routes(
    provider_routes: Sequence[ProviderRoute],
    departure: datetime,
    interval_miles: int,
    warnings: list[dict],
) -> list[_RoutePlan]:
    """Keep up to three distinct routes and place their timed checkpoints."""
    distinct: list[tuple[ProviderRoute, list[float]]] = []
    duplicates = 0
    for route in provider_routes:
        cumulative = cumulative_miles(route.points)
        if any(
            are_near_identical(route.points, cumulative, kept.points, kept_cumulative)
            for kept, kept_cumulative in distinct
        ):
            duplicates += 1
        elif len(distinct) < ROUTE_LIMIT:
            distinct.append((route, cumulative))
    if not distinct:
        raise NoRouteError("The routing provider returned no route for this trip.")

    if duplicates:
        plural = duplicates != 1
        warnings.append(
            {
                "code": "DUPLICATE_ROUTES_REMOVED",
                "message": (
                    f"The routing provider returned {duplicates} route{'s' if plural else ''} "
                    f"that duplicate{'' if plural else 's'} another option. "
                    f"{'They were' if plural else 'It was'} removed."
                ),
            }
        )
    if len(distinct) < ROUTE_LIMIT:
        count = len(distinct)
        warnings.append(
            {
                "code": "FEWER_ROUTES",
                "message": (
                    f"The routing provider returned {count} distinct "
                    f"route{'' if count == 1 else 's'} for this trip."
                ),
            }
        )

    plans = []
    for number, (route, cumulative) in enumerate(distinct, start=1):
        samples = sample_route(route.points, cumulative, interval_miles)
        profile = elapsed_profile(cumulative, route.maneuvers, route.duration_seconds)
        etas = [
            departure + timedelta(seconds=round(elapsed_at(cumulative, profile, s.distance_miles)))
            for s in samples
        ]
        plans.append(
            _RoutePlan(
                route_id=f"route-{number}",
                name=f"Route {chr(ord('A') + number - 1)}",
                route=route,
                cumulative=cumulative,
                samples=samples,
                etas=etas,
                departure=departure,
                arrival=departure + timedelta(seconds=round(route.duration_seconds)),
            )
        )
    return plans


def _check_trip_size(plans: Sequence[_RoutePlan], interval_miles: int) -> None:
    needed = sum(len(plan.samples) for plan in plans)
    if needed > MAX_CHECKPOINT_FORECASTS:
        raise TripTooLargeError(
            f"This trip needs {needed} checkpoint forecasts at a {interval_miles}-mile interval, "
            f"and the limit is {MAX_CHECKPOINT_FORECASTS}. "
            "Choose a larger checkpoint interval or a shorter trip."
        )


def _assess_route(
    plan: _RoutePlan, series: Mapping[PointKey, HourlySeries], load_lb: int
) -> tuple[dict, RouteCandidate]:
    """Look up the forecast at each checkpoint's ETA, classify it and summarize the route."""
    checkpoints: list[dict] = []
    levels: list[tuple[RiskLevel | None, float]] = []
    blocking: list[str] = []
    unknown_count = 0

    for sample, eta in zip(plan.samples, plan.etas, strict=True):
        point_series = series.get(point_key(sample.lat, sample.lon))
        observation = _observation_at(point_series, eta)
        risk = classify_checkpoint(
            wind_mph=observation.wind_mph if observation else None,
            rain_in_per_hr=observation.rain_in_per_hr if observation else None,
            snow_in_per_hr=observation.snow_in_per_hr if observation else None,
            load_lb=load_lb,
        )
        timezone = point_series.timezone if point_series else None
        levels.append((risk.level, sample.attributed_miles))
        if risk.level is None:
            unknown_count += 1
        elif risk.level is RiskLevel.NO_TRAVEL:
            blocking.append(
                f"No Travel at checkpoint {sample.index} near {sample.lat:.2f}, {sample.lon:.2f} "
                f"at {_local_clock(eta, timezone)} ({_causes(risk, observation)})"
            )
        checkpoints.append(
            {
                "index": sample.index,
                "id": f"{plan.route_id}-cp-{sample.index}",
                "kind": sample.kind,
                "lat": round(sample.lat, 5),
                "lon": round(sample.lon, 5),
                "distance_miles": round(sample.distance_miles, 2),
                "eta": iso_utc(eta),
                "timezone": timezone,
                "utc_offset_seconds": _utc_offset_seconds(eta, point_series),
                "attributed_miles": round(sample.attributed_miles, 2),
                "weather": _weather_payload(observation),
                "risk": risk.to_dict(),
            }
        )

    summary = summarize(levels)
    payload = {
        "id": plan.route_id,
        "name": plan.name,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [round(lon, 5), round(lat, 5)]
                for lat, lon in simplify(plan.route.points, DISPLAY_TOLERANCE_MILES)
            ],
        },
        "distance_miles": round(plan.cumulative[-1], 1),
        "provider_distance_miles": round(plan.route.provider_distance_miles, 1),
        "duration_seconds": round(plan.route.duration_seconds),
        "departure_time": iso_utc(plan.departure),
        "arrival_time": iso_utc(plan.arrival),
        "status": summary.status,
        "checkpoints": checkpoints,
        "summary": summary.to_dict(),
    }
    candidate = RouteCandidate(
        route_id=plan.route_id,
        name=plan.name,
        status=summary.status,
        severe_miles=summary.severe_miles,
        high_miles=summary.high_miles,
        average_risk=summary.average_risk,
        duration_seconds=plan.route.duration_seconds,
        issue=_issue(summary, blocking, unknown_count),
    )
    return payload, candidate


def _issue(summary: RouteSummary, blocking: list[str], unknown_count: int) -> str | None:
    """Why a route is excluded from the recommendation, in the words shown to the driver."""
    if summary.status == STATUS_OK:
        return None
    if summary.status == STATUS_BLOCKED:
        more = len(blocking) - 1
        suffix = f", and at {more} more checkpoint{'' if more == 1 else 's'}" if more else ""
        return blocking[0] + suffix
    return f"forecast unavailable for {unknown_count} checkpoint{'' if unknown_count == 1 else 's'}"


def _causes(risk: CheckpointRisk, observation: Observation) -> str:
    """The measurements that made a checkpoint No Travel, for example `wind 58.0 mph`."""
    causes = []
    if "wind" in risk.drivers:
        over_load = "load_rule_2" in risk.drivers
        causes.append(
            f"wind {observation.wind_mph:.1f} mph"
            + (f" with a load over {LOAD_RULE_2_LB:,} lb" if over_load else "")
        )
    if "rain" in risk.drivers:
        causes.append(f"rain {observation.rain_in_per_hr:.2f} in/h")
    if "snow" in risk.drivers:
        causes.append(f"snow {observation.snow_in_per_hr:.2f} in/h")
    return ", ".join(causes)


# ----------------------------------------------------------------- weather ------
def _observation_at(series: HourlySeries | None, eta: datetime) -> Observation | None:
    """The forecast hour nearest the ETA, or None when the ETA is outside forecast coverage."""
    if series is None:
        return None
    index = series.nearest_index(eta.timestamp())
    return None if index is None else series.observation(index)


def _weather_payload(observation: Observation | None) -> dict | None:
    if observation is None:
        return None
    return {
        "forecast_time": iso_utc(observation.forecast_time),
        "wind_mph": observation.wind_mph,
        "wind_gust_mph": observation.wind_gust_mph,
        "rain_in_per_hr": observation.rain_in_per_hr,
        "snow_in_per_hr": observation.snow_in_per_hr,
        "temperature_f": observation.temperature_f,
        "weather_code": observation.weather_code,
    }


def _heatmap(
    plans: Sequence[_RoutePlan],
    weather,
    window_start: datetime,
    window_end: datetime,
    base_time: datetime,
    load_lb: int,
    warnings: list[dict],
) -> dict:
    """The corridor heatmap. It is secondary: if its forecast fails, the routes still stand."""
    grid = build_grid([(plan.route.points, plan.cumulative) for plan in plans])
    try:
        cell_series = weather.fetch_hourly(grid.cells, window_start, window_end)
    except UpstreamError:
        warnings.append(
            {
                "code": "HEATMAP_UNAVAILABLE",
                "message": (
                    "The corridor weather heatmap could not be loaded. "
                    "Route and checkpoint results are not affected."
                ),
            }
        )
        empty = Grid(grid.cell_size_miles, grid.lat_step, grid.lon_step, cells=())
        return build_heatmap(empty, {}, base_time, load_lb=load_lb)
    return build_heatmap(grid, cell_series, base_time, load_lb=load_lb)


# -------------------------------------------------------------------- time ------
def _ceil_hour(moment: datetime) -> datetime:
    floored = moment.replace(minute=0, second=0, microsecond=0)
    return floored if floored == moment else floored + timedelta(hours=1)


def _zone(timezone: str | None) -> ZoneInfo | None:
    if not timezone:
        return None
    try:
        return ZoneInfo(timezone)
    except (KeyError, ValueError):  # unknown or malformed zone name
        return None


def _utc_offset_seconds(moment: datetime, series: HourlySeries | None) -> int | None:
    """The local UTC offset at `moment`, so the offset is right on either side of a DST change."""
    if series is None:
        return None
    zone = _zone(series.timezone)
    if zone is None:
        return series.utc_offset_seconds
    return int(moment.astimezone(zone).utcoffset().total_seconds())


def _local_clock(moment: datetime, timezone: str | None) -> str:
    zone = _zone(timezone)
    return moment.astimezone(zone or UTC).strftime("%H:%M %Z")

# StormRoute | Weather-Aware Trip Planning
## Project specification (single source of truth)

Spotter Full Stack Developer take-home assessment. Candidate: Oliver Leonor (GitHub `Oliver-Leonor`).
Repository: https://github.com/Oliver-Leonor/spotter-weather-routing (public).

This document is the single source of truth for scope, contracts, decisions and progress. Approved
requirements are never changed silently: every change is recorded in section 17 (Decision log) first.

Status legend used throughout: `Not Started`, `In Progress`, `Ready for Codex Review`,
`Changes Requested`, `Approved`, `Merged`.

---

## 1. Overview and objectives

Build a React + Django web application that helps truck drivers choose a safer route by combining
real road routes, real hourly weather forecasts at each checkpoint's estimated arrival time, the cargo
load weight, and travel time.

Objectives, in priority order:

1. Correctness: Spotter's risk rules, units, boundary conventions and route preference order are
   implemented exactly and covered by tests.
2. Genuine data: real road-network routes and real forecasts in normal operation. A fixture mode exists
   only for repeatable demos and tests and is always labeled as such.
3. Map and heatmap quality: a smooth interactive map with three routes, checkpoints, and a time-aware
   corridor weather heatmap driven by a 0 to 48 hour slider.
4. Professional UX at desktop and 375 px mobile widths, with useful loading, empty and error states.
5. Delivered within the hard limits: 16 active working hours and 4 calendar days, as 5 reviewable PRs.

Working product name: **StormRoute | Weather-Aware Trip Planning**.

---

## 2. Exact assessment requirements (from Spotter, restated)

Hard constraints: max 4 calendar days, max 16 working hours, React frontend, Django backend.

User inputs: origin, destination, departure date and time, load weight (lb), checkpoint interval
(10 / 25 / 50 miles, default 25).

Required functionality:

1. Request three genuine route options from a routing API.
2. Compute checkpoints along each route at the selected mileage interval.
3. Estimate the arrival time at every checkpoint.
4. Retrieve the forecast for each checkpoint's location and estimated arrival time.
5. Classify weather risk using Spotter's rules (section 7).
6. Recommend the best route using the fixed priority order (section 8).
7. Display routes, checkpoints, risk classes, ETAs and summaries on an interactive map.
8. Display a weather heatmap along the travel corridor.
9. Provide a working 0 to 48 hour forecast slider.

Deliverables: public GitHub repository, hosted application, README, 5 to 10 minute Loom walkthrough.

---

## 3. Functional and nonfunctional requirements

### 3.1 Functional

- [ ] F1. Trip form with origin/destination autocomplete, departure datetime, load weight, interval.
- [ ] F2. Backend analysis endpoint returning up to three distinct real routes with checkpoints,
      ETAs, per-checkpoint weather and risk, risk mileage aggregates, recommendation, warnings.
- [ ] F3. Fewer than three routes is handled transparently (warning, never invented routes).
- [ ] F4. Duplicate geometries from the provider are rejected.
- [ ] F5. Missing or out-of-coverage weather is represented as `unknown`, never as Low.
- [ ] F6. No Travel is a hard block: such routes are never recommended; if all are blocked the UI
      shows "No safe route is currently recommended." with the causing conditions.
- [ ] F7. Routes with incomplete forecast coverage are marked `unverified` and never recommended.
- [ ] F8. Map shows all routes, highlights the selected one, shows checkpoints with risk colors, fits
      bounds automatically, and supports clicking cards and checkpoints.
- [ ] F9. Corridor heatmap for forecast offsets 0 to 48 h with the exact timestamp displayed, updated
      without rebuilding the map and without new API calls per slider move.
- [ ] F10. Changing interval or departure time re-runs the analysis and changes results accordingly.
- [ ] F11. Clearly labeled demo (fixture) mode, never presented as live weather.

### 3.2 Nonfunctional

- [ ] N1. Deterministic business logic (risk, aggregation, recommendation) in pure, tested functions.
- [ ] N2. Upstream timeouts, retries (bounded) and graceful 502/504 responses with actionable messages.
- [ ] N3. Bounded concurrency and batching for weather requests; in-process TTL cache.
- [ ] N4. No secrets in the frontend bundle or the repository. `.env.example` provided.
- [ ] N5. Typed frontend (strict TypeScript) mirroring the backend contract.
- [ ] N6. Responsive at 375 px and desktop; no heavy animations on the map.
- [ ] N7. Production: HTTPS, restrictive CORS, `DEBUG=False`, `ALLOWED_HOSTS`, pinned dependencies.
- [ ] N8. Provider attribution rendered in the UI (OpenStreetMap / FOSSGIS, Open-Meteo CC-BY 4.0,
      OpenFreeMap).

---

## 4. Architecture

### 4.1 Repository layout

```text
spotter-weather-routing/
├── frontend/                 React 19 + TypeScript + Vite + Tailwind + TanStack Query + MapLibre GL
│   ├── src/
│   │   ├── components/       presentational UI (cards, legend, slider, form controls)
│   │   ├── features/         trip-planner/, route-map/, route-comparison/, heatmap/
│   │   ├── hooks/            useAnalyzeRoutes, useGeocode, useHeatmapLayer
│   │   ├── lib/              api client, formatting (units, local time), risk colors
│   │   └── types/            api.ts (mirrors backend contract)
│   ├── e2e/                  Playwright specs (mocked API; one live smoke spec)
│   └── ...
├── backend/
│   ├── config/               Django settings/urls/wsgi (settings split: base, dev, prod)
│   ├── routing/              provider client (Valhalla), geometry decoding, sampling, ETA profile,
│   │                         recorded demo response (fixtures/)
│   ├── weather/              Open-Meteo client, unit validation, batching, geocoding, demo scenario
│   ├── risk/                 classification, aggregation, recommendation
│   ├── analysis/             orchestration service, corridor heatmap, DRF views/serializers
│   ├── common/               error types, TTL cache, outbound HTTP helper
│   ├── tests/                pytest suites (unit, API with mocked HTTP, live smoke marked `live`)
│   ├── manage.py, pyproject.toml, requirements.txt
├── docs/                     ARCHITECTURE.md, ASSUMPTIONS.md, LOOM_SCRIPT.md, screenshots/
├── spec.md                   this file
├── .env.example
├── .gitignore
└── README.md
```

No database, no auth, no background workers. Django is used for settings, URL routing, DRF
validation/serialization and a clean service layer. `DATABASES` stays empty (no migrations).

### 4.2 Request flow

```text
Browser (React) --POST /api/routes/analyze/--> Django/DRF
   1. validate input (serializer)
   2. routing.get_routes(origin, destination)        -> Valhalla, alternates=2, auto costing
   3. routing.dedupe(routes)                          -> reject near-identical geometries
   4. for each route: sample checkpoints (interval), cumulative miles, ETA per checkpoint
   5. weather.fetch_hourly(points, window)            -> Open-Meteo, batched, cached, concurrency 4
   6. risk.classify(checkpoint weather, load)         -> per-checkpoint level (or unknown)
   7. risk.aggregate(route)                           -> miles per level, avg risk, coverage
   8. risk.recommend(routes)                          -> lexicographic order + explanation
   9. heatmap.build(corridor bbox, departure)         -> grid points x 49 hourly risk values
   10. respond (typed JSON, section 6)
```

### 4.3 Frontend state

- TanStack Query owns the analysis request (`useMutation`) and geocode lookups (`useQuery`, debounced).
- Local UI state: selected route id, selected checkpoint id, slider hour, layer toggles.
- The map instance is created once (`useRef`), sources/layers created once on load, and updated via
  `source.setData()` and `map.setPaintProperty()` only. Slider changes update a paint expression that
  reads the hour-specific property (`r_<h>`) on each heatmap cell: no re-fetch, no data rebuild.

---

## 5. Provider choices (verified 2026-11-05)

### 5.1 Routing: Valhalla public instance (FOSSGIS e.V.), with Mapbox as the documented alternative

Verified facts:

- Mapbox Directions requires an access token and returns "at most two alternatives" and alternatives
  are not guaranteed. No Mapbox token is available in this environment, and three routes could not be
  verified for any corridor without one.
- Valhalla (`https://valhalla1.openstreetmap.de/route`, version 3.9.1, no key) with `costing: "auto"`,
  `alternates: 2` returned **three distinct routes on 5 of 5 probed corridors**:

| Corridor | Routes | Distances (mi) | Durations (h) |
|---|---:|---|---|
| Denver, CO to Kansas City, MO | 3 | 604.7 / 614.2 / 635.5 | 8.78 / 9.53 / 9.84 |
| Chicago, IL to Nashville, TN | 3 | 508.4 / 473.3 / 441.4 | 7.76 / 7.41 / 7.73 |
| Denver, CO to Salt Lake City, UT | 3 | 535.8 / 525.4 / 491.0 | 7.90 / 8.16 / 8.44 |
| Dallas, TX to Houston, TX | 3 | 239.4 / 263.5 / 279.5 | 3.65 / 4.35 / 4.41 |
| Atlanta, GA to Nashville, TN | 3 | 250.0 / 273.0 / 283.3 | 3.84 / 4.51 / 4.63 |

- The public OSRM demo server returned only 1 or 2 routes on the same corridors (rejected).
- Valhalla `truck` costing returned 3 routes for Chicago to Nashville but only 1 for Denver to Kansas
  City, so `auto` is the default costing. This means **standard driving routes, not truck-restricted
  routes**; this is disclosed in the UI and README. The load weight is cargo weight and is never used
  as gross vehicle weight for road restrictions.
- FOSSGIS terms of use (https://www.fossgis.de/arbeitsgruppen/osm-server/nutzungsbedingungen/):
  non-substantial, low-traffic use is permitted; commercial use only when not a substantial part of
  an offering; required: a valid identifying `User-Agent`, OSM attribution with a fixthemap link,
  an operator contact email on the website, scripts limited to one connection. The backend therefore
  calls Valhalla with one connection at a time and a `StormRoute/<version> (<contact email>)` agent.
  No availability guarantee (single server): the UI shows a clear upstream error if it is down.
- Geometry: polyline6-encoded shape per leg; maneuvers carry `time`, `length`,
  `begin_shape_index`, `end_shape_index`, which gives a per-maneuver duration profile for ETAs.

Provider abstraction: `routing/providers/base.py` defines `RouteProvider.get_routes()`. Valhalla is
implemented. A Mapbox Directions adapter is **optional** and only built if Oliver provides a token and
time allows; otherwise it is documented as the drop-in alternative.

### 5.2 Weather: Open-Meteo Forecast API (free, no key)

Verified on 2026-11-05 with live calls:

- Hourly variables used: `wind_speed_10m` (instant at the hour, 10 m sustained wind, not gusts),
  `rain` and `showers` (preceding-hour sums), `snowfall` (preceding-hour sum), plus `wind_gusts_10m`,
  `precipitation`, `temperature_2m`, `weather_code` for display only.
- Requesting `wind_speed_unit=mph&precipitation_unit=inch` makes the API return
  `wind_speed_10m: "mp/h"`, `rain: "inch"`, `showers: "inch"`, `snowfall: "inch"` (verified from
  `hourly_units`). Default units would be km/h, mm and cm. The backend requests the converted units
  and additionally validates `hourly_units` on every response, falling back to explicit conversion
  (km/h × 0.621371, mm ÷ 25.4, cm ÷ 2.54) if the units ever differ.
- Rain rate (in/h) = `rain + showers` for the hour. Snow rate (in/h) = `snowfall` for the hour.
  These are hourly amounts, never daily totals.
- Multi-location batching works: comma-separated `latitude`/`longitude` lists return a JSON array.
- Time handling: `timeformat=unixtime&timezone=auto` gives absolute UTC epochs plus each location's
  IANA `timezone` and `utc_offset_seconds`, which the backend forwards so the UI can render each
  checkpoint's ETA in that checkpoint's local time (DST-safe via IANA zones).
- Coverage: up to 16 forecast days; the backend requests only the window it needs. With
  `timezone=auto` the `start_date`/`end_date` parameters are local calendar days per location, so
  the request pads the UTC window by one day on each side. The API accepts dates up to today (UTC)
  plus 15 days (verified 2026-11-05: a later `end_date` is a 400), so `end_date` is clamped and
  later hours are simply absent from the series.
- Terms: free for non-commercial use, CC-BY 4.0 attribution, fewer than 10,000 calls/day, 5,000/hour,
  600/minute. A portfolio app with no ads or subscriptions is non-commercial. Attribution in the UI.
- Geocoding: Open-Meteo Geocoding API (`geocoding-api.open-meteo.com/v1/search`, free, no key)
  for city/town autocomplete, proxied by the backend so the frontend has a single API origin and the
  backend can cache and rate-limit.

### 5.3 Map rendering: MapLibre GL JS + OpenFreeMap vector tiles (no key)

OpenFreeMap: "no limits on the number of map views or requests... no API keys"; attribution is
added automatically by MapLibre. This avoids shipping any token to the browser. Mapbox GL JS would
require a public token and billing-tracked map loads. Weather heatmap is rendered as a GeoJSON grid
of corridor cells (fill layer) with per-hour risk properties, plus optional circle markers.

### 5.4 Credentials and billing

- No credentials are required for the default stack. Nothing billable is used.
- Optional: a Mapbox token only if Oliver wants the Mapbox adapter demonstrated.
- Hosting: Vercel Hobby (personal account `oliverleonor90`, already logged in via
  `vercel -Q ~/.vercel-personal`). No billing activation needed. See section 12.

---

## 6. Data models and API contracts

All times in the API are ISO-8601 UTC (`Z`). Distances in miles, durations in seconds, speeds in mph,
precipitation in inches per hour. Risk levels are strings and integers:

| level | name | int |
|---|---|---:|
| `low` | Low | 0 |
| `moderate` | Moderate | 1 |
| `high` | High | 2 |
| `severe` | Severe | 3 |
| `no_travel` | No Travel | 4 |
| `unknown` | Unknown (no usable forecast) | null |

### 6.1 `GET /api/health/`

`200 {"status": "ok", "version": "x.y.z", "providers": {"routing": "valhalla", "weather": "open-meteo"}}`

### 6.2 `GET /api/geocode/?q=<text>&limit=5`

`200 {"results": [{"name": "Denver", "admin1": "Colorado", "country_code": "US", "lat": 39.7392, "lon": -104.9903, "label": "Denver, Colorado, US"}]}`
`400` on empty/short query. Cached 1 h in-process.

### 6.3 `POST /api/routes/analyze/`

Request:

```json
{
  "origin":      {"lat": 39.7392, "lon": -104.9903, "label": "Denver, Colorado, US"},
  "destination": {"lat": 39.0997, "lon": -94.5786,  "label": "Kansas City, Missouri, US"},
  "departure_time": "2026-11-06T08:00:00-07:00",
  "load_weight_lb": 42000,
  "checkpoint_interval_miles": 25,
  "mode": "live"
}
```

Validation: lat in [-90, 90], lon in [-180, 180], origin != destination, `departure_time` must carry an
offset or `Z`, must be no earlier than 1 hour in the past and within 14 days ahead (forecast coverage);
`load_weight_lb` integer 0 to 200000; interval in {10, 25, 50}; `mode` in {`live`, `fixture`}
(default `live`; `fixture` is only honored when `ALLOW_FIXTURE_MODE=true`).
`checkpoint_interval_miles` defaults to 25. In `fixture` mode the origin and destination are
replaced by the recorded demo trip (Denver to Kansas City) and echoed as such.

Response `200`:

```json
{
  "request": { "...echo of validated input, departure_time_utc": "2026-11-06T15:00:00Z" },
  "provenance": {
    "mode": "live",
    "routing": {"provider": "valhalla", "endpoint": "valhalla1.openstreetmap.de", "costing": "auto", "fetched_at": "..."},
    "weather": {"provider": "open-meteo", "model": "best_match", "fetched_at": "...", "forecast_window": {"start": "...", "end": "..."}},
    "notes": ["Standard driving routes; truck restrictions not applied."]
  },
  "routes": [
    {
      "id": "route-1",
      "name": "Route A",
      "geometry": {"type": "LineString", "coordinates": [[lon, lat], ...]},
      "distance_miles": 604.1,
      "provider_distance_miles": 604.7,
      "duration_seconds": 31608,
      "departure_time": "2026-11-06T15:00:00Z",
      "arrival_time": "2026-11-07T00:46:48Z",
      "status": "ok | blocked | unverified",
      "checkpoints": [
        {
          "index": 0, "id": "route-1-cp-0", "kind": "origin | checkpoint | destination",
          "lat": 39.7392, "lon": -104.9903,
          "distance_miles": 0.0, "eta": "2026-11-06T15:00:00Z",
          "timezone": "America/Denver", "utc_offset_seconds": -25200,
          "attributed_miles": 12.5,
          "weather": {
            "forecast_time": "2026-11-06T15:00:00Z",
            "wind_mph": 12.3, "wind_gust_mph": 20.1, "rain_in_per_hr": 0.0, "snow_in_per_hr": 0.0,
            "temperature_f": 41.2, "weather_code": 3
          },
          "risk": {"level": "low", "value": 0, "drivers": [], "wind_level": "low", "rain_level": "low", "snow_level": "low", "load_rule_applied": null, "missing": []}
        }
      ],
      "summary": {
        "no_travel_miles": 0.0, "severe_miles": 0.0, "high_miles": 18.0, "moderate_miles": 75.0,
        "low_miles": 511.7, "unknown_miles": 0.0, "average_risk": 0.26,
        "coverage_complete": true, "max_level": "high"
      }
    }
  ],
  "recommendation": {
    "route_id": "route-2",
    "explanation": "Route B is recommended because it avoids 18.0 miles of severe weather encountered on Route A, despite adding 24 minutes of travel time.",
    "ranking": ["route-2", "route-1", "route-3"],
    "blocked_route_ids": [], "unverified_route_ids": []
  },
  "warnings": [{"code": "FEWER_ROUTES", "message": "The routing provider returned 2 distinct routes for this trip."}],
  "heatmap": {
    "base_time": "2026-11-06T15:00:00Z",
    "hours": ["2026-11-06T15:00:00Z", "... 49 timestamps ..."],
    "cell_size_miles": 23.08, "lat_step": 0.33409, "lon_step": 0.43178,
    "cells": [{"lat": 39.5, "lon": -104.2, "risk": [0, 0, 1, null, ...], "wind": [...], "rain": [...], "snow": [...]}]
  }
}
```

`recommendation.route_id` is `null` when no route qualifies; `explanation` then starts with
"No safe route is currently recommended." and lists the blocking conditions per route.

Contract notes (PR #2):

- `geometry` is simplified for display (about 30 m tolerance). `distance_miles` is the haversine
  length of the full geometry, which the risk mileage adds up to; `provider_distance_miles` is the
  routing provider's own total.
- `recommendation.ranking` lists eligible routes only (status `ok`), best first.
- `heatmap.lat_step` and `heatmap.lon_step` give the cell size in degrees, so the client draws each
  cell as centre plus or minus half a step. `heatmap.cells` is empty when the heatmap forecast
  failed; the routes are still returned.
- Warning codes: `FEWER_ROUTES`, `DUPLICATE_ROUTES_REMOVED`, `HEATMAP_UNAVAILABLE`, `DEMO_MODE`.

Error responses, all in the envelope `{"error": {"code", "message", ...}}`:

| Status | Code | Notes |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `details` holds the messages per field |
| 422 | `NO_ROUTE` | the provider found no drivable route |
| 422 | `TRIP_TOO_LARGE` | more than 450 checkpoint forecasts needed (section 9) |
| 429 | `THROTTLED` | per-client rate limit |
| 502 | `ROUTING_UNAVAILABLE`, `WEATHER_UNAVAILABLE`, `GEOCODING_UNAVAILABLE` | with `provider` |
| 504 | `ROUTING_TIMEOUT`, `WEATHER_TIMEOUT`, `GEOCODING_TIMEOUT` | with `provider` |

---

## 7. Weather risk classification rules

Exactly as specified by Spotter. Boundary convention (documented in README): every threshold listed
as "X to below Y" is the half-open interval `[X, Y)`; a value equal to a shared boundary belongs to the
**more severe** class; thresholds stated as "above" are strict (`>`).

Wind (mph, `wind_speed_10m`):

| Level | Condition |
|---|---|
| Low | `w < 25` |
| Moderate | `25 <= w < 35` |
| High | `35 <= w < 45` |
| Severe | `45 <= w < 55` |
| No Travel | `w >= 55` |

Rain (in/h, `rain + showers`):

| Level | Condition |
|---|---|
| Low | `r < 0.10` |
| Moderate | `0.10 <= r < 0.25` |
| High | `0.25 <= r < 0.50` |
| Severe | `0.50 <= r <= 1.00` |
| No Travel | `r > 1.00` |

Snow (in/h, `snowfall`):

| Level | Condition |
|---|---|
| Low | `s < 0.5` |
| Moderate | `0.5 <= s < 1.0` |
| High | `1.0 <= s < 2.0` |
| Severe | `2.0 <= s <= 3.0` |
| No Travel | `s > 3.0` |

Load-dependent rules (strict `>` comparisons):

1. `w >= 55` → No Travel regardless of load.
2. `45 <= w < 55` and `load > 30000` → No Travel.
3. `35 <= w < 45` and `load > 40000` → Severe.

Final checkpoint level = max severity over (wind level after load rules, rain level, snow level).
Severity order: Low < Moderate < High < Severe < No Travel. The response lists the `drivers`
(for example `["wind", "load_rule_2"]`) that produced the final level.

Missing data precedence (clarified after Codex review of PR #1):

1. If any *available* measurement conclusively establishes No Travel (wind `>= 55`, the 45 to 55 mph
   rule with load `> 30,000`, rain `> 1.00`, snow `> 3.0`), the checkpoint is **No Travel** and its
   `drivers` are kept. Missing data cannot make a prohibited condition less dangerous. The gaps are
   reported separately in `risk.missing` (subset of `wind`, `rain`, `snow`).
2. Otherwise, if any of wind, rain or snow is missing for the forecast hour, or the ETA falls outside
   the fetched forecast coverage, the checkpoint risk is `unknown` (`null`). A known Severe (or
   lower) level is not conclusive because the missing measurement could raise it. Unknown never
   becomes Low.
3. Otherwise the level is the maximum of the three conditions.

Route aggregation (PR #2) counts case 1 as No Travel miles (route blocked) and case 2 as unknown
miles (route unverified).

Precision (corrected after the PR #2 review): measurements are classified at the provider's
precision. They are normalized to six decimals only, which is far finer than the provider's
resolution (0.01 mm of rain is 0.0004 in) and removes binary floating-point noise (0.01 + 0.09 must
be 0.10, and 25.4 mm must be exactly 1.00 in), so a real threshold crossing is never rounded away:
25.41 mm of rain in the hour is 1.000394 in/h and is No Travel. Rain and showers are added before
any normalization. Rounding for display is separate, and a displayed measurement keeps enough
decimals to agree with its risk band ("1.0004 in/h", never "1.00 in/h", for a No Travel reading).
Tests cover 24.99, 25, 34.99, 35, 44.99, 45, 54.99, 55 mph; 30000 vs 30001 lb; 40000 vs 40001 lb;
rain 0.099/0.10/0.249/0.25/0.499/0.50/1.00/1.001; snow 0.49/0.5/0.99/1.0/1.99/2.0/3.0/3.001.

---

## 8. Route recommendation algorithm

Eligibility: a route is a candidate only if `status == "ok"`, meaning `no_travel_miles == 0` and
`coverage_complete == true`. Blocked (`no_travel_miles > 0`) and unverified (any unknown checkpoint)
routes are shown but never recommended.

Ordering of candidates is a deterministic lexicographic sort on the tuple
`(severe_miles, high_miles, average_risk, duration_seconds)`, ascending, with miles rounded to
0.1 and average risk rounded to 0.001 before comparison so floating noise cannot flip ties. Final
tie-break is the route id for determinism. No weighted formula.

Explanation generation (always from computed numbers): compare the winner with the best-ranked other
candidate (or, if the winner is the only candidate, with the blocked/unverified routes) and state the
first criterion that decided it, plus the travel-time delta, for example:

"Route B is recommended because it avoids 18.0 miles of severe weather encountered on Route A,
despite adding 24 minutes of travel time."

When a third eligible route exists, one more sentence names the first criterion that puts the
winner ahead of it (for example "It also has 50.0 fewer miles of severe weather than Route A."),
so a faster route that lost on weather is always accounted for. Blocked and unverified routes are
then listed with their reason.

If there is no candidate: `route_id = null` and the explanation is
"No safe route is currently recommended." followed by, per route, the blocking conditions
(for example "Route A: No Travel at checkpoint 7 near 39.41, -102.33 at 18:00 MST (wind 58 mph)") or
"Route C could not be verified: forecast unavailable for 3 checkpoints."

### 8.1 Mileage calculation

- Cumulative distance along the decoded geometry uses the haversine distance between consecutive
  shape points (summed), not the provider's rounded total; the provider total is reported alongside.
- Checkpoints are interpolated at `k * interval` miles along the geometry for `k = 1..`, plus origin
  (0 mi) and destination (total mi). A final checkpoint closer than 10 % of the interval to the
  destination is dropped in favor of the destination (the final partial segment is still counted).
- Each mile of the route is attributed to its nearest checkpoint along the route (midpoint split):
  checkpoint `i` owns `(d_i - d_{i-1}) / 2 + (d_{i+1} - d_i) / 2`; origin and destination own half of
  their single adjacent segment. Sum of attributed miles == total miles exactly (verified in tests).
- `severe_miles`, `high_miles`, `moderate_miles`, `low_miles`, `no_travel_miles`, `unknown_miles` are
  sums of attributed miles by checkpoint level. Average risk is the attributed-miles-weighted mean of
  the integer levels over known checkpoints; `null` when nothing is known.
- Risk mileage is never `count * interval`.

---

## 9. Checkpoint and ETA calculations

- Geometry: polyline6 decoded to `[lon, lat]` pairs; legs concatenated.
- ETA profile: Valhalla maneuvers give `time` and `length` per maneuver with shape index ranges, so
  elapsed time is accumulated per maneuver and interpolated proportionally to distance inside a
  maneuver. Fallback (if maneuver data is missing): proportional to distance over the total duration.
  Documented in README.
- `eta_i = departure_time_utc + elapsed(d_i)`. Changing departure time shifts every ETA, which changes
  the forecast hour selected and therefore the risk.
- Forecast hour selection: **nearest hourly timestamp** to the ETA (ties round down). The selected
  `forecast_time` is returned per checkpoint. No interpolation between hours.
- Coverage: one forecast window serves the checkpoints and the heatmap, from
  `floor(departure) - 1 h` to the later of `ceil(last arrival) + 1 h` and `floor(departure) + 48 h`
  (bounded by Open-Meteo's 16-day horizon). Nothing is extrapolated: a checkpoint whose ETA is more
  than 30 minutes outside the returned series is `unknown`.
- Timezones: input offset is honored and converted to UTC; all arithmetic is in UTC; each checkpoint
  carries the IANA timezone from Open-Meteo for local display (DST handled by the zone database in
  the browser via `Intl.DateTimeFormat`). Backend tests cover a DST transition (for example
  2026-11-01 in `America/Denver`) and a non-UTC input offset.
- Batching and limits: points are deduplicated on 3-decimal coordinates, requested in batches of up to
  50 locations per Open-Meteo call, at most 4 concurrent weather calls, with a 10-minute in-process
  TTL cache keyed by (rounded lat, lon, window, variables). Valhalla calls are sequential (one
  connection) with a 25 s timeout and one retry on connection errors only. One analysis may request
  at most 450 checkpoint forecasts across its routes (`TRIP_TOO_LARGE` otherwise). This is an
  application performance and fair-use safeguard: it bounds the response size and analysis time
  and keeps a single analysis a modest load on the free weather service.

---

## 10. Map and heatmap implementation

### 10.1 Map

- MapLibre GL JS with the OpenFreeMap `positron`-style light basemap (or `liberty`), created once.
- Sources: `routes` (FeatureCollection of LineStrings with `id`, `selected`, `status`),
  `checkpoints` (Points with `risk`, `selected`), `heatmap-cells` (Polygons), `truck-position`
  (optional Point for the slider hour).
- Layers: unselected routes (slate, 4 px, 0.6 opacity), selected route (teal, 6 px, with a darker
  casing), checkpoint circles colored by risk (gray for unknown, hatched/outlined for blocked),
  heatmap fill, labels for origin/destination.
- Interactions: card click → `selected` property updated with `source.setData()` (three small
  features); checkpoint click → detail panel with measurements, forecast time and ETA; `fitBounds`
  on new results only.
- Risk colors (consistent across map, cards and legend): Low `#22c55e`, Moderate `#eab308`,
  High `#f97316`, Severe `#dc2626`, No Travel `#7f1d1d` with hatch, Unknown `#94a3b8`.

### 10.2 Heatmap

- Grid: the union bounding box of all routes, padded by 10 % (at least 20 miles), covered by a grid
  that is square in miles. Each cell center is a weather sample point. Cells farther than 60 miles
  from every route are dropped so the overlay reads as a corridor, and the cell size is the
  smallest one (at least 5 miles) for which the kept cells number at most 144. The response gives
  the cell size in miles and in degrees (`lat_step`, `lon_step`).
- Data: for each cell, 49 hourly values (hours 0 to 48 from `base_time` = departure floored to the
  hour) of wind/rain/snow and the resulting risk level computed with the **same classifier** and the
  request's load weight. Returned once in the analysis response (`heatmap`), roughly 100 to 200 KB.
- Rendering: one GeoJSON source whose features carry `r_0 .. r_48`; the slider sets a `fill-color`
  expression `['match', ['get', 'r_<h>'], 0, low, 1, moderate, ...]` with throttled updates (one
  per animation frame). No source rebuild, no network call per move. Label shows the exact timestamp
  (local time with zone abbreviation and the UTC value on hover).
- Distinction from checkpoint risk: the legend and the slider panel state "Corridor forecast at
  <timestamp>" while checkpoint markers are labeled "Risk at estimated arrival". Toggles: heatmap,
  checkpoints, unselected routes.
- Performance: cells are built once per analysis; React state for the slider lives in a small
  component so the rest of the tree does not re-render; `requestAnimationFrame` throttling.

---

## 11. Testing and acceptance criteria

Backend (pytest, `backend/tests/`):

- Risk table: every boundary listed in section 7, multi-condition max, load rules with strict
  comparisons, No Travel overrides, missing data → unknown.
- Recommendation: severe beats high; high beats average; average beats duration; duration tie-break;
  blocked route never recommended; all blocked → `route_id null` with explanation; unverified excluded.
- Sampling: 10/25/50 intervals on a synthetic geometry with known lengths, short route (< interval),
  final partial segment, attributed miles sum to total, ETA monotonic and departure-shifted, DST and
  offset handling, nearest-hour selection, out-of-coverage → unknown.
- Providers: Valhalla and Open-Meteo clients with recorded JSON fixtures (HTTP mocked with `respx`),
  unit validation and fallback conversion, dedupe of identical geometries, fewer-than-three warning.
- API: `POST /api/routes/analyze/` end to end with mocked providers; validation errors; 502/504 paths.
- Live smoke: `pytest -m live` hits the real providers for Denver to Kansas City (skipped in CI by
  default, run manually and recorded in the PR report).

Frontend (Vitest + React Testing Library): form validation, route cards rendering and selection,
risk formatting utilities, local-time formatting with timezones, slider label.

E2E (Playwright, mocked `/api` via route interception, desktop 1280 px and mobile 375 px): submit
trip, three cards, recommendation badge, select route, click checkpoint, change load weight, move
slider (assert paint/label update), API failure state. One live smoke spec against the local backend.

Acceptance per PR is listed in section 14.

---

## 12. Deployment strategy

- Frontend: Vercel Hobby, personal account `oliverleonor90` (`vercel -Q ~/.vercel-personal`),
  project `stormroute` (Vite static build). `VITE_API_BASE_URL` points at the backend.
- Backend: Vercel Hobby too, second project `stormroute-api`, Python runtime 3.14 (from
  `.python-version`), Django served as a WSGI app by Vercel Functions, 300 s max duration, no billing
  required. Rationale: already authenticated account, HTTPS and env management included, no card,
  no sleeping dynos. Trade-off: the in-process cache is per warm instance (documented), and an
  alternative (Render free tier) would need a new account and sleeps after inactivity.
- Production settings: `DEBUG=False`, `SECRET_KEY` from env, `ALLOWED_HOSTS` from env,
  `CORS_ALLOWED_ORIGINS` = the frontend origin only, `SECURE_PROXY_SSL_HEADER`, HSTS,
  pinned `requirements.txt`, `/api/health/` for checks, `ALLOW_FIXTURE_MODE=true` so the demo mode is
  available but labeled.
- Verification (section 11 of the brief): homepage, map tiles, analyze request against production
  backend, weather and risk returned, route selection, slider, no secrets in bundle, no console
  errors, 375 px rendering. Recorded in `docs/VERIFICATION.md` with timestamps.

Backend hosting on the personal Vercel account was approved on 2026-11-05 (decision D2).

---

## 13. Assumptions, limitations and technical risks

Assumptions:

- A1. Autocomplete is place-level (cities/towns via Open-Meteo geocoding), which is adequate for
  intercity trucking trips; street addresses are out of scope.
- A2. Departure times within the next 14 days (forecast horizon with margin); past departures are
  rejected (forecast, not reanalysis).
- A3. Risk is evaluated at checkpoints only; the heatmap is a corridor overview and is not used for
  the recommendation.
- A4. Wind risk uses sustained 10 m wind speed. Gusts are shown but not classified (rules say wind
  speed).

Limitations (disclosed in README and UI):

- L1. Routes are standard driving routes (Valhalla `auto` costing). Truck restrictions (bridge
  weights, low clearances, hazmat) are not applied, and load weight is cargo weight, not GVW.
- L2. Forecasts are model output (Open-Meteo best_match) with hourly resolution; nearest-hour
  selection can be up to 30 minutes off the ETA.
- L3. The public Valhalla and Open-Meteo services have no SLA. Fixture mode exists for demos.
- L4. Fewer than three routes can occur; the UI states how many distinct routes were returned.
- L5. Non-commercial terms: the deployment is a portfolio demo.

Risks and mitigations:

- R1. Public Valhalla instability or blocking → identifying User-Agent, single connection, caching,
  fixture mode, Mapbox adapter as documented fallback.
- R2. Open-Meteo rate limits with the heatmap grid (up to 144 cells + checkpoints per analysis) →
  batches of 50 locations, TTL cache, grid capped, 49-hour window only.
- R3. Vercel Python cold starts / 300 s limit → total upstream time is a few seconds; timeouts set
  below the limit; health endpoint.
- R4. Time budget (16 h) → PR scope is strict; optional items are listed and skipped first.
- R5. Deadline unknown → see section 15; confirm the start of the 4-day window before PR #1.

---

## 14. Implementation phases and PR boundaries

| PR | Title | Status | Budget | Actual |
|---|---|---|---:|---:|
| 0 | Preflight, spec, repo bootstrap | Merged (direct push, authorized) | 1.0 h | 0.5 h |
| 1 | Project foundation and risk engine | Merged (squash, `5265147`) | 2.0 h | 0.5 h |
| 2 | Routing, weather, recommendation backend | Merged (squash, `14b4a05`) | 4.0 h | 0.7 h |
| 3 | React dashboard and interactive map | Merged (squash, `c52e9c7`) | 3.5 h | 0.6 h |
| 4 | Weather heatmap and forecast slider | Merged (squash, `b761b38`) | 2.5 h | 0.3 h |
| 5 | Production deployment and submission prep | Ready for Codex Review (deployed and verified) | 2.5 h | 0.5 h |
| | Reserve for review fixes and verification | | 1.0 h | |
| | **Total** | | **16.0 h** | |

### PR #0 (bootstrap, pushed directly to `main` with Oliver's go-ahead)

Scope: `spec.md`, `.gitignore`, minimal `README.md` stub, `.env.example`. Needed so PR #1 has a base.

### PR #1: Project foundation and risk engine

Branch `feat/pr1-foundation-risk-engine`.
Scope: Django project (`config`, settings split, DRF, CORS, health endpoint), Vite React TS app with
Tailwind and routing shell, shared API types (`frontend/src/types/api.ts`), `risk/classification.py`
(wind/rain/snow/load rules), `risk/levels.py`, pytest config, Vitest config, lint/format config
(ruff, eslint, prettier), `docs/ARCHITECTURE.md` skeleton, and an early Vercel **preview** deployment
of the backend health endpoint on the personal account (hosting smoke test requested by Oliver).
Acceptance: `python manage.py runserver` serves `/api/health/`; `npm run dev` renders the shell;
`pytest` passes the full boundary table (section 7); logic is pure and deterministic.

**Status: Merged** (2026-11-05, squash commit `5265147`). PR: https://github.com/Oliver-Leonor/spotter-weather-routing/pull/1
(branch `feat/pr1-foundation-risk-engine`).

Implementation summary:
- Backend: Django 6.1.3 + DRF 3.18.3, settings split (`base`/`dev`/`test`/`prod`), no database,
  JSON-only renderer, uniform error envelope (`analysis/exceptions.py`, also defines `UpstreamError`
  for PR #2), CORS, anon throttle, `GET /api/health/`.
- Risk engine: `risk/levels.py` (`RiskLevel` IntEnum 0..4), `risk/classification.py` (pure
  `classify_wind/rain/snow`, `apply_load_rules`, `classify_checkpoint` returning a frozen
  `CheckpointRisk` with per-condition levels, drivers and the applied load rule; missing/NaN/negative
  inputs yield `unknown`, never Low).
- Frontend: Vite 8 + React 19 + TypeScript strict + Tailwind 4 + TanStack Query + MapLibre GL +
  lucide (installed, map wiring in PR #3), app shell with empty state, `types/api.ts` contract,
  `lib/risk.ts` colors/labels/values, Vitest + RTL + jsdom, Prettier, oxlint.
- Hosting smoke test (requested by Oliver): backend deployed to the personal Vercel Hobby account,
  project `stormroute-api`, public domain https://stormroute-api-navy.vercel.app/api/health/
  verified live with production settings (`DEBUG=False`, HTTPS redirect 308, HSTS, CORS limited to
  the configured origin, custom 405/404 envelopes). Findings recorded in the decision log.

Test results (2026-11-05): backend `pytest` 69 passed (65 risk-table/boundary/load/missing-data
cases + 4 health/error-envelope API tests), `ruff check` and `ruff format --check` clean; frontend `vitest` 3 passed,
`tsc -b` clean, `oxlint` clean, `prettier --check` clean, `vite build` OK.

Codex review round 1 (2026-11-05): finding accepted. Unresolved paths were answered by Django's
HTML 404 (URL resolution fails before any DRF view, so the DRF exception handler never runs).
Fix: `analysis/errors.py` JSON `handler404`/`handler500` registered in `config/urls.py`;
`test_unknown_api_route_is_404_json` now asserts content type and body, plus tests for non-API
paths and the 500 handler. Backend suite: 62 passed. Production backend redeployed and re-verified.

Codex review round 2 (2026-11-05): P2 finding accepted. A conclusive No Travel measurement (wind
>= 55, load rule 2, rain > 1.00, snow > 3.0) was downgraded to `unknown` when another measurement
was missing. Fix in `risk/classification.py`: conclusive No Travel takes precedence over gaps; a new
`missing` list (and `is_complete`) reports the gaps separately; non-conclusive known levels still
yield `unknown`. Spec section 7 documents the precedence. Backend suite: 69 passed (8 new tests).
Frontend `CheckpointRisk` type gained `missing`.

Review round 3 (2026-11-05): no blocking findings at `1e43ffe`. Before the merge the full suite was
rerun independently (backend 69 passed, frontend 3 passed, lint and typecheck clean) and the
deployed health endpoint was rechecked. Oliver authorized the squash merge.

Known issues: none open. Frontend map/heatmap and all provider code are intentionally absent (PR #2
to #4).

### PR #2: Routing, weather and recommendation backend

Branch `feat/pr2-analysis-backend`.
Scope: Valhalla client + polyline6 decoding + dedupe, sampling and ETA profile, Open-Meteo client with
unit validation, batching, concurrency and cache, segment attribution and aggregation, recommendation
and explanation, heatmap grid builder (data only), `POST /api/routes/analyze/`, `GET /api/geocode/`,
fixture mode with recorded responses, error mapping (400/422/502/504), tests from section 11 (backend),
live smoke test executed once and recorded.
Acceptance: valid analysis for Denver to Kansas City with three routes; ETAs shift with departure
time and change the selected forecast hour; recommendation order verified by tests; blocked and
unverified routes handled; `docs/ASSUMPTIONS.md` written.

**Status: Merged** (2026-11-05, squash commit `14b4a05`, after the review round 1 fix). PR:
https://github.com/Oliver-Leonor/spotter-weather-routing/pull/2 (branch `feat/pr2-analysis-backend`).

Implementation summary:
- Routing: `routing/geometry.py` (polyline6 decoding, haversine distances, interpolation, display
  simplification, near-identical route detection), `routing/sampling.py`, `routing/eta.py`, and the
  Valhalla client (one request at a time, identifying User-Agent, 10-minute cache, 422/502/504
  mapping).
- Weather: Open-Meteo client (units verified on every response with metric fallback, values kept
  at provider precision, batches of 50, at most 4 concurrent, per-place cache, horizon clamp), nearest-hour
  selection, geocoding proxy.
- Risk: `risk/aggregation.py` and `risk/recommendation.py`, both pure.
- Analysis: orchestration service, corridor heatmap, `POST /api/routes/analyze/`,
  `GET /api/geocode/`, request validation, per-client rate limits, error mapping.
- Demo mode: a recorded real Valhalla response (Denver to Kansas City) with scripted weather that
  is labeled in every response and is not a forecast (decision log).
- Docs: `docs/ASSUMPTIONS.md`, architecture and README updates; frontend `types/api.ts` synced with
  the contract.

Test results (2026-11-05): backend `pytest` 360 passed, 1 deselected (the live test); `ruff check`
and `ruff format --check` clean. Frontend `vitest` 3 passed; `tsc -b`, `oxlint` and
`prettier --check` clean.

Live smoke test (2026-11-05 10:33 Asia/Manila, `pytest -m live -s`, run once): Denver to Kansas
City through the API against the real Valhalla and Open-Meteo services. Three distinct routes
(604.1 / 613.5 / 634.8 miles; 8.78 / 9.53 / 9.84 h), 26 / 26 / 27 checkpoints at 25 miles, a real
forecast at every checkpoint, heatmap of 140 cells of 23.1 miles. A departure 6 hours later
shifted every ETA by 6 hours and selected forecast hours 6 hours later. First call 4.9 s, repeat
0.09 s (cache), response 176 KB. The weather was calm (all Low), so the fastest route was
recommended.

Not deployed: production still serves only the PR #1 health endpoint. Deploying the analysis
endpoints is PR #5 scope and needs the FOSSGIS notification decision (D3) first.

Review round 1 (2026-11-05): the GitHub Codex bot reviewed `981d23e` with no findings. An
independent inspection raised one P2 finding, accepted: weather values were rounded to three
decimals before classification, so 25.41 mm of rain (1.000394 in/h) was classified Severe instead
of No Travel, and 54.99997 mph could be rounded up to 55. Fix: `weather/open_meteo.py` keeps
provider precision (normalized to six decimals, rain and showers added first), unit factors are
exact, and `risk/formatting.py` formats displayed measurements so they never contradict their band.
Section 7 documents the rule. Backend suite: 382 passed (22 new tests at the rain, snow and wind
thresholds, through the parser, the service and the API).

Known issues and limits: caches and rate limits are per process (per warm instance on Vercel).

### PR #3: React dashboard and interactive map

Branch `feat/pr3-dashboard-map`.
Scope: trip planner form (autocomplete, datetime, load weight, interval), TanStack Query wiring,
route comparison cards with recommended badge and No Travel warnings, MapLibre map with routes,
checkpoints, selection, popups/detail panel, fit bounds, loading/empty/error states, responsive
layout (375 px), attribution footer, and a prominent, persistent "simulated weather" label whenever
demo mode is shown. Vitest component tests.
Acceptance: full analysis through the UI against the local backend; route selection and checkpoint
detail work; mobile layout verified with screenshots.

**Status: Merged** (2026-11-05, squash commit `c52e9c7`, after two review rounds). PR:
https://github.com/Oliver-Leonor/spotter-weather-routing/pull/3 (branch `feat/pr3-dashboard-map`).
The Codex bot had reviewed `0d84a64`; its last finding was fixed in `a069cf9`, which Oliver merged
without a further bot review.

Implementation summary:
- Trip form (`features/trip-planner`): city and town search as an accessible combobox (debounced,
  keyboard and pointer), departure in the browser's time zone sent as UTC, load weight, 10/25/50
  mile interval, client-side validation that mirrors the API, server field errors shown on the
  field. "Run the demo trip" loads the recorded trip with simulated weather.
- Route comparison (`features/route-comparison`): recommendation banner with the backend's
  explanation (or "No safe route is currently recommended"), one card per route with travel time,
  distance, arrival in the destination's time zone, Blocked / Unverified / Recommended status and
  a **risk ribbon**: the route drawn as a strip, each stretch as wide as the miles its checkpoint
  owns and colored by the risk at arrival. Checkpoint detail panel with measurements, per-condition
  levels, the load rule that applied, the forecast hour used and previous/next stepping.
- Map (`features/route-map`): MapLibre GL with OpenFreeMap tiles, created once and updated with
  `setData`. All routes, the selected one highlighted, checkpoints colored by risk, start and end
  markers, fit to bounds once per analysis, click a route or a checkpoint to select it. Loaded
  lazily in its own chunk.
- States: loading, empty, provider failure with "Try again", validation failure. Results are
  removed as soon as a new comparison starts, and every result names the trip it was computed for.
  Warnings from the API are shown.
- Demo mode: a sticky hazard-striped "Simulated weather" band stays on screen for as long as demo
  results are shown, with a second label on the map.
- Responsive: one column on small screens (form, recommendation, map, cards) with the result and
  checkpoint details scrolled into view; a scrolling rail beside a full-height map on large ones.
- Attribution footer (OpenStreetMap with the fixthemap link, FOSSGIS, Open-Meteo CC BY 4.0,
  OpenFreeMap) and the routing limitation notes from the API.

Test results (2026-11-05): frontend `vitest` 87 passed (API client, formatting, map data, ribbon,
place search, trip form, route card, recommendation, checkpoint detail, full App flows); `tsc -b`,
`oxlint` and `prettier --check` clean; `vite build` OK (app 289 kB / 91 kB gzip, map chunk
1,081 kB / 294 kB gzip, loaded lazily). Backend unchanged: `pytest` 382 passed.

Browser verification (2026-11-05, Chromium via Playwright against the local backend, no console
errors): demo trip at 1440 x 900 and 375 x 812; a live Denver to Kansas City trip typed through the
form (place search, real Valhalla and Open-Meteo, three route cards, 8.0 s including typing);
clicking a checkpoint and a route line on the map; changing the load to 28,000 lb and comparing
again; no horizontal overflow at 375 px. Screenshots: `docs/screenshots/pr3-*.png`.

Codex review round 1 (2026-11-05, at `926b16c`): two P2 findings, both accepted.

1. Keyboard users could not open checkpoint details: the ribbon segments were pointer-only and the
   Previous/Next buttons only exist once a checkpoint is open. Fix: the ribbon is now a single tab
   stop with a roving focus. Arrow, Home and End keys move between checkpoints, Enter or Space
   opens the focused one, the tab stop returns to the selected checkpoint, the focus ring is
   visible and each segment has a label and a pressed state. Nothing requires the map.
2. A failed comparison left the earlier routes and recommendation on screen while the form could
   describe a different trip. Fix: results are removed as soon as a new comparison starts, so they
   never sit beside a pending or failed request, and every result now carries an "Analyzed trip"
   line (origin, destination, departure, load, interval).

Frontend suite after the fixes: 95 passed (8 new tests, including a keyboard-only flow through the
whole App and a failed request after a successful one); `tsc -b`, `oxlint`, `prettier --check`
clean. Rechecked in Chromium with the keyboard only and with the backend stopped mid-session.

Codex review round 2 (2026-11-05, at `0d84a64`): both round 1 fixes verified; one new P2 finding,
accepted. A validation error for a request field that has no input in the form was invisible: with
`ALLOW_FIXTURE_MODE=false` the 400 carries `details.mode`, and the alert only said "Check the
highlighted fields" with nothing highlighted. Fix: the alert now lists every validation message
whose field has no input in the form (`mode`, `checkpoint_interval_miles`, non-field errors), says
"Check the highlighted fields" only when a form field really is highlighted, and falls back to the
server message when there are no details. Frontend suite: 98 passed (3 new tests). Rechecked in
Chromium against a backend started with demo mode disabled: the alert reads "Demo mode is not
enabled on this server."

Known issues: none open. The heatmap layer and forecast slider are PR #4; the Playwright e2e suite
is PR #4.

### PR #4: Weather heatmap and forecast slider

Branch `feat/pr4-heatmap-slider`.
Scope: heatmap source/layer, slider (0 to 48 h) with exact timestamp, paint-expression updates with
rAF throttling, layer toggles, legend, optional truck-position marker, Playwright e2e (desktop and
mobile), accessibility pass (labels, focus, keyboard slider).
Acceptance: slider changes the visualization with no network calls (verified in Playwright by
counting requests); smooth interaction; e2e suite green at both widths.

**Status: Merged** (2026-11-05, squash commit `b761b38`; the Codex re-review of `c7796e9` found no
issues). PR: https://github.com/Oliver-Leonor/spotter-weather-routing/pull/4 (branch
`feat/pr4-heatmap-slider`).

Implementation summary:
- Corridor heatmap (`features/heatmap/heatmapData.ts`, map layer in `RouteMap.tsx`): one GeoJSON
  source of cell rectangles built once per analysis, each carrying its risk for all 49 hours
  (`r_0` to `r_48`). The fill layer sits under the basemap labels. Calm cells are faint so the
  weather stands out; hours without a forecast are grey, never a risk color.
- Forecast slider (`ForecastSlider.tsx`): 0 to 48 hours, exact local time of the chosen hour with
  the UTC value on hover, time before or after the real departure, `aria-valuetext` with both,
  keyboard support.
  The thumb and label follow at once; the map is updated at most once per animation frame.
- No re-render, no rebuild, no request per move: the chosen hour lives in a small store outside
  React (`hourStore.ts`). The map subscribes to it and swaps two paint expressions.
- Truck marker (the optional item): the expected position on the selected route at the chosen
  hour, interpolated from the checkpoint ETAs, so the corridor forecast can be read against where
  the truck would be.
- Layer switches for the weather corridor, checkpoints and other routes. A hidden route cannot be
  selected by clicking where it was.
- The panel states the difference: shading is the corridor forecast at the chosen time;
  checkpoints keep showing the risk at their own arrival time. If the corridor forecast could not
  be loaded, the slider is replaced by a note and the routes are unaffected.
- Playwright e2e suite (`frontend/e2e`, `npm run e2e`): 11 specs at 1280 px and 375 px (22 runs),
  hermetic. The API is mocked with recorded responses of the real backend, the map style is a
  blank style and web fonts are blocked, so nothing leaves the machine.

Test results (2026-11-05): frontend `vitest` 126 passed; Playwright 22 passed (run three times,
stable); `tsc -b` (now also covering `e2e/` and the Playwright config), `oxlint` and
`prettier --check` clean; `vite build` OK. Backend unchanged: `pytest` 382 passed.

Acceptance evidence:
- No network calls per slider move: the e2e test records every request the page makes while the
  slider goes to hour 6 and hour 48 and asserts the list is empty. A manual sweep through all 49
  positions against the real backend took 0.77 s with 0 requests.
- The visualization changes: pictures of the map canvas alone (markers, panels and controls hidden)
  differ between the departure hour and the storm hour, and are identical again at +48 h when the
  demo weather repeats. Switching the corridor off and on gives the same picture back.
- Both widths: all specs pass at 1280 px and 375 px, with no horizontal overflow.
- Screenshots: `docs/screenshots/pr4-*.png`.

Codex review round 1 (2026-11-05, at `35f50ff`): one P2 finding, accepted. The forecast hours start
at the top of the departure hour, but the slider called hour 0 "At departure" and counted the
other hours from it. For a 3:45 PM departure, hour 0 is 45 minutes before departure and hour 1 only
15 minutes after it. Fix: the slider now receives the real departure time and measures every hour
from it ("45 min before departure", "15 min after departure", "1 h 15 min after departure"), in
the visible label and in the screen-reader text alike. The tick marks under the slider are clock
times ("Fri 8 AM") instead of "Departure / +24 h / +48 h". The 49 forecast timestamps and the map
painting are unchanged. Frontend suite: 136 passed (10 new tests, including departures at 45 past
the hour through the slider and through the whole App); Playwright 22 passed. Rechecked in Chromium
against the real backend with a departure at 8:45 AM.

Known issues: none open. The truck marker moves in straight lines between checkpoints, which is an
approximation of the road (noted in the code).

### PR #5: Production deployment and submission preparation

Branch `feat/pr5-deploy-docs`.
Scope: production settings, Vercel projects (frontend + backend), env configuration, production smoke
verification (`docs/VERIFICATION.md`), README (all 12 sections of the brief), screenshots,
`docs/LOOM_SCRIPT.md`, final `spec.md` reconciliation, AI-assistance disclosure.
Acceptance: hosted app verified end to end against the production backend; all checklist items in
section 16 checked or explicitly reported.

**Status: Ready for Codex Review** (2026-11-05). Branch `feat/pr5-deploy-docs`. **Both applications
are deployed to production and verified.**

- Frontend: https://stormroute-three.vercel.app (Vercel project `stormroute`)
- Backend: https://stormroute-api-navy.vercel.app (Vercel project `stormroute-api`)
- Account `oliverleonor90`, personal scope, Hobby plan. No paid resource.

Sequence on 2026-11-05: Oliver approved the deployment on two conditions (notify the Valhalla
maintainers first; make the README's AI disclosure precise). The README was corrected. Oliver
posted the usage notice himself (https://github.com/valhalla/valhalla/discussions/6465); it was checked to be authored by `Oliver-Leonor` and
to carry the agreed wording. The frontend was then deployed to learn its domain, the backend's
`CORS_ALLOWED_ORIGINS`, `VALHALLA_CLIENT_ID` and `ALLOW_FIXTURE_MODE` were set, and the backend
was deployed.

Production verification (2026-11-05, details in `docs/VERIFICATION.md`):
- `scripts/verify_deployment.py --live`: 12 of 12 checks passed, including one live analysis
  (three routes of 604.1 / 613.5 / 634.8 miles, a forecast at 79 of 79 checkpoints).
- Browser checks on the deployed app at 1440 x 900 and 375 x 812: 17 of 17 passed (demo labeled
  as simulated, load rule changes the result, slider with 0 requests, no console errors, no
  horizontal overflow).
- Backend runtime logs: no error lines.

Codex review: the bot reviewed `d941054` with no findings. The commits after it (README wording,
notice text, deployment records) have not been reviewed yet.

Done in this PR:
- Valhalla etiquette: every routing request carries an `X-Client-Id` header
  (`VALHALLA_CLIENT_ID`), as the Valhalla documentation asks of apps published to end users.
- Frontend hosting config: `frontend/vercel.json` (build, output directory, security headers,
  long-lived caching for hashed assets).
- `scripts/verify_deployment.py`: checks a deployed backend and frontend end to end (health, HTTPS
  redirect, JSON 404, debug off, CORS for the frontend and against another origin, validation
  envelope, place search, demo analysis, one optional live analysis, and that the frontend bundle
  points at the API and holds no secret) and prints the table for `docs/VERIFICATION.md`.
- Dress rehearsal on a local machine with the production settings module and a production build
  of the frontend: every check passed, including one live analysis (three routes, 79 of 79
  checkpoints with a forecast).
- Documents: complete `README.md` (what it does, risk rules, recommendation, architecture,
  providers, running, API, tests, deployment, limitations, AI assistance, attribution),
  `docs/DEPLOYMENT.md` (runbook, environment variables, a draft of the Valhalla notification),
  `docs/VERIFICATION.md`, `docs/LOOM_SCRIPT.md`, and a ready GitHub Actions workflow in
  `docs/ci/github-actions-ci.yml` (not active: the token cannot push workflow files).
- Housekeeping: unused Vite template assets removed.

Test results (2026-11-05): backend `pytest` 384 passed, 1 deselected; `ruff` clean. Frontend
`vitest` 136 passed; Playwright 22 passed; `tsc -b`, `oxlint`, `prettier --check`, `vite build`
clean.

Still to do:
1. Codex review of the final PR head, then Oliver's decision on merging PR #5.
2. Oliver records the Loom walkthrough (`docs/LOOM_SCRIPT.md`) and adds the link to the README.
3. Oliver confirms when Spotter's four-day window began (D1), before submitting.
4. Watch the usage notice for a reply. If the maintainers object, switch live routing off.

Optional (only if time remains after PR #5 acceptance): Mapbox adapter, truck-position marker
animation, CSV export of checkpoints.

---

## 15. Open decisions and blockers

- [ ] D1. **Deadline: UNCONFIRMED.** Oliver will confirm when Spotter sent the assessment (start of
      the 4-calendar-day window) and the due time zone. No submission deadline is assumed or invented
      until then.
- [x] D2. **Backend hosting:** approved 2026-11-05. Personal Vercel Hobby account for both frontend
      and backend. No Juris Digital accounts or infrastructure. No paid services without approval.
      An early Vercel smoke deployment of the Django health endpoint is added to PR #1 scope.
- [x] D3. **Routing:** Valhalla approved 2026-11-05 as the default provider behind an adapter
      interface. Standard driving routes, limitation documented. FOSSGIS fair use respected
      (identifying headers, caching, low volume). Before the public production deployment, flag the
      FOSSGIS/Valhalla maintainers' requested GitHub Discussions notification for Oliver's approval
      (tracked in PR #5). No Mapbox token for now.
- [x] D4. **Bootstrap push:** approved 2026-11-05 as a one-time exception, limited to `spec.md`,
      `.gitignore`, `.env.example` and the initial README.

No credentials are required for the default plan.

---

## 16. Progress checklist (final acceptance)

- [x] React frontend implemented (PR #3 dashboard and map, PR #4 heatmap and slider)
- [x] Django backend implemented (PR #1 scaffold and risk engine; PR #2 routing, weather,
      recommendation and API)
- [x] Origin and destination work (PR #3)
- [x] Departure date and time work (PR #3)
- [x] Load weight works (PR #3)
- [x] Three distinct routing API routes verified for a demonstration trip (PR #2 live smoke test
      through the API: Denver to Kansas City, 604.1 / 613.5 / 634.8 miles; UI in PR #3)
- [x] 10/25/50-mile checkpoint sampling works (API, PR #2; UI control in PR #3)
- [x] Checkpoint ETAs are calculated (PR #2)
- [x] Weather is retrieved for checkpoint arrival times (PR #2)
- [x] All Spotter risk rules are correctly implemented (PR #1, 65 classifier tests; route-level wiring in PR #2)
- [x] Load-dependent rules work (PR #1 classifier; end-to-end in PR #2)
- [x] No Travel rules work (PR #2: a blocked route is never recommended)
- [x] Route recommendations follow the required priority order (PR #2)
- [x] All routes are displayed on the map (PR #3)
- [x] Checkpoint details work (PR #3)
- [x] Weather heatmap works (PR #4)
- [x] 0 to 48 hour forecast slider works (PR #4: no request per move, verified in Playwright)
- [x] Application is responsive (PR #3: verified at 375 px and 1440 px)
- [x] Automated tests pass (backend 382, frontend 126, Playwright 22 at two widths)
- [x] Live provider integration verified (PR #2 live smoke test, 2026-11-05)
- [x] Production frontend verified (PR #5, 2026-11-05)
- [x] Production backend verified (PR #5, 2026-11-05)
- [x] GitHub repository pushed under Oliver-Leonor
- [x] README completed (PR #5; the hosted URL and video link are added after deployment)
- [x] Loom recording script prepared (PR #5, `docs/LOOM_SCRIPT.md`)
- [ ] Final Loom video recorded and linked by Oliver
- [ ] Total working time within 16 hours

---

## 17. Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-05 | Valhalla (FOSSGIS public) instead of Mapbox Directions as the default router | Verified 3 distinct routes on 5/5 corridors with no key; Mapbox needs a token and caps at 2 alternatives, not guaranteed. |
| 2026-11-05 | Valhalla `auto` costing, not `truck` | `truck` returned only 1 route for Denver to Kansas City; limitation disclosed. |
| 2026-11-05 | MapLibre GL + OpenFreeMap instead of Mapbox GL | No token in the browser, no billing, unlimited tile use per OpenFreeMap. |
| 2026-11-05 | Open-Meteo with `wind_speed_unit=mph`, `precipitation_unit=inch`, unit validation + fallback conversion | Verified `hourly_units` output; belt-and-braces against unit drift. |
| 2026-11-05 | Oliver approved: personal Vercel for both apps, Valhalla default, bootstrap push to main, PR #1 start; deadline still unconfirmed | Review gate decisions D1 to D4. |
| 2026-11-05 | Vercel Django preset: framework must be set to `django` on the project, dependencies must be listed in `pyproject.toml` `[project].dependencies` (a lone `requirements.txt` is ignored), Python from `.python-version` (3.14 works) | Found during the PR #1 hosting smoke test; first deploy was treated as static files and the `.vercel.app` name `stormroute-api` was already taken by someone else (our domain is `stormroute-api-navy.vercel.app`). |
| 2026-11-05 | Early production deployment of the health-only backend | First CLI deploy of a new project went to production automatically; it carries no provider calls, so the FOSSGIS notification condition (D3) is not yet triggered. |
| 2026-11-05 | Nearest-hour forecast selection | Simple, documented, testable; interpolation adds little at hourly resolution. |
| 2026-11-05 | Nearest-checkpoint (midpoint split) mileage attribution | Unbiased, sums exactly to total, handles the final partial segment. |
| 2026-11-05 | Heatmap as GeoJSON cell grid with per-hour properties and paint-expression switching | Zero network and zero data rebuild per slider move. |
| 2026-11-05 | Demo (fixture) mode is a recorded real Valhalla response plus scripted weather, labeled in `provenance` and a `DEMO_MODE` warning | Real weather is usually calm, which cannot show Severe, No Travel or the load rules on demand. A labeled, repeatable scenario serves the demo and the e2e tests and is never presented as live. |
| 2026-11-05 | Response geometry simplified to about 30 m; distances and checkpoints use the full geometry | About 5,500 shape points per route become about 400 with no visible change on the map. |
| 2026-11-05 | `distance_miles` is the haversine length; the provider total is `provider_distance_miles` | Risk mileage must add up to the length the checkpoints were placed on. |
| 2026-11-05 | Heatmap cell size chosen against the cells kept near the routes, minimum 5 miles | Spends the 144-cell budget on the corridor: 23-mile cells for Denver to Kansas City instead of 28. |
| 2026-11-05 | Forecast window requested as `start_date`/`end_date` padded one day and clamped to today + 15 | With `timezone=auto` the dates are local days; the API rejects later dates (verified). |
| 2026-11-05 | Trip-size guard: at most 450 checkpoint forecasts per analysis (`TRIP_TOO_LARGE`) | An application performance and fair-use safeguard: bounds response size and analysis time and keeps one analysis a modest load on the free weather service. Open-Meteo's own call accounting is more nuanced than one call per place. |
| 2026-11-05 | Separate 504 codes per provider and per-client throttles (analyze 20/min, geocode 120/min) | Clearer client handling and protection for the public providers. |
| 2026-11-05 | Explanation adds one sentence for a third eligible route | Never implies the winner is the fastest when a faster route lost on weather. |
| 2026-11-05 | `tzdata` added as a dependency | DST-correct local UTC offsets at each ETA whatever zone database the host has. |
| 2026-11-05 | Measurements are classified at provider precision (normalized to 6 decimals), replacing the 3-decimal rounding; display rounding is separate and band-aware | PR #2 review: 3-decimal rounding turned 1.000394 in/h (25.41 mm) into 1.000 and Severe instead of No Travel, and could round 54.99997 mph up to 55. |
| 2026-11-05 | Oliver approved the scripted demo weather, the 450-forecast guard and the contract additions | PR #2 review. Follow-ups: PR #3 must show a prominent, persistent "simulated weather" label in demo mode; before production (PR #5) add Valhalla's identifying `X-Client-Id` header and arrange the provider notification with Oliver's approval. |
| 2026-11-05 | Typeface: Barlow with Barlow Condensed for names and numbers, loaded from Google Fonts | Barlow descends from highway signage lettering, which suits a driver's tool; system fonts are the fallback. |
| 2026-11-05 | Risk ribbon on each route card | Shows where along the route the risk is, in proportion to the attributed miles, and makes three routes comparable at a glance without the map. |
| 2026-11-05 | Checkpoint details in a panel, not a map popup; selection pushed to the map with `setData` | One place for details on every screen size and for keyboard users; three small features make `setData` as cheap as feature state. |
| 2026-11-05 | The analysis runs on "Compare routes", not on every field change | Each analysis calls the public routing and weather services, so runs are explicit. |
| 2026-11-05 | The risk ribbon is one tab stop with arrow-key movement (roving focus) | PR #3 review: checkpoints must be reachable without a pointer; a route can have 60 checkpoints, so one tab stop per route keeps the page navigable. |
| 2026-11-05 | Results are cleared when a new comparison starts, and each result states its trip | PR #3 review: a recommendation must never be shown beside a form or a failed request that describes a different trip. |
| 2026-11-05 | The slider's hour lives in a small store outside React; the map subscribes to it | A slider move swaps paint expressions only: no React render of the page, no source rebuild, no request. |
| 2026-11-05 | `X-Client-Id` header on Valhalla requests; a notification draft is ready; no public deployment before Oliver decides D3 | The Valhalla documentation asks end-user apps on the FOSSGIS server to identify themselves and to tell the maintainers. |
| 2026-11-05 | Oliver approved the production deployment on his personal Vercel Hobby account, on condition that the Valhalla usage notice is posted first (edited: non-commercial assessment and portfolio demo, limits are per server instance, requests are user-initiated with no background polling) and that the README's AI disclosure is made precise | PR #5 review. If the maintainers object, live routing is switched off until another source is configured. StormRoute stays a low-traffic personal demo with no advertising, subscriptions or production trucking use, in line with Open-Meteo's non-commercial terms. |
| 2026-11-05 | Production deployed after the usage notice was posted (https://github.com/valhalla/valhalla/discussions/6465); frontend first to learn its domain, then the backend with that origin in CORS and in `X-Client-Id` | The approved order. The frontend alone sends no routing request, so nothing reached Valhalla before the notice. |
| 2026-11-05 | A deployment verification script instead of manual curl checks | The same checks can be rerun after every deployment and pasted into the verification record. |
| 2026-11-05 | The CI workflow is kept in `docs/ci/` rather than `.github/workflows/` | The project's access token has no `workflow` scope, so a push containing a workflow file would be rejected. |
| 2026-11-05 | Slider offsets are measured from the real departure time, and the ticks are clock times | PR #4 review: the forecast hours start at the top of the departure hour, so "At departure" was wrong for any departure with minutes. |
| 2026-11-05 | Calm heatmap cells are drawn faint (opacity 0.14 against 0.5) | A corridor of solid green hid the map and the routes; the weather that matters now stands out. |
| 2026-11-05 | Truck position marker included | It ties the corridor forecast at the chosen hour to where the truck would be at that hour. |
| 2026-11-05 | e2e tests are hermetic: recorded real backend responses, blank map style, fonts blocked | Deterministic and polite to the public providers; live behavior is covered by the backend live smoke test and the manual browser checks. |
| 2026-11-05 | MapLibre is loaded lazily and its worker URL is set explicitly | Keeps the form usable before 1 MB of map code arrives; MapLibre 6 ships its worker as a separate module that the bundler must emit. |

---

## 18. Work log (active time only; review waiting time excluded)

| Date (Asia/Manila) | Phase | Start | End | Active | Notes |
|---|---|---|---|---:|---|
| 2026-11-05 | PR #0 preflight + spec | 08:50 | 09:17 | 0.5 h | env checks, gh identity, Valhalla/OSRM/Open-Meteo probes, FOSSGIS terms, Vercel limits, spec.md, decisions, bootstrap push |
| 2026-11-05 | PR #1 foundation + risk engine | 09:17 | 09:35 | 0.3 h | Django/DRF scaffold, TDD risk classifier (60 tests), Vite/React scaffold (3 tests), Vercel smoke deploy + debugging, docs, PR |
| 2026-11-05 | PR #1 Codex round 1 fix | 09:31 | 09:38 | 0.1 h | JSON handler404/handler500 + tests, redeploy |
| 2026-11-05 | PR #1 Codex round 2 fix | 09:39 | 09:47 | 0.1 h | conclusive No Travel precedence over missing data, `missing` field, 8 tests, spec section 7 |
| 2026-11-05 | Session handoff onboarding | 09:56 | 10:01 | 0.1 h | new session: repo, PR and identity checks, full test rerun, deployed health recheck |
| 2026-11-05 | PR #1 merge + PR #2 analysis backend | 10:05 | 10:41 | 0.6 h | squash merge, provider probes, TDD routing/weather/risk/heatmap/API (291 new tests), live smoke test, docs, PR |
| 2026-11-05 | PR #2 review round 1 fix | 10:50 | 10:52 | 0.1 h | threshold precision: provider-precision classification, band-aware display, 22 tests, spec section 7 |
| 2026-11-05 | PR #2 merge + PR #3 dashboard and map | 10:52 | 11:12 | 0.4 h | squash merge, TDD frontend (84 new tests), MapLibre map, browser verification at desktop and 375 px, docs, PR |
| 2026-11-05 | PR #3 Codex round 1 fixes | 11:24 | 11:26 | 0.1 h | keyboard access to checkpoints (roving focus), stale results cleared, trip summary, 8 tests |
| 2026-11-05 | PR #3 Codex round 2 fix | 11:43 | 11:46 | 0.1 h | validation messages without a form field shown in the alert, 3 tests, browser check with demo mode disabled |
| 2026-11-05 | PR #3 merge + PR #4 heatmap and slider | 11:49 | 11:59 | 0.2 h | squash merge, corridor heatmap layer, forecast slider with external store, truck marker, layer switches, Playwright suite (22 runs), browser checks, docs, PR |
| 2026-11-05 | PR #4 Codex round 1 fix | 12:13 | 12:14 | 0.1 h | slider offsets measured from the real departure, clock-time ticks, 10 tests, browser check at 8:45 AM |
| 2026-11-05 | PR #4 merge + PR #5 preparation | 12:25 | 12:30 | 0.2 h | squash merge, X-Client-Id, Vercel config, verification script and local dress rehearsal, README, deployment runbook, verification record, Loom script, CI workflow file |
| 2026-11-05 | PR #5 approved changes | 12:42 | 12:43 | 0.1 h | README AI disclosure, edited Valhalla notice, Vercel account and plan checks; the notice could not be posted from the session, so the deployment is on hold |
| 2026-11-05 | PR #5 production deployment and verification | 13:28 | 13:34 | 0.3 h | notice verified, frontend and backend deployed on the personal Hobby account, verification script (12 checks), browser checks (17), runtime logs, documents |

Cumulative active time: 3.3 h of 16.0 h (12.7 h remain).

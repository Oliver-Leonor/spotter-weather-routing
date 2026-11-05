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
├── frontend/                 React 18 + TypeScript + Vite + Tailwind + TanStack Query + MapLibre GL
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
│   ├── routing/              provider client (Valhalla), geometry decoding, sampling, ETA profile
│   ├── weather/              Open-Meteo client, unit normalization, batching, cache, fixtures
│   ├── risk/                 classification, segment attribution, aggregation, recommendation
│   ├── analysis/             orchestration service + DRF views/serializers (health, geocode, analyze)
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
- Coverage: up to 16 forecast days; the backend requests only the window it needs.
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
      "distance_miles": 604.7,
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
          "risk": {"level": "low", "value": 0, "drivers": [], "wind_level": "low", "rain_level": "low", "snow_level": "low", "load_rule_applied": null}
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
    "cell_size_miles": 15,
    "cells": [{"lat": 39.5, "lon": -104.2, "risk": [0, 0, 1, null, ...], "wind": [...], "rain": [...], "snow": [...]}]
  }
}
```

`recommendation.route_id` is `null` when no route qualifies; `explanation` then starts with
"No safe route is currently recommended." and lists the blocking conditions per route.

Error responses: `400` validation errors (DRF format), `502` upstream provider failure
(`{"error": {"code": "ROUTING_UNAVAILABLE" | "WEATHER_UNAVAILABLE", "message": "...", "provider": "..."}}`),
`504` upstream timeout, `422` when the provider returns no route (`NO_ROUTE`).

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

Missing data: if any of wind, rain or snow is missing for the forecast hour, or the ETA falls outside
the fetched forecast coverage, the checkpoint risk is `unknown` (`null`). Unknown never becomes Low.

Floating point: values are compared as Python floats after rounding provider values to 3 decimals;
tests cover 24.99, 25, 34.99, 35, 44.99, 45, 54.99, 55 mph; 30000 vs 30001 lb; 40000 vs 40001 lb;
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
- Coverage: the backend requests hourly data from `floor(departure) - 1 h` to `ceil(arrival) + 1 h`
  for checkpoints (bounded by Open-Meteo's 16-day horizon) and never extrapolates: a checkpoint whose
  ETA is more than 30 minutes outside the returned series is `unknown`.
- Timezones: input offset is honored and converted to UTC; all arithmetic is in UTC; each checkpoint
  carries the IANA timezone from Open-Meteo for local display (DST handled by the zone database in
  the browser via `Intl.DateTimeFormat`). Backend tests cover a DST transition (for example
  2026-11-01 in `America/Denver`) and a non-UTC input offset.
- Batching and limits: points are deduplicated on 3-decimal coordinates, requested in batches of up to
  50 locations per Open-Meteo call, at most 4 concurrent weather calls, with a 10-minute in-process
  TTL cache keyed by (rounded lat, lon, window, variables). Valhalla calls are sequential (one
  connection) with a 25 s timeout and one retry on connection errors only.

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
- Interactions: card click → `selected` property updated via `setFeatureState`; checkpoint click →
  popup/side detail with measurements, forecast time and ETA; `fitBounds` on new results only.
- Risk colors (consistent across map, cards and legend): Low `#22c55e`, Moderate `#eab308`,
  High `#f97316`, Severe `#dc2626`, No Travel `#7f1d1d` with hatch, Unknown `#94a3b8`.

### 10.2 Heatmap

- Grid: the union bounding box of all routes, padded by 10 % (at least 20 miles), covered by a grid
  whose cell size is chosen so the grid has at most 144 cells (12 × 12 target, aspect-aware). Each
  cell center is a weather sample point. Cells farther than 60 miles from every route are dropped so
  the overlay reads as a corridor.
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
- Backend: Vercel Hobby too, second project `stormroute-api`, Python runtime 3.12 (3.13/3.14 also
  available), Django served as a WSGI app by Vercel Functions, 300 s max duration, no billing
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

Decision required from Oliver (section 15): confirm backend on the personal Vercel account, or name
another host.

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
| 1 | Project foundation and risk engine | Ready for Codex Review (round 2) | 2.0 h | 0.4 h |
| 2 | Routing, weather, recommendation backend | Not Started | 4.0 h | |
| 3 | React dashboard and interactive map | Not Started | 3.5 h | |
| 4 | Weather heatmap and forecast slider | Not Started | 2.5 h | |
| 5 | Production deployment and submission prep | Not Started | 2.5 h | |
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

**Status: Ready for Codex Review** (2026-11-05). PR: https://github.com/Oliver-Leonor/spotter-weather-routing/pull/1
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

Test results (2026-11-05): backend `pytest` 62 passed (58 risk-table/boundary/load/missing-data
cases + 4 health/error-envelope API tests), `ruff check` and `ruff format --check` clean; frontend `vitest` 3 passed,
`tsc -b` clean, `oxlint` clean, `prettier --check` clean, `vite build` OK.

Codex review round 1 (2026-11-05): finding accepted. Unresolved paths were answered by Django's
HTML 404 (URL resolution fails before any DRF view, so the DRF exception handler never runs).
Fix: `analysis/errors.py` JSON `handler404`/`handler500` registered in `config/urls.py`;
`test_unknown_api_route_is_404_json` now asserts content type and body, plus tests for non-API
paths and the 500 handler. Backend suite: 62 passed. Production backend redeployed and re-verified.

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

### PR #3: React dashboard and interactive map

Branch `feat/pr3-dashboard-map`.
Scope: trip planner form (autocomplete, datetime, load weight, interval), TanStack Query wiring,
route comparison cards with recommended badge and No Travel warnings, MapLibre map with routes,
checkpoints, selection, popups/detail panel, fit bounds, loading/empty/error states, responsive
layout (375 px), attribution footer, demo-mode label. Vitest component tests.
Acceptance: full analysis through the UI against the local backend; route selection and checkpoint
detail work; mobile layout verified with screenshots.

### PR #4: Weather heatmap and forecast slider

Branch `feat/pr4-heatmap-slider`.
Scope: heatmap source/layer, slider (0 to 48 h) with exact timestamp, paint-expression updates with
rAF throttling, layer toggles, legend, optional truck-position marker, Playwright e2e (desktop and
mobile), accessibility pass (labels, focus, keyboard slider).
Acceptance: slider changes the visualization with no network calls (verified in Playwright by
counting requests); smooth interaction; e2e suite green at both widths.

### PR #5: Production deployment and submission preparation

Branch `feat/pr5-deploy-docs`.
Scope: production settings, Vercel projects (frontend + backend), env configuration, production smoke
verification (`docs/VERIFICATION.md`), README (all 12 sections of the brief), screenshots,
`docs/LOOM_SCRIPT.md`, final `spec.md` reconciliation, AI-assistance disclosure.
Acceptance: hosted app verified end to end against the production backend; all checklist items in
section 16 checked or explicitly reported.

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

- [ ] React frontend implemented
- [ ] Django backend implemented (scaffold + risk engine + health in PR #1)
- [ ] Origin and destination work
- [ ] Departure date and time work
- [ ] Load weight works
- [ ] Three distinct routing API routes verified for a demonstration trip (preflight: yes, Valhalla,
      5 corridors; to be re-verified through the app)
- [ ] 10/25/50-mile checkpoint sampling works
- [ ] Checkpoint ETAs are calculated
- [ ] Weather is retrieved for checkpoint arrival times
- [x] All Spotter risk rules are correctly implemented (PR #1, 58 boundary tests; route-level wiring in PR #2)
- [x] Load-dependent rules work (PR #1 classifier; end-to-end in PR #2)
- [ ] No Travel rules work
- [ ] Route recommendations follow the required priority order
- [ ] All routes are displayed on the map
- [ ] Checkpoint details work
- [ ] Weather heatmap works
- [ ] 0 to 48 hour forecast slider works
- [ ] Application is responsive
- [ ] Automated tests pass
- [ ] Live provider integration verified
- [ ] Production frontend verified
- [ ] Production backend verified
- [ ] GitHub repository pushed under Oliver-Leonor
- [ ] README completed
- [ ] Loom recording script prepared
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

---

## 18. Work log (active time only; review waiting time excluded)

| Date (Asia/Manila) | Phase | Start | End | Active | Notes |
|---|---|---|---|---:|---|
| 2026-11-05 | PR #0 preflight + spec | 08:50 | 09:17 | 0.5 h | env checks, gh identity, Valhalla/OSRM/Open-Meteo probes, FOSSGIS terms, Vercel limits, spec.md, decisions, bootstrap push |
| 2026-11-05 | PR #1 foundation + risk engine | 09:17 | 09:35 | 0.3 h | Django/DRF scaffold, TDD risk classifier (60 tests), Vite/React scaffold (3 tests), Vercel smoke deploy + debugging, docs, PR |
| 2026-11-05 | PR #1 Codex round 1 fix | 09:40 | 09:48 | 0.1 h | JSON handler404/handler500 + tests, redeploy |

Cumulative active time: 0.9 h of 16.0 h (reforecast after PR #1 round 1: 15.1 h remain; PR #2 to #5 budgets unchanged, reserve raised to 1.0 h).

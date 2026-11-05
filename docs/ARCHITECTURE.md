# Architecture

StormRoute is a stateless React + Django application. The backend owns every business rule
(risk classification, mileage attribution, recommendation) and every provider call; the frontend
renders the typed analysis response and drives the map.

```text
Browser (React 19, Vite, TanStack Query, MapLibre GL)
   │  POST /api/routes/analyze/   GET /api/geocode/   GET /api/health/
   ▼
Django 6 + DRF (backend/)
   ├── analysis/   DRF views, request validation, orchestration service, corridor heatmap
   ├── routing/    Valhalla client, polyline decoding, checkpoint sampling, ETA profile
   ├── weather/    Open-Meteo forecast client, unit validation, geocoding, demo scenario
   ├── risk/       pure classification, aggregation and recommendation functions
   └── common/     error types, TTL cache, outbound HTTP helper
          │
          ├── Valhalla public routing server (FOSSGIS)   https://valhalla1.openstreetmap.de
          └── Open-Meteo forecast + geocoding            https://api.open-meteo.com
```

Dependencies point one way: `analysis` uses `routing`, `weather` and `risk`; those use `common`.
`risk` has no I/O at all.

## Analysis request flow

`POST /api/routes/analyze/` is handled by `analysis/service.py`:

1. Validate the request (`analysis/serializers.py`).
2. Ask the routing provider for the primary route and two alternates
   (`routing/providers/valhalla.py`).
3. Drop near-identical routes and keep at most three (`routing/geometry.are_near_identical`).
4. Place checkpoints at the selected interval and attribute mileage (`routing/sampling.py`).
5. Compute each checkpoint's ETA from the per-maneuver time profile (`routing/eta.py`).
6. Fetch hourly forecasts for every checkpoint in batched calls (`weather/open_meteo.py`).
7. Pick the forecast hour nearest each ETA and classify it (`weather/models.py`,
   `risk/classification.py`).
8. Summarize each route: miles per level, average risk, status (`risk/aggregation.py`).
9. Recommend a route and explain why (`risk/recommendation.py`).
10. Build the corridor heatmap grid and its 49 hourly values (`analysis/heatmap.py`).

Steps 4, 5, 7, 8 and 9 are pure functions and are tested without any network.

## Backend

- `config/settings/{base,dev,test,prod}.py`: environment-driven settings. No database, no auth,
  no sessions.
- `analysis/exceptions.py` renders the uniform error envelope `{"error": {"code", "message", ...}}`
  for DRF errors and for the application errors in `common/errors.py`. `analysis/errors.py`
  (`handler404`/`handler500`) covers unresolved paths and unhandled exceptions, which never reach
  DRF.
- `routing/providers/base.py` defines the provider contract (`RouteProvider`, `ProviderRoute`).
  `valhalla.py` is the live client. `recorded.py` replays a recorded real response for the demo
  mode through the same parser.
- `weather/open_meteo.py` requests mph and inches, verifies the reported units on every response,
  deduplicates places on three decimals, batches 50 places per call with at most 4 calls in flight
  and caches each place for 10 minutes. `weather/scenario.py` is the scripted demo weather.
- `risk/levels.py`, `risk/classification.py`: Spotter's rules. Missing values yield `unknown`,
  never Low. See `spec.md` section 7.
- `common/http.py`: one shared `httpx` client and the mapping of transport failures to 502 and 504.
- Provider calls are limited per client by DRF throttles (`analysis/views.py`).

### Error codes

| Status | Code | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Invalid request; `details` names each field |
| 422 | `NO_ROUTE` | The router found no drivable route |
| 422 | `TRIP_TOO_LARGE` | More than 450 checkpoint forecasts needed |
| 429 | `THROTTLED` | Per-client rate limit reached |
| 502 | `ROUTING_UNAVAILABLE`, `WEATHER_UNAVAILABLE`, `GEOCODING_UNAVAILABLE` | Provider failure |
| 504 | `ROUTING_TIMEOUT`, `WEATHER_TIMEOUT`, `GEOCODING_TIMEOUT` | Provider timeout |

## Frontend

- `src/types/api.ts` mirrors the backend contract (spec section 6).
- `src/lib/api.ts` is the only place that calls the backend; failures become an
  `ApiRequestError` carrying the error envelope. `src/lib/format.ts` formats distances, durations,
  local times and measurements (a measurement keeps enough decimals to agree with its risk band).
  `src/lib/risk.ts` holds the shared risk colors, labels and thresholds.
- `features/trip-planner`: the trip form and the place search combobox.
- `features/route-comparison`: recommendation banner, route cards with the risk ribbon, and the
  checkpoint detail panel.
- `features/route-map`: `mapData.ts` builds the GeoJSON (pure, tested); `RouteMap.tsx` owns the
  MapLibre instance, which is created once and updated with `setData` and `fitBounds`. It is
  loaded lazily so the form is usable before the map code arrives.
- `App.tsx` holds the three pieces of state that everything else derives from: the last analysis,
  the selected route and the selected checkpoint. The analysis request is a TanStack Query
  mutation; place search is a debounced query.
- `features/heatmap` (corridor layer and forecast slider) arrives in PR #4.

## Hosting (verified in PR #1)

- Backend: Vercel Python runtime (Django preset) on the personal Hobby account, project
  `stormroute-api`, public domain `https://stormroute-api-navy.vercel.app`. The Django preset reads
  `manage.py` to discover `DJANGO_SETTINGS_MODULE` (set in the environment to
  `config.settings.prod`) and installs dependencies from `pyproject.toml` `[project].dependencies`
  (`requirements.txt` alone is ignored when a `pyproject.toml` is present). Python version comes
  from `.python-version` (3.14). Framework preset must be `django` in the project settings.
- The deployed backend still serves only the health endpoint from PR #1. The analysis endpoints
  are deployed in PR #5, after the routing provider's notification request has been handled.
- Frontend: Vercel static build (PR #5).

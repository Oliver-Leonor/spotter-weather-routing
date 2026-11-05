# Architecture

StormRoute is a stateless React + Django application. The backend owns every business rule
(risk classification, mileage attribution, recommendation) and every provider call; the frontend
renders the typed analysis response and drives the map.

```text
Browser (React 19, Vite, TanStack Query, MapLibre GL)
   │  POST /api/routes/analyze/   GET /api/geocode/   GET /api/health/
   ▼
Django 6 + DRF (backend/)
   ├── analysis/   DRF views, serializers, error envelope, orchestration service
   ├── routing/    provider adapter (Valhalla), polyline decoding, checkpoint sampling, ETA profile
   ├── weather/    Open-Meteo client, unit validation, batching, caching, fixtures
   └── risk/       pure classification, aggregation and recommendation functions
          │
          ├── Valhalla public routing server (FOSSGIS)   https://valhalla1.openstreetmap.de
          └── Open-Meteo forecast + geocoding            https://api.open-meteo.com
```

## Backend

- `config/settings/{base,dev,test,prod}.py`: environment-driven settings. No database, no auth,
  no sessions. DRF renders JSON only; a uniform error envelope
  `{"error": {"code", "message", ...}}` is produced by `analysis/exceptions.py` for DRF
  exceptions and by `analysis/errors.py` (`handler404`/`handler500` in `config/urls.py`) for
  unresolved paths and unhandled exceptions, which never reach DRF.
- `risk/levels.py`: `RiskLevel` IntEnum in Spotter's severity order (Low 0 to No Travel 4).
- `risk/classification.py`: pure functions `classify_wind`, `classify_rain`, `classify_snow`,
  `apply_load_rules` and `classify_checkpoint`. Missing values yield `unknown`, never Low.
  Boundary convention: half-open bands `[X, Y)`, shared boundaries go to the more severe class,
  "above" thresholds are strict. See `spec.md` section 7.
- `analysis/views.py`: `/api/health/` (PR #1). Analysis and geocode endpoints arrive in PR #2.

## Frontend

- `src/types/api.ts` mirrors the backend contract (spec section 6).
- `src/lib/risk.ts` holds the shared risk colors, labels and numeric values.
- Feature folders (`features/trip-planner`, `route-map`, `route-comparison`, `heatmap`) arrive in
  PR #3 and PR #4.

## Hosting (verified in PR #1)

- Backend: Vercel Python runtime (Django preset) on the personal Hobby account, project
  `stormroute-api`, public domain `https://stormroute-api-navy.vercel.app`. The Django preset reads
  `manage.py` to discover `DJANGO_SETTINGS_MODULE` (set in the environment to
  `config.settings.prod`) and installs dependencies from `pyproject.toml` `[project].dependencies`
  (`requirements.txt` alone is ignored when a `pyproject.toml` is present). Python version comes
  from `.python-version` (3.14). Framework preset must be `django` in the project settings.
- Frontend: Vercel static build (PR #5).

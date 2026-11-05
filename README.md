# StormRoute | Weather-Aware Trip Planning

Spotter full-stack take-home: a React + Django application that compares real road routes against
hourly weather forecasts at each checkpoint's estimated arrival time, applies Spotter's risk rules
and load-dependent adjustments, and recommends the safer route.

Work in progress. The backend analysis API is complete; the dashboard and map are next. The project
specification, decisions and progress live in [`spec.md`](./spec.md), the architecture overview is
in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md), and every modelling assumption is listed in
[`docs/ASSUMPTIONS.md`](./docs/ASSUMPTIONS.md).

## Quick start

```bash
# Backend (Python 3.12+)
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py runserver 8000          # GET http://localhost:8000/api/health/
pytest                                   # full suite, no network access
pytest -m live -s                        # optional: one real Valhalla + Open-Meteo run

# Frontend (Node 24 via nvm)
cd frontend
nvm use && npm install
npm run dev                              # http://localhost:5173
npm test && npm run typecheck && npm run lint
```

Copy `.env.example` to `.env` at the repository root for backend settings and to `frontend/.env`
for the Vite variables. No API keys are required: routing uses the public Valhalla server
(OpenStreetMap data), weather uses Open-Meteo, and map tiles come from OpenFreeMap.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health/` | Service status and provider names |
| `GET /api/geocode/?q=Denver&limit=5` | City and town search for the trip form |
| `POST /api/routes/analyze/` | Routes, checkpoints, weather risk, recommendation and heatmap |

```bash
curl -s -X POST http://localhost:8000/api/routes/analyze/ \
  -H 'Content-Type: application/json' \
  -d '{
        "origin":      {"lat": 39.7392, "lon": -104.9903, "label": "Denver, Colorado, US"},
        "destination": {"lat": 39.0997, "lon": -94.5786,  "label": "Kansas City, Missouri, US"},
        "departure_time": "2026-11-06T08:00:00-07:00",
        "load_weight_lb": 42000,
        "checkpoint_interval_miles": 25
      }'
```

`departure_time` must carry a UTC offset and be between 1 hour ago and 14 days ahead. The full
request and response contract is in `spec.md` section 6.

### Demo mode

Real weather is often calm. Adding `"mode": "fixture"` to the request serves a recorded real
Denver to Kansas City routing response with **scripted weather that is not a forecast**, so the
risk rules, load rules and recommendation can be shown on demand. Demo responses make no provider
calls and are always labeled (`provenance.mode`, a `DEMO_MODE` warning).

## Limitations

- Routes are standard driving routes. Truck restrictions (bridge weights, low clearances, hazmat)
  are not applied, and load weight is cargo weight used only for the weather rules.
- Arrival times assume continuous driving. Rest breaks and live traffic are not modelled.
- The public routing and weather services have no availability guarantee.

Routing data © OpenStreetMap contributors, served by FOSSGIS e.V. Weather data by Open-Meteo.com
(CC BY 4.0).

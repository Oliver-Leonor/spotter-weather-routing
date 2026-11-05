# StormRoute | Weather-Aware Trip Planning

Spotter full-stack take-home: a React + Django application that compares real road routes against
hourly weather forecasts at each checkpoint's estimated arrival time, applies Spotter's risk rules
and load-dependent adjustments, and recommends the safer route.

Work in progress. The project specification, decisions and progress live in [`spec.md`](./spec.md);
the architecture overview is in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

## Quick start

```bash
# Backend (Python 3.12+)
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py runserver 8000          # GET http://localhost:8000/api/health/
pytest                                   # risk engine + API tests

# Frontend (Node 24 via nvm)
cd frontend
nvm use && npm install
npm run dev                              # http://localhost:5173
npm test && npm run typecheck && npm run lint
```

Copy `.env.example` to `.env` at the repository root for backend settings and to `frontend/.env`
for the Vite variables. No API keys are required: routing uses the public Valhalla server
(OpenStreetMap data), weather uses Open-Meteo, and map tiles come from OpenFreeMap.

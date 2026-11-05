# Verification record

What was checked, when, and with what result. Times are UTC unless stated.

## Production

**Not verified yet.** The analysis endpoints and the frontend have not been deployed to
production. Deployment is waiting for Oliver's decision on notifying the Valhalla maintainers
(see [`DEPLOYMENT.md`](./DEPLOYMENT.md)). The production backend currently serves only the health
endpoint from PR #1.

When the deployment is done, run `scripts/verify_deployment.py` with `--live` and paste its table
here, then add the browser checks listed in `DEPLOYMENT.md`.

## Dress rehearsal on a local machine (2026-11-05)

The backend ran with the production settings module (`config.settings.prod`, debug off, CORS
limited to one origin). The frontend was a production build (`vite build`) served by
`vite preview` and pointed at that backend. This is the same code path as production, without TLS.

`python3 scripts/verify_deployment.py --api http://127.0.0.1:8000 --web http://localhost:4173 --live`

Checked 2026-11-05 04:27 UTC.

| Check | Result | Detail |
|---|---|---|
| Backend health | Pass | 200, version 0.1.0 |
| HTTP redirects to HTTPS | Skipped | no TLS on localhost (verified on the real domain in PR #1: 308) |
| Unknown route is a JSON 404 | Pass | 404 NOT_FOUND, application/json |
| Debug pages are off | Pass | no debug page content |
| CORS allows the frontend origin | Pass | Access-Control-Allow-Origin: http://localhost:4173 |
| CORS refuses another origin | Pass | no Access-Control-Allow-Origin header |
| Validation error envelope | Pass | 400 VALIDATION_ERROR |
| Place search | Pass | 200, first result: Denver, Colorado, US |
| Demo analysis (labeled, no provider calls) | Pass | 200, three routes |
| Live analysis (real routing and weather) | Pass | 200, 3 routes 604.1 / 613.5 / 634.8 mi, 79 of 79 checkpoints with a forecast, 140 heatmap cells |
| Frontend page loads | Pass | 200 |
| Frontend bundle points at the API and holds no secrets | Pass | 287 KB main bundle, API base URL found, no secret pattern |

## Automated tests (2026-11-05)

| Suite | Result |
|---|---|
| Backend `pytest` | 384 passed, 1 deselected (the live test) |
| Backend `ruff check`, `ruff format --check` | Clean |
| Frontend `vitest` | 136 passed |
| Frontend `tsc -b`, `oxlint`, `prettier --check`, `vite build` | Clean |
| Playwright end to end | 22 passed (11 specs at 1280 px and 375 px) |

## Live provider checks (2026-11-05)

| Check | Result |
|---|---|
| Backend live smoke test (`pytest -m live -s`, PR #2) | Denver to Kansas City: three distinct routes (604.1 / 613.5 / 634.8 mi), a real forecast at every checkpoint, ETAs and forecast hours shifted by 6 hours for a departure 6 hours later. First call 4.9 s, repeat 0.09 s from cache. |
| Live trip typed through the UI (PR #3) | Place search, real Valhalla and Open-Meteo, three route cards, no console errors. |
| Forecast slider against the real backend (PR #4) | All 49 positions in 0.77 s with 0 network requests. |

## Browser checks against the local backend (2026-11-05, Chromium)

| Check | Result |
|---|---|
| Demo trip at 1440 x 900 and 375 x 812 | Pass, no console errors, no horizontal overflow at 375 px |
| Click a checkpoint and a route line on the map | Pass |
| Checkpoint details with the keyboard only | Pass |
| Failed comparison (backend stopped) | Pass: error shown, earlier results removed |
| Demo mode disabled on the server | Pass: "Demo mode is not enabled on this server." |
| Departure at 45 past the hour | Pass: slider reads "45 min before departure" at the first hour |

Screenshots are in [`screenshots/`](./screenshots).

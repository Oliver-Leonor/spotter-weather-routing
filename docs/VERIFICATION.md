# Verification record

What was checked, when, and with what result. Times are UTC unless stated.

## Production (2026-11-05)

| | |
|---|---|
| Frontend | https://stormroute-three.vercel.app (Vercel project `stormroute`) |
| Backend | https://stormroute-api-navy.vercel.app (Vercel project `stormroute-api`) |
| Account and plan | `oliverleonor90`, scope `oliverleonor90s-projects`, Hobby |
| Valhalla usage notice | https://github.com/valhalla/valhalla/discussions/6465 (posted before the deployment) |
| Deployed from | branch `feat/pr5-deploy-docs` at `f8956c3` |

### Verification script

`python3 scripts/verify_deployment.py --api https://stormroute-api-navy.vercel.app --web https://stormroute-three.vercel.app --live`

Checked 2026-11-05 05:31 UTC. The live analysis was a single request (one Valhalla call and a few
Open-Meteo calls).

| Check | Result | Detail |
|---|---|---|
| Backend health | Pass | 200, version 0.1.0, HSTS set |
| HTTP redirects to HTTPS | Pass | 308 to https://stormroute-api-navy.vercel.app/api/health/ |
| Unknown route is a JSON 404 | Pass | 404 NOT_FOUND, application/json |
| Debug pages are off | Pass | no debug page content |
| CORS allows the frontend origin | Pass | Access-Control-Allow-Origin: https://stormroute-three.vercel.app |
| CORS refuses another origin | Pass | no Access-Control-Allow-Origin header |
| Validation error envelope | Pass | 400 VALIDATION_ERROR |
| Place search | Pass | 200, first result: Denver, Colorado, US |
| Demo analysis (labeled, no provider calls) | Pass | 200, three routes |
| Live analysis (real routing and weather) | Pass | 200, 3 routes 604.1 / 613.5 / 634.8 mi, 79 of 79 checkpoints with a forecast, 140 heatmap cells |
| Frontend page loads | Pass | 200, X-Content-Type-Options: nosniff |
| Frontend bundle points at the API and holds no secrets | Pass | 287 KB main bundle, API base URL found, no secret pattern |

### Browser checks on the deployed application

Chromium (Playwright), 2026-11-05, against https://stormroute-three.vercel.app. All 17 passed.
Apart from one place search, these use the demo trip, so they add no routing or weather requests.

| Check | Desktop 1440 x 900 | Phone 375 x 812 |
|---|---|---|
| Page is served over HTTPS and the map tiles load | Pass | |
| Place search suggests "Denver, Colorado, US" | Pass | |
| Demo trip shows three route cards | Pass | Pass |
| Demo is labeled "Simulated weather" for as long as it is shown | Pass | Pass |
| 42,000 lb load: Routes A and B are blocked (wind with a load over 30,000 lb), Route C is recommended | Pass | |
| 28,000 lb load: no route is blocked, the recommendation avoids 50.0 miles of severe weather | Pass | |
| Selecting a route card selects the route | Pass | |
| Checkpoint details show wind 50.1 mph, No Travel, and the load rule | Pass | Pass (opens and scrolls into view) |
| Forecast slider across 0 to 48 h makes no network request | Pass (0 requests) | Pass |
| Map layer switches | Pass | |
| No horizontal overflow | | Pass (0 px) |
| No console errors and no failed requests | Pass | Pass |

Screenshots: [`screenshots/production-desktop.png`](./screenshots/production-desktop.png),
[`screenshots/production-mobile.png`](./screenshots/production-mobile.png).

### Runtime logs

The backend's runtime log for the verification window (`vercel logs`, last 20 minutes) has no
error, exception or 5xx line. The only non-200 responses are the ones the checks ask for on
purpose (the 404, the 400 and the redirect).

### Not verified, and why

- The values of the encrypted environment variables cannot be read back from Vercel. They were
  confirmed by behavior (health, CORS).
- The `X-Client-Id` header reaches Valhalla from the server and cannot be observed from outside.
  It is covered by a backend test.
- Clicking a checkpoint or a route line on the map itself was checked against the local backend in
  PR #3, not repeated on production.
- The Loom walkthrough has not been recorded.

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

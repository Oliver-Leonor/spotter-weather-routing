# Deployment

StormRoute deploys as two projects on Vercel's free Hobby plan, on Oliver's personal account
(`oliverleonor90`). No paid resource is used.

| Part | Vercel project | What it is |
|---|---|---|
| Backend | `stormroute-api` (exists) | Django as a Python function. Domain `stormroute-api-navy.vercel.app` |
| Frontend | `stormroute` (to be created) | Static Vite build from `frontend/` |

Current state: the backend project serves only the health endpoint from PR #1. The analysis
endpoints and the frontend have **not** been deployed.

## Before the first public deployment

The app sends routing requests to the public Valhalla server run by FOSSGIS. The
[Valhalla documentation](https://valhalla.github.io/valhalla/) asks apps published to end users to
do two things:

1. Send an identifying `X-Client-Id` header. The backend does this; set `VALHALLA_CLIENT_ID` to
   the frontend's domain.
2. Let the maintainers know through GitHub Discussions.

A notification that can be posted at https://github.com/valhalla/valhalla/discussions:

> **StormRoute: small portfolio app using the FOSSGIS demo server**
>
> Hello, I am publishing a small portfolio project that sends routing requests to
> valhalla1.openstreetmap.de. It is a take-home assessment, not a commercial product, and I expect
> very low traffic.
>
> - App: StormRoute, weather-aware trip planning (https://github.com/Oliver-Leonor/spotter-weather-routing)
> - Requests: `/route` with `auto` costing and two alternates, one request per trip comparison
> - Etiquette: `X-Client-Id` and an identifying `User-Agent` on every request, one request in
>   flight at a time, identical trips cached for 10 minutes, and a per-client rate limit in front
>   of it
>
> Please tell me if this use is not welcome and I will switch to another routing source. Thank you
> for running the service.

This step needs Oliver's decision. It is recorded as D3 in `spec.md`.

## Backend

Environment variables for the **Production** environment of `stormroute-api`:

| Variable | Value |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `DJANGO_SECRET_KEY` | a long random string (already set) |
| `DJANGO_ALLOWED_HOSTS` | `stormroute-api-navy.vercel.app` |
| `CORS_ALLOWED_ORIGINS` | the frontend origin, for example `https://stormroute.vercel.app` |
| `VALHALLA_CLIENT_ID` | the frontend domain, for example `stormroute.vercel.app` |
| `ALLOW_FIXTURE_MODE` | `true` (keeps the labeled demo available) |
| `APP_CONTACT_EMAIL` | optional: a contact address added to the `User-Agent` |

```bash
cd backend
vercel -Q ~/.vercel-personal env ls                       # check what is set
vercel -Q ~/.vercel-personal env add CORS_ALLOWED_ORIGINS production
vercel -Q ~/.vercel-personal env add VALHALLA_CLIENT_ID production
vercel -Q ~/.vercel-personal deploy --prod
```

Notes from the PR #1 hosting test: the project's framework preset must be `django`, dependencies
are read from `pyproject.toml` `[project].dependencies`, and the Python version comes from
`.python-version`.

## Frontend

```bash
cd frontend
vercel -Q ~/.vercel-personal link                         # create or link the project "stormroute"
vercel -Q ~/.vercel-personal env add VITE_API_BASE_URL production   # https://stormroute-api-navy.vercel.app
vercel -Q ~/.vercel-personal deploy --prod
```

`frontend/vercel.json` sets the build command, the output directory, basic security headers and
long-lived caching for the hashed assets. `VITE_API_BASE_URL` is read at build time, so the
frontend must be redeployed if the backend address changes.

Order: deploy the frontend once to learn its domain, set `CORS_ALLOWED_ORIGINS` and
`VALHALLA_CLIENT_ID` on the backend to that domain, then deploy the backend.

## Verify

```bash
python3 scripts/verify_deployment.py \
  --api https://stormroute-api-navy.vercel.app \
  --web https://<frontend-domain> \
  --live
```

The script checks health, the HTTPS redirect, the JSON 404, that debug pages are off, CORS for
the frontend and against another origin, the validation envelope, place search, a demo analysis,
one live analysis, and that the frontend bundle points at the API and contains no secret. It
prints a Markdown table for [`VERIFICATION.md`](./VERIFICATION.md). Without `--live` the only
provider call is one place search.

Then check by hand in a browser, on a desktop and at a 375 px width: the map tiles load, the demo
trip works, a live trip works, a route and a checkpoint can be selected, the forecast slider moves
the corridor, and the console shows no errors.

## Continuous integration

A GitHub Actions workflow is ready in [`ci/github-actions-ci.yml`](./ci/github-actions-ci.yml). It
is not active because the access token used for this project cannot push workflow files. To
enable it, add the file as `.github/workflows/ci.yml` through the GitHub web interface.

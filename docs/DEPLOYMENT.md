# Deployment

StormRoute deploys as two projects on Vercel's free Hobby plan, on Oliver's personal account
(`oliverleonor90`). No paid resource is used.

| Part | Vercel project | What it is |
|---|---|---|
| Backend | `stormroute-api` | Django as a Python function. https://stormroute-api-navy.vercel.app |
| Frontend | `stormroute` | Static Vite build from `frontend/`. https://stormroute-three.vercel.app |

Current state: both were deployed to production on 2026-11-05 and verified (see
[`VERIFICATION.md`](./VERIFICATION.md)). The plan is Hobby and the scope is the personal one,
`oliverleonor90s-projects`. The bare names `stormroute.vercel.app` and `stormroute-api.vercel.app`
belong to other people, which is why the domains carry a suffix.

## Before the first public deployment

The app sends routing requests to the public Valhalla server run by FOSSGIS. The
[Valhalla documentation](https://valhalla.github.io/valhalla/) asks apps published to end users to
do two things:

1. Send an identifying `X-Client-Id` header. The backend does this; set `VALHALLA_CLIENT_ID` to
   the frontend's domain.
2. Let the maintainers know through GitHub Discussions.

Other apps announce themselves in the **General** category of
https://github.com/valhalla/valhalla/discussions with a title of the form "Public demo server
usage notice: <app>". The notice for StormRoute, with the title
"Public demo server usage notice: StormRoute (non-commercial portfolio demo)":

> **StormRoute: non-commercial portfolio demo using the FOSSGIS demo server**
>
> Hello, I am publishing a small web app that sends routing requests to
> valhalla1.openstreetmap.de, and I would like to let you know as the documentation asks.
>
> StormRoute is a non-commercial take-home assessment and portfolio demonstration, not a product.
> It has no advertising, no subscriptions and no production trucking use, and I expect very low
> traffic.
>
> - App: StormRoute, weather-aware trip planning (https://github.com/Oliver-Leonor/spotter-weather-routing)
> - Requests: `/route` with `auto` costing and two alternates. Every request is started by a
>   person pressing a button to compare routes for one trip. There is no background polling and
>   no batch use.
> - Identification: an `X-Client-Id` header and an identifying `User-Agent` on every request.
> - Load limiting: one request in flight at a time, identical trips cached for 10 minutes, and a
>   per-client rate limit in front of the routing call. These work per server instance. The app
>   runs on serverless hosting, so they are not global across instances.
>
> If this use is not welcome, please tell me and I will disable live routing until I have
> configured another routing source. Thank you for running the service.

Oliver posted it on 2026-11-05, before the deployment: https://github.com/valhalla/valhalla/discussions/6465
(D3 in `spec.md`). If the maintainers object, live routing is switched off until another routing
source is configured.

## Backend

Environment variables for the **Production** environment of `stormroute-api`:

| Variable | Value |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `DJANGO_SECRET_KEY` | a long random string (already set) |
| `DJANGO_ALLOWED_HOSTS` | `stormroute-api-navy.vercel.app` (already set) |
| `CORS_ALLOWED_ORIGINS` | `https://stormroute-three.vercel.app` (set on 2026-11-05) |
| `VALHALLA_CLIENT_ID` | `stormroute-three.vercel.app` (set on 2026-11-05) |
| `ALLOW_FIXTURE_MODE` | `true` (set on 2026-11-05; keeps the labeled demo available) |
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
`VALHALLA_CLIENT_ID` on the backend to that domain, then deploy the backend. This is the order
that was used.

Vercel stores these variables encrypted, and `vercel env pull` returns them empty, so their values
cannot be read back. They were confirmed by behavior instead: the health check passes (settings
module, secret and allowed hosts), and the CORS checks allow the frontend origin and refuse
another one.

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

#!/usr/bin/env python3
"""Check a deployed StormRoute backend and frontend end to end.

    python3 scripts/verify_deployment.py --api https://<backend> --web https://<frontend> [--live]

Standard library only. Prints a Markdown table (paste it into docs/VERIFICATION.md) and exits
non-zero if any check fails. Without --live the only provider call is one place search; --live
adds a single real analysis (one Valhalla request and a handful of Open-Meteo requests).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

DENVER = {"lat": 39.7392, "lon": -104.9903, "label": "Denver, Colorado, US"}
KANSAS_CITY = {"lat": 39.0997, "lon": -94.5786, "label": "Kansas City, Missouri, US"}
SECRET_PATTERNS = re.compile(
    r"SECRET_KEY|DJANGO_SECRET|gh[pousr]_[A-Za-z0-9]{20,}|sk_live_|-----BEGIN [A-Z ]*PRIVATE KEY"
)
USER_AGENT = "StormRoute-verify/1.0 (+https://github.com/Oliver-Leonor/spotter-weather-routing)"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(url, *, method="GET", body=None, headers=None, follow=True, timeout=90):
    """Return (status, headers, text) for any status code."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("User-Agent", USER_AGENT)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.headers, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read().decode("utf-8", "replace")


def trip(mode, hours_ahead=2):
    departure = (datetime.now(UTC) + timedelta(hours=hours_ahead)).replace(
        minute=0, second=0, microsecond=0
    )
    return {
        "origin": DENVER,
        "destination": KANSAS_CITY,
        "departure_time": departure.isoformat(),
        "load_weight_lb": 42000,
        "checkpoint_interval_miles": 25,
        "mode": mode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True, help="backend origin, e.g. https://api.example.app")
    parser.add_argument("--web", required=True, help="frontend origin, e.g. https://example.app")
    parser.add_argument("--live", action="store_true", help="also run one real analysis")
    args = parser.parse_args()
    api, web = args.api.rstrip("/"), args.web.rstrip("/")
    is_https = api.startswith("https://")

    results: list[tuple[str, bool | None, str]] = []

    def check(name, run):
        try:
            outcome = run()
        except Exception as error:  # noqa: BLE001 - every failure belongs in the report
            results.append((name, False, f"{type(error).__name__}: {error}"))
            return
        passed, detail = outcome
        results.append((name, passed, detail))

    def health():
        status, headers, text = fetch(f"{api}/api/health/")
        body = json.loads(text)
        hsts = headers.get("Strict-Transport-Security")
        ok = status == 200 and body.get("status") == "ok" and (bool(hsts) or not is_https)
        return ok, f"{status}, version {body.get('version')}, HSTS {'set' if hsts else 'not set'}"

    def https_redirect():
        if not is_https:
            return None, "skipped (backend is not served over HTTPS)"
        status, headers, _ = fetch(
            api.replace("https://", "http://") + "/api/health/", follow=False
        )
        return status in (301, 307, 308), f"{status} to {headers.get('Location')}"

    def not_found():
        status, headers, text = fetch(f"{api}/api/does-not-exist/")
        code = json.loads(text)["error"]["code"]
        return (
            status == 404 and code == "NOT_FOUND",
            f"{status} {code}, {headers.get('Content-Type')}",
        )

    def debug_off():
        _, _, text = fetch(f"{api}/api/does-not-exist/")
        return "Traceback" not in text and "DEBUG = True" not in text, "no debug page content"

    def cors(origin, expect_allowed):
        def run():
            _, headers, _ = fetch(
                f"{api}/api/routes/analyze/",
                method="OPTIONS",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            allowed = headers.get("Access-Control-Allow-Origin")
            return (allowed == origin) == expect_allowed, f"Access-Control-Allow-Origin: {allowed}"

        return run

    def validation():
        status, _, text = fetch(f"{api}/api/routes/analyze/", method="POST", body={})
        code = json.loads(text)["error"]["code"]
        return status == 400 and code == "VALIDATION_ERROR", f"{status} {code}"

    def geocode():
        status, _, text = fetch(f"{api}/api/geocode/?q=Denver&limit=3")
        places = json.loads(text).get("results", [])
        label = places[0]["label"] if places else None
        return status == 200 and bool(places), f"{status}, first result: {label}"

    def demo():
        status, _, text = fetch(f"{api}/api/routes/analyze/", method="POST", body=trip("fixture"))
        body = json.loads(text)
        codes = [warning["code"] for warning in body.get("warnings", [])]
        ok = (
            status == 200
            and body["provenance"]["mode"] == "fixture"
            and "DEMO_MODE" in codes
            and len(body["routes"]) == 3
            and len(body["heatmap"]["hours"]) == 49
        )
        statuses = [route["status"] for route in body.get("routes", [])]
        return ok, f"{status}, routes {statuses}, recommended {body['recommendation']['route_id']}"

    def live():
        status, _, text = fetch(f"{api}/api/routes/analyze/", method="POST", body=trip("live"))
        body = json.loads(text)
        if status != 200:
            return False, f"{status} {body.get('error', {}).get('code')}"
        routes = body["routes"]
        checkpoints = [c for route in routes for c in route["checkpoints"]]
        with_forecast = sum(1 for c in checkpoints if c["weather"] is not None)
        ok = body["provenance"]["mode"] == "live" and len(routes) >= 1 and with_forecast > 0
        miles = [route["distance_miles"] for route in routes]
        return ok, (
            f"{status}, {len(routes)} routes {miles} mi, {with_forecast}/{len(checkpoints)} "
            f"checkpoints with a forecast, {len(body['heatmap']['cells'])} heatmap cells"
        )

    page: dict[str, str] = {}

    def frontend():
        status, headers, text = fetch(f"{web}/")
        page["html"] = text
        nosniff = headers.get("X-Content-Type-Options")
        return status == 200 and 'id="root"' in text, f"{status}, X-Content-Type-Options: {nosniff}"

    def bundle():
        scripts = re.findall(r'src="(/assets/[^"]+\.js)"', page.get("html", ""))
        if not scripts:
            return False, "no script found in the page"
        _, _, text = fetch(f"{web}{scripts[0]}")
        leaked = SECRET_PATTERNS.search(text)
        points_at_api = api in text
        api_url = "found" if points_at_api else "NOT found"
        detail = f"{scripts[0]}, {len(text) // 1024} KB, API base URL {api_url}"
        if leaked:
            detail += f", SECRET PATTERN {leaked.group(0)}"
        return leaked is None and points_at_api, detail

    check("Backend health", health)
    check("HTTP redirects to HTTPS", https_redirect)
    check("Unknown route is a JSON 404", not_found)
    check("Debug pages are off", debug_off)
    check("CORS allows the frontend origin", cors(web, True))
    check("CORS refuses another origin", cors("https://not-the-frontend.example", False))
    check("Validation error envelope", validation)
    check("Place search", geocode)
    check("Demo analysis (labeled, no provider calls)", demo)
    if args.live:
        check("Live analysis (real routing and weather)", live)
    check("Frontend page loads", frontend)
    check("Frontend bundle points at the API and holds no secrets", bundle)

    print(f"Checked {datetime.now(UTC):%Y-%m-%d %H:%M} UTC. Backend: {api}. Frontend: {web}.\n")
    print("| Check | Result | Detail |")
    print("|---|---|---|")
    for name, passed, detail in results:
        mark = "Skipped" if passed is None else "Pass" if passed else "FAIL"
        print(f"| {name} | {mark} | {detail} |")
    return 1 if any(passed is False for _, passed, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())

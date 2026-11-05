# Assumptions and limitations

Every modelling choice the backend makes, in one place. The rules themselves are specified in
[`spec.md`](../spec.md) sections 7 to 10; this file records how they are interpreted and where the
application stops short of reality.

## Routes

- Routes come from the public Valhalla server (FOSSGIS) with `auto` costing. They are **standard
  driving routes**. Truck restrictions (bridge weight limits, low clearances, hazmat rules) are not
  applied. The limitation is repeated in every API response (`provenance.notes`).
- Load weight is **cargo weight**. It is used only for the weather risk rules, never as a gross
  vehicle weight for routing.
- Up to three options are analyzed: the provider's primary route and its two alternates. If the
  provider returns fewer, the response says so (`FEWER_ROUTES`). Routes are never invented.
- Two routes are treated as the same when their lengths agree within 1 % and their positions at 51
  evenly spaced fractions of the way along never differ by more than 0.25 miles. Such routes would
  be sampled at the same places and carry the same weather exposure. The duplicate is removed and
  reported (`DUPLICATE_ROUTES_REMOVED`).
- `distance_miles` is the great-circle (haversine) length of the full route geometry, which is the
  length the risk mileage adds up to. The provider's own total is reported next to it as
  `provider_distance_miles`. On the recorded Denver to Kansas City routes the two agree within 0.2 %.
- The geometry in the response is simplified for display (Douglas-Peucker, about 30 m tolerance).
  Distances, checkpoints and ETAs are always computed on the full geometry.

## Checkpoints and mileage

- Checkpoints sit at every multiple of the selected interval (10, 25 or 50 miles) along the route,
  plus the origin and the destination.
- A checkpoint closer to the destination than 10 % of the interval is dropped in favour of the
  destination, so a route never ends with two samples on top of each other. The final partial
  segment is still counted.
- Every mile belongs to its nearest checkpoint along the route (segments are split at their
  midpoint). The attributed miles always add up to the route length. Risk mileage is the sum of the
  miles owned by checkpoints at each level. It is never "number of checkpoints times interval".

## Arrival times

- The router reports a duration per maneuver. Elapsed time is accumulated maneuver by maneuver and
  interpolated by distance inside a maneuver, then scaled so the last checkpoint arrives exactly at
  the route duration. If the maneuver data is unusable, time is proportional to distance.
- ETAs assume **continuous driving at the router's speeds**. Rest breaks, fuelling, hours-of-service
  limits and live traffic are not modelled. A later departure shifts every ETA by the same amount.

## Weather

- Forecasts come from Open-Meteo (`best_match` model blend), hourly.
- Wind is the sustained 10 m wind speed (`wind_speed_10m`). Gusts are shown but not classified,
  because the rules are written for wind speed.
- Rain rate is `rain + showers` for the hour. Snow rate is `snowfall` for the hour. Both are hourly
  amounts in inches, used directly as inches per hour. Open-Meteo reports them as the sum over the
  preceding hour.
- The forecast hour used for a checkpoint is the **nearest hour to its ETA**. An ETA exactly on the
  half hour uses the earlier hour. There is no interpolation between hours, so the forecast can be
  up to 30 minutes away from the ETA.
- An ETA more than 30 minutes outside the returned forecast (for example beyond the provider's
  16-day horizon) has no forecast. It is never extrapolated.
- The API is asked for mph, inches and Fahrenheit, and the units it actually reports are checked on
  every response. Metric units are converted. An unrecognised unit on wind, rain, showers or
  snowfall rejects the response instead of guessing.
- Risk measurements are rounded to three decimals before classification, so floating-point noise
  cannot move a value across a threshold (0.01 + 0.09 inches is 0.1, not 0.09999999999999999).
- Forecast points are requested at coordinates rounded to three decimals (about 110 m).

## Risk classification

- Bands are half-open: "X to below Y" is `[X, Y)`, and a value on a shared boundary belongs to the
  more severe band. "Above" thresholds are strict.
- Load rules use strict comparisons: more than 30,000 lb and more than 40,000 lb.
- A measurement that is missing is never treated as zero or as Low. If an available measurement
  already proves No Travel, the checkpoint is No Travel. Otherwise a checkpoint with any missing
  measurement is `unknown`.
- A route with a No Travel checkpoint is `blocked`. A route with an unknown checkpoint is
  `unverified`. Neither is ever recommended.

## Recommendation

- Eligible routes are compared in a fixed order with no weighting: fewest Severe miles, then fewest
  High miles, then lowest average risk, then shortest duration.
- Miles are compared at 0.1 and average risk at 0.001. A complete tie falls back to the provider's
  route order.
- Average risk is the miles-weighted mean of the level values (Low 0 to No Travel 4).
- The explanation is generated from the same numbers that are returned in the response.

## Corridor heatmap

- The heatmap is an overview of the weather around the routes. It is **not** used for checkpoint
  risk or for the recommendation.
- It is a grid of at most 144 cells, square in miles, covering the routes' bounding box plus 10 %
  padding (at least 20 miles). Cells whose centre is more than 60 miles from every route are
  dropped. The cell size is the smallest one (at least 5 miles) whose kept cells fit the budget.
- Each cell has 49 hourly values (0 to 48 hours from the departure hour) classified with the same
  rules and the same load weight as the checkpoints.
- If the heatmap forecast fails, the routes and recommendation are still returned and the response
  carries a `HEATMAP_UNAVAILABLE` warning.

## Time

- Departure times must carry a UTC offset. All arithmetic is in UTC.
- Each checkpoint reports the IANA time zone of its location and the UTC offset in force at its
  ETA, so local times are right on both sides of a daylight saving change.

## Request limits

- Departure: no more than 1 hour in the past and no more than 14 days ahead.
- Load weight: 0 to 200,000 lb, whole pounds.
- One analysis may need at most 450 checkpoint forecasts across its routes. A longer trip at a
  short interval is rejected with `TRIP_TOO_LARGE` and a suggestion to use a larger interval. With
  the heatmap grid this keeps a single analysis within Open-Meteo's 600 calls per minute, counting
  each place as one call.

## Provider fair use

- Valhalla (FOSSGIS): identifying `User-Agent`, one request in flight at a time, identical trips
  answered from a 10-minute cache.
- Open-Meteo: batches of 50 places, at most 4 concurrent requests, a 10-minute per-place cache.
- Analyses are rate limited per client (20 per minute by default).
- Caches and rate limits live in process memory. On serverless hosting they apply per warm
  instance.
- Neither public service has an availability guarantee. A provider failure is reported as a 502 or
  504 with a message the driver can act on.

## Demo mode

- `mode: "fixture"` serves a recorded real Valhalla response for Denver to Kansas City together
  with **scripted weather that is not a forecast**. It exists because real weather is often calm,
  which would make the risk rules impossible to demonstrate on demand.
- The scripted weather depends only on place and hour of day (UTC) and repeats every 24 hours, so
  the demo is repeatable and still changes with the departure time and load weight.
- Every demo response is labeled: `provenance.mode` is `fixture`, the weather provider is
  `demo-scenario`, and a `DEMO_MODE` warning is included. It makes no provider calls.

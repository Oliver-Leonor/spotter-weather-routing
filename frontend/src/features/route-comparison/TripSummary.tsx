import { formatLocalTime, formatWeight } from '../../lib/format'
import type { AnalyzeResponse, LatLon } from '../../types/api'

const name = (place: LatLon) => place.label || `${place.lat.toFixed(3)}, ${place.lon.toFixed(3)}`

/**
 * The trip these results were computed for. The form above can be edited at any time, so the
 * results always say which origin, destination, departure and load they belong to.
 */
export function TripSummary({ analysis }: { analysis: AnalyzeResponse }) {
  const { request, routes } = analysis
  const originZone = routes[0]?.checkpoints[0]?.timezone ?? null
  return (
    <section aria-label="Analyzed trip" className="text-sm leading-relaxed text-slate-700">
      <p className="font-medium text-ink">
        {name(request.origin)} to {name(request.destination)}
      </p>
      <p>
        Departs {formatLocalTime(request.departure_time_utc, originZone)},{' '}
        {formatWeight(request.load_weight_lb)} load, weather checked every{' '}
        {request.checkpoint_interval_miles} mi
      </p>
    </section>
  )
}

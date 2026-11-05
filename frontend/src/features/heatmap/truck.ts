import type { RouteAnalysis } from '../../types/api'

export interface TruckPosition {
  lon: number
  lat: number
  status: 'not_departed' | 'driving' | 'arrived'
}

/**
 * Where the truck is expected to be on `route` at `timeMs`, from the checkpoint ETAs. Between two
 * checkpoints the position is interpolated in a straight line by elapsed time, which is close
 * enough to place a marker beside the corridor forecast for that hour.
 */
export function truckPositionAt(route: RouteAnalysis, timeMs: number): TruckPosition {
  const checkpoints = route.checkpoints
  const first = checkpoints[0]
  const last = checkpoints[checkpoints.length - 1]
  if (timeMs <= Date.parse(first.eta)) {
    const status = timeMs < Date.parse(first.eta) ? 'not_departed' : 'driving'
    return { lon: first.lon, lat: first.lat, status }
  }
  if (timeMs >= Date.parse(last.eta)) {
    const status = timeMs > Date.parse(last.eta) ? 'arrived' : 'driving'
    return { lon: last.lon, lat: last.lat, status }
  }
  const next = checkpoints.findIndex((checkpoint) => Date.parse(checkpoint.eta) > timeMs)
  const from = checkpoints[next - 1]
  const to = checkpoints[next]
  const started = Date.parse(from.eta)
  const fraction = (timeMs - started) / (Date.parse(to.eta) - started)
  return {
    lon: from.lon + (to.lon - from.lon) * fraction,
    lat: from.lat + (to.lat - from.lat) * fraction,
    status: 'driving',
  }
}

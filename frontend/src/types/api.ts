/**
 * Backend API contract (mirrors spec.md section 6). All timestamps are ISO-8601 UTC strings.
 * Distances in miles, durations in seconds, wind in mph, precipitation in inches per hour.
 */

export type RiskLevel = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel'
export type RiskLevelOrUnknown = RiskLevel | 'unknown'
export type RouteStatus = 'ok' | 'blocked' | 'unverified'
export type CheckpointKind = 'origin' | 'checkpoint' | 'destination'
export type CheckpointInterval = 10 | 25 | 50
export type AnalysisMode = 'live' | 'fixture'

export interface LatLon {
  lat: number
  lon: number
  label?: string
}

export interface HealthResponse {
  status: 'ok'
  version: string
  providers: { routing: string; weather: string }
}

export interface GeocodeResult {
  name: string
  admin1: string | null
  country_code: string
  lat: number
  lon: number
  label: string
}

export interface GeocodeResponse {
  results: GeocodeResult[]
}

export interface AnalyzeRequest {
  origin: LatLon
  destination: LatLon
  departure_time: string
  load_weight_lb: number
  checkpoint_interval_miles: CheckpointInterval
  mode?: AnalysisMode
}

export interface CheckpointWeather {
  forecast_time: string
  wind_mph: number | null
  wind_gust_mph: number | null
  rain_in_per_hr: number | null
  snow_in_per_hr: number | null
  temperature_f: number | null
  weather_code: number | null
}

export interface CheckpointRisk {
  level: RiskLevelOrUnknown
  value: number | null
  drivers: string[]
  wind_level: RiskLevel | null
  rain_level: RiskLevel | null
  snow_level: RiskLevel | null
  load_rule_applied: string | null
  /** Measurements absent for this forecast hour (wind, rain, snow). Non-empty with a
   *  `no_travel` level means a conclusive hazard was found despite gaps. */
  missing: ('wind' | 'rain' | 'snow')[]
}

export interface Checkpoint {
  index: number
  id: string
  kind: CheckpointKind
  lat: number
  lon: number
  distance_miles: number
  eta: string
  timezone: string | null
  utc_offset_seconds: number | null
  attributed_miles: number
  weather: CheckpointWeather | null
  risk: CheckpointRisk
}

export interface RouteSummary {
  no_travel_miles: number
  severe_miles: number
  high_miles: number
  moderate_miles: number
  low_miles: number
  unknown_miles: number
  average_risk: number | null
  coverage_complete: boolean
  max_level: RiskLevelOrUnknown
}

export interface RouteAnalysis {
  id: string
  name: string
  /** GeoJSON `[lon, lat]` pairs, simplified for display (about 30 m tolerance). */
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  /** Great-circle length of the full route geometry. Risk mileage adds up to this. */
  distance_miles: number
  /** The routing provider's own total, reported alongside for comparison. */
  provider_distance_miles: number
  duration_seconds: number
  departure_time: string
  arrival_time: string
  status: RouteStatus
  checkpoints: Checkpoint[]
  summary: RouteSummary
}

export interface Recommendation {
  route_id: string | null
  explanation: string
  /** Eligible routes only (status `ok`), best first. */
  ranking: string[]
  blocked_route_ids: string[]
  unverified_route_ids: string[]
}

/** Codes sent today: FEWER_ROUTES, DUPLICATE_ROUTES_REMOVED, HEATMAP_UNAVAILABLE, DEMO_MODE. */
export interface Warning {
  code: string
  message: string
}

/** One corridor grid cell. `lat`/`lon` is the cell centre; arrays have one value per hour. */
export interface HeatmapCell {
  lat: number
  lon: number
  /** Risk value 0 to 4 per hour, or null when that hour has no usable forecast. */
  risk: (number | null)[]
  wind: (number | null)[]
  rain: (number | null)[]
  snow: (number | null)[]
}

export interface Heatmap {
  /** Departure time floored to the hour (UTC). `hours[0]` equals `base_time`. */
  base_time: string
  /** 49 timestamps: forecast offsets 0 to 48 hours. */
  hours: string[]
  cell_size_miles: number
  /** Cell height and width in degrees: a cell spans centre ± half a step. */
  lat_step: number
  lon_step: number
  /** Empty when the heatmap forecast failed (see the HEATMAP_UNAVAILABLE warning). */
  cells: HeatmapCell[]
}

export interface Provenance {
  mode: AnalysisMode
  routing: { provider: string; endpoint: string; costing: string; fetched_at: string }
  weather: {
    provider: string
    model: string
    fetched_at: string
    forecast_window: { start: string; end: string }
  }
  notes: string[]
}

export interface AnalyzeResponse {
  request: AnalyzeRequest & { departure_time_utc: string }
  provenance: Provenance
  routes: RouteAnalysis[]
  recommendation: Recommendation
  warnings: Warning[]
  heatmap: Heatmap
}

/**
 * Error envelope for every non-2xx response. Codes: VALIDATION_ERROR (400, with `details` per
 * field), NO_ROUTE and TRIP_TOO_LARGE (422), THROTTLED (429), ROUTING_UNAVAILABLE,
 * WEATHER_UNAVAILABLE and GEOCODING_UNAVAILABLE (502, with `provider`), ROUTING_TIMEOUT,
 * WEATHER_TIMEOUT and GEOCODING_TIMEOUT (504, with `provider`).
 */
export interface ApiError {
  error: { code: string; message: string; provider?: string; details?: unknown }
}

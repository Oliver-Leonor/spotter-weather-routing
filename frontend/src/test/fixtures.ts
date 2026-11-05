import type {
  AnalyzeResponse,
  Checkpoint,
  RiskLevelOrUnknown,
  RouteAnalysis,
  RouteStatus,
} from '../types/api'

const VALUES: Record<RiskLevelOrUnknown, number | null> = {
  low: 0,
  moderate: 1,
  high: 2,
  severe: 3,
  no_travel: 4,
  unknown: null,
}

export function makeCheckpoint(
  routeId: string,
  index: number,
  level: RiskLevelOrUnknown,
  overrides: Partial<Checkpoint> = {},
): Checkpoint {
  const known = level !== 'unknown'
  return {
    index,
    id: `${routeId}-cp-${index}`,
    kind: 'checkpoint',
    lat: 39 + index * 0.1,
    lon: -100 - index * 0.5,
    distance_miles: index * 25,
    eta: `2026-11-06T${String(15 + index).padStart(2, '0')}:00:00Z`,
    timezone: 'America/Denver',
    utc_offset_seconds: -25200,
    attributed_miles: 25,
    weather: known
      ? {
          forecast_time: `2026-11-06T${String(15 + index).padStart(2, '0')}:00:00Z`,
          wind_mph: 12.3,
          wind_gust_mph: 20.1,
          rain_in_per_hr: 0,
          snow_in_per_hr: 0,
          temperature_f: 41.2,
          weather_code: 3,
        }
      : null,
    risk: {
      level,
      value: VALUES[level],
      drivers: [],
      wind_level: known ? 'low' : null,
      rain_level: known ? 'low' : null,
      snow_level: known ? 'low' : null,
      load_rule_applied: null,
      missing: known ? [] : ['wind', 'rain', 'snow'],
    },
    ...overrides,
  }
}

export function makeRoute(
  number: number,
  levels: RiskLevelOrUnknown[],
  status: RouteStatus = 'ok',
  overrides: Partial<RouteAnalysis> = {},
): RouteAnalysis {
  const id = `route-${number}`
  const checkpoints = levels.map((level, index) =>
    makeCheckpoint(id, index, level, {
      kind: index === 0 ? 'origin' : index === levels.length - 1 ? 'destination' : 'checkpoint',
      attributed_miles: index === 0 || index === levels.length - 1 ? 12.5 : 25,
    }),
  )
  const miles = (level: RiskLevelOrUnknown) =>
    checkpoints
      .filter((c) => c.risk.level === level)
      .reduce((sum, c) => sum + c.attributed_miles, 0)
  return {
    id,
    name: `Route ${'ABC'[number - 1]}`,
    geometry: {
      type: 'LineString',
      coordinates: checkpoints.map((c) => [c.lon, c.lat + number * 0.2] as [number, number]),
    },
    distance_miles: (levels.length - 1) * 25,
    provider_distance_miles: (levels.length - 1) * 25 + 0.6,
    duration_seconds: 7200 + number * 1800,
    departure_time: '2026-11-06T15:00:00Z',
    arrival_time: '2026-11-06T17:30:00Z',
    status,
    checkpoints,
    summary: {
      no_travel_miles: miles('no_travel'),
      severe_miles: miles('severe'),
      high_miles: miles('high'),
      moderate_miles: miles('moderate'),
      low_miles: miles('low'),
      unknown_miles: miles('unknown'),
      average_risk: 0.5,
      coverage_complete: status !== 'unverified',
      max_level: 'severe',
    },
    ...overrides,
  }
}

/** Route A is blocked, Route B is fine and recommended, Route C could not be verified. */
export function makeAnalysis(overrides: Partial<AnalyzeResponse> = {}): AnalyzeResponse {
  return {
    request: {
      origin: { lat: 39.7392, lon: -104.9903, label: 'Denver, Colorado, US' },
      destination: { lat: 39.0997, lon: -94.5786, label: 'Kansas City, Missouri, US' },
      departure_time: '2026-11-06T08:00:00-07:00',
      departure_time_utc: '2026-11-06T15:00:00Z',
      load_weight_lb: 42000,
      checkpoint_interval_miles: 25,
      mode: 'live',
    },
    provenance: {
      mode: 'live',
      routing: {
        provider: 'valhalla',
        endpoint: 'valhalla1.openstreetmap.de',
        costing: 'auto',
        fetched_at: '2026-11-06T14:59:00Z',
      },
      weather: {
        provider: 'open-meteo',
        model: 'best_match',
        fetched_at: '2026-11-06T14:58:00Z',
        forecast_window: { start: '2026-11-06T14:00:00Z', end: '2026-11-08T15:00:00Z' },
      },
      notes: [
        'Standard driving routes (Valhalla auto costing). Truck restrictions are not applied.',
      ],
    },
    routes: [
      makeRoute(1, ['low', 'severe', 'no_travel', 'low'], 'blocked'),
      makeRoute(2, ['low', 'moderate', 'high', 'low'], 'ok'),
      makeRoute(3, ['low', 'unknown', 'low', 'low'], 'unverified'),
    ],
    recommendation: {
      route_id: 'route-2',
      explanation:
        'Route B is recommended because it is the only route that is neither blocked nor unverified.',
      ranking: ['route-2'],
      blocked_route_ids: ['route-1'],
      unverified_route_ids: ['route-3'],
    },
    warnings: [],
    heatmap: {
      base_time: '2026-11-06T15:00:00Z',
      hours: [],
      cell_size_miles: 23,
      lat_step: 0.33,
      lon_step: 0.43,
      cells: [],
    },
    ...overrides,
  }
}

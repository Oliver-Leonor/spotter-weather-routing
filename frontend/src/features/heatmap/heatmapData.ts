import type { ExpressionSpecification } from 'maplibre-gl'
import type { Feature, FeatureCollection, Polygon } from 'geojson'
import { RISK_COLORS } from '../../lib/risk'
import type { Heatmap } from '../../types/api'

/** Stored for an hour without a usable forecast. It is painted grey, never as a risk level. */
export const UNKNOWN_RISK = -1

/**
 * The corridor grid as GeoJSON. Every cell carries its risk for every forecast hour (`r_0` to
 * `r_48`), so moving the time slider only swaps which property the paint expression reads. The
 * source data is built once per analysis and no request is made per slider move.
 */
export function heatmapFeatures(
  heatmap: Heatmap,
): FeatureCollection<Polygon, Record<string, number>> {
  const halfLat = heatmap.lat_step / 2
  const halfLon = heatmap.lon_step / 2
  return {
    type: 'FeatureCollection',
    features: heatmap.cells.map((cell): Feature<Polygon, Record<string, number>> => {
      const [west, east] = [cell.lon - halfLon, cell.lon + halfLon]
      const [south, north] = [cell.lat - halfLat, cell.lat + halfLat]
      const properties: Record<string, number> = {}
      cell.risk.forEach((value, hour) => {
        properties[`r_${hour}`] = value ?? UNKNOWN_RISK
      })
      return {
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [west, south],
              [east, south],
              [east, north],
              [west, north],
              [west, south],
            ],
          ],
        },
        properties,
      }
    }),
  }
}

/** Fill color for the cells at one forecast hour, using the same colors as the checkpoints. */
export function riskFillColor(hour: number): ExpressionSpecification {
  return [
    'match',
    ['get', `r_${hour}`],
    0,
    RISK_COLORS.low,
    1,
    RISK_COLORS.moderate,
    2,
    RISK_COLORS.high,
    3,
    RISK_COLORS.severe,
    4,
    RISK_COLORS.no_travel,
    RISK_COLORS.unknown,
  ]
}

/**
 * Fill opacity for the cells at one forecast hour. Calm cells are kept faint so the corridor does
 * not turn into a green block and the weather that matters stands out.
 */
export function riskFillOpacity(hour: number): ExpressionSpecification {
  return ['match', ['get', `r_${hour}`], 0, 0.14, UNKNOWN_RISK, 0.35, 0.5]
}

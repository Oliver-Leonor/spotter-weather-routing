import type { Feature, FeatureCollection, LineString, Point } from 'geojson'
import type {
  CheckpointKind,
  RiskLevelOrUnknown,
  RouteAnalysis,
  RouteStatus,
} from '../../types/api'

/** GeoJSON for the map sources. Pure, so the map component only has to hand it to MapLibre. */

export interface RouteProperties {
  id: string
  name: string
  status: RouteStatus
  selected: boolean
  recommended: boolean
}

export interface CheckpointProperties {
  id: string
  route_id: string
  level: RiskLevelOrUnknown
  kind: CheckpointKind
  on_selected_route: boolean
  selected: boolean
}

export type Bounds = [[number, number], [number, number]] // [[west, south], [east, north]]

export function routeFeatures(
  routes: RouteAnalysis[],
  selectedRouteId: string | null,
  recommendedRouteId: string | null,
): FeatureCollection<LineString, RouteProperties> {
  return {
    type: 'FeatureCollection',
    features: routes.map((route): Feature<LineString, RouteProperties> => ({
      type: 'Feature',
      geometry: route.geometry,
      properties: {
        id: route.id,
        name: route.name,
        status: route.status,
        selected: route.id === selectedRouteId,
        recommended: route.id === recommendedRouteId,
      },
    })),
  }
}

export function checkpointFeatures(
  routes: RouteAnalysis[],
  selectedRouteId: string | null,
  selectedCheckpointId: string | null,
): FeatureCollection<Point, CheckpointProperties> {
  return {
    type: 'FeatureCollection',
    features: routes.flatMap((route) =>
      route.checkpoints.map((checkpoint): Feature<Point, CheckpointProperties> => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [checkpoint.lon, checkpoint.lat] },
        properties: {
          id: checkpoint.id,
          route_id: route.id,
          level: checkpoint.risk.level,
          kind: checkpoint.kind,
          on_selected_route: route.id === selectedRouteId,
          selected: checkpoint.id === selectedCheckpointId,
        },
      })),
    ),
  }
}

export function boundsOf(routes: RouteAnalysis[]): Bounds | null {
  const points = routes.flatMap((route) => route.geometry.coordinates)
  if (points.length === 0) return null
  let [west, south] = points[0]
  let [east, north] = points[0]
  for (const [lon, lat] of points) {
    west = Math.min(west, lon)
    east = Math.max(east, lon)
    south = Math.min(south, lat)
    north = Math.max(north, lat)
  }
  return [
    [west, south],
    [east, north],
  ]
}

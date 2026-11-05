import 'maplibre-gl/dist/maplibre-gl.css'
import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
} from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { RISK_COLORS } from '../../lib/risk'
import type { RouteAnalysis } from '../../types/api'
import { boundsOf, checkpointFeatures, routeFeatures, type Bounds } from './mapData'

interface Props {
  routes: RouteAnalysis[]
  recommendedRouteId: string | null
  selectedRouteId: string | null
  selectedCheckpointId: string | null
  /** Changes when a new analysis arrives; the map only re-fits its view then. */
  fitKey: string | null
  isDemo: boolean
  onSelectRoute: (routeId: string) => void
  onSelectCheckpoint: (routeId: string, checkpointId: string) => void
}

// MapLibre 6 ships its worker as a separate module. The bundler has to be told to emit it as a
// file and MapLibre where to find it, or tiles never load.
setWorkerUrl(workerUrl)

const STYLE_URL =
  import.meta.env.VITE_MAP_STYLE_URL ?? 'https://tiles.openfreemap.org/styles/positron'
const CONTIGUOUS_US: Bounds = [
  [-125, 24.5],
  [-66.5, 49.5],
]
const CHECKPOINT_LAYERS = ['checkpoints', 'checkpoints-other']
const EMPTY = { type: 'FeatureCollection' as const, features: [] }

const LEVEL_COLOR: ExpressionSpecification = [
  'match',
  ['get', 'level'],
  'low',
  RISK_COLORS.low,
  'moderate',
  RISK_COLORS.moderate,
  'high',
  RISK_COLORS.high,
  'severe',
  RISK_COLORS.severe,
  'no_travel',
  RISK_COLORS.no_travel,
  RISK_COLORS.unknown,
]

function addLayers(map: MapLibreMap) {
  map.addSource('routes', { type: 'geojson', data: EMPTY })
  map.addSource('checkpoints', { type: 'geojson', data: EMPTY })

  const line = { 'line-cap': 'round', 'line-join': 'round' } as const
  map.addLayer({
    id: 'routes-other',
    type: 'line',
    source: 'routes',
    filter: ['!', ['get', 'selected']],
    layout: line,
    paint: { 'line-color': '#64748b', 'line-width': 4, 'line-opacity': 0.6 },
  })
  map.addLayer({
    id: 'route-selected-casing',
    type: 'line',
    source: 'routes',
    filter: ['get', 'selected'],
    layout: line,
    paint: { 'line-color': '#134e4a', 'line-width': 9 },
  })
  map.addLayer({
    id: 'route-selected',
    type: 'line',
    source: 'routes',
    filter: ['get', 'selected'],
    layout: line,
    paint: { 'line-color': '#14b8a6', 'line-width': 5 },
  })
  // A wide invisible line so a route is easy to hit with a finger.
  map.addLayer({
    id: 'routes-hit',
    type: 'line',
    source: 'routes',
    layout: line,
    paint: { 'line-color': '#000000', 'line-width': 22, 'line-opacity': 0 },
  })
  map.addLayer({
    id: 'checkpoints-other',
    type: 'circle',
    source: 'checkpoints',
    filter: ['!', ['get', 'on_selected_route']],
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 2.5, 9, 5],
      'circle-color': LEVEL_COLOR,
      'circle-opacity': 0.8,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 1,
    },
  })
  map.addLayer({
    id: 'checkpoints',
    type: 'circle',
    source: 'checkpoints',
    filter: ['get', 'on_selected_route'],
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 5, 9, 9],
      'circle-color': LEVEL_COLOR,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
    },
  })
  map.addLayer({
    id: 'checkpoint-selected',
    type: 'circle',
    source: 'checkpoints',
    filter: ['get', 'selected'],
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 9, 9, 14],
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-color': '#0f1b2d',
      'circle-stroke-width': 3,
    },
  })
}

function hasWebGL(): boolean {
  const canvas = document.createElement('canvas')
  return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'))
}

function endpointMarker(label: string): HTMLElement {
  const element = document.createElement('div')
  element.className = 'map-endpoint'
  element.textContent = label
  return element
}

/**
 * The map is created once. Results, selection and the view are then pushed into it with
 * `setData` and `fitBounds`, so selecting a route or checkpoint never rebuilds the map.
 */
export default function RouteMap({
  routes,
  recommendedRouteId,
  selectedRouteId,
  selectedCheckpointId,
  fitKey,
  isDemo,
  onSelectRoute,
  onSelectCheckpoint,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  // The map that has finished loading its style, or null. Layers can only be touched after that.
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [webglSupported] = useState(hasWebGL)

  // Map event handlers are registered once, so they read the latest callbacks through a ref.
  const callbacks = useRef({ onSelectRoute, onSelectCheckpoint })
  useEffect(() => {
    callbacks.current = { onSelectRoute, onSelectCheckpoint }
  })

  useEffect(() => {
    if (!containerRef.current || !webglSupported) return
    const created = new MapLibreMap({
      container: containerRef.current,
      style: STYLE_URL,
      bounds: CONTIGUOUS_US,
      dragRotate: false,
      pitchWithRotate: false,
      attributionControl: { compact: true },
    })
    created.touchZoomRotate.disableRotation()
    created.addControl(new NavigationControl({ showCompass: false }), 'top-left')

    created.on('load', () => {
      addLayers(created)
      setMap(created)
    })
    created.on('click', (event) => {
      const box: [[number, number], [number, number]] = [
        [event.point.x - 6, event.point.y - 6],
        [event.point.x + 6, event.point.y + 6],
      ]
      // A checkpoint sits on its route line, so it wins when both are under the pointer.
      const checkpoint = created.queryRenderedFeatures(box, { layers: CHECKPOINT_LAYERS })[0]
      if (checkpoint) {
        callbacks.current.onSelectCheckpoint(
          String(checkpoint.properties.route_id),
          String(checkpoint.properties.id),
        )
        return
      }
      const route = created.queryRenderedFeatures(box, { layers: ['routes-hit'] })[0]
      if (route) callbacks.current.onSelectRoute(String(route.properties.id))
    })
    created.on('mousemove', (event) => {
      const hit = created.queryRenderedFeatures(event.point, {
        layers: [...CHECKPOINT_LAYERS, 'routes-hit'],
      })
      created.getCanvas().style.cursor = hit.length > 0 ? 'pointer' : ''
    })

    return () => {
      created.remove()
      setMap((current) => (current === created ? null : current))
    }
  }, [webglSupported])

  useEffect(() => {
    if (!map) return
    map
      .getSource<GeoJSONSource>('routes')
      ?.setData(routeFeatures(routes, selectedRouteId, recommendedRouteId))
    map
      .getSource<GeoJSONSource>('checkpoints')
      ?.setData(checkpointFeatures(routes, selectedRouteId, selectedCheckpointId))
  }, [map, routes, selectedRouteId, selectedCheckpointId, recommendedRouteId])

  // Fit the view and place the start and end markers. This is an effect event so that it reads
  // the current routes without making the effect below run on every selection.
  const showAnalysis = useEffectEvent((target: MapLibreMap) => {
    const bounds = boundsOf(routes)
    if (!bounds) return undefined
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    target.fitBounds(bounds, { padding: 56, maxZoom: 11, duration: reduceMotion ? 0 : 700 })

    const line = routes[0].geometry.coordinates
    const markers = [
      new Marker({ element: endpointMarker('Start'), anchor: 'bottom' }).setLngLat(line[0]),
      new Marker({ element: endpointMarker('End'), anchor: 'bottom' }).setLngLat(
        line[line.length - 1],
      ),
    ]
    markers.forEach((marker) => marker.addTo(target))
    return () => markers.forEach((marker) => marker.remove())
  })

  // Once per analysis (fitKey), never on a selection change: selecting must not move the map.
  useEffect(() => {
    if (!map || fitKey === null) return
    return showAnalysis(map)
  }, [map, fitKey])

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        role="application"
        aria-label="Map of the route options. Use the route cards to select routes and checkpoints."
        className="h-full w-full"
      />
      {isDemo && (
        <p className="pointer-events-none absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-sm border-2 border-ink bg-hazard px-2.5 py-1 text-sm font-semibold whitespace-nowrap text-ink shadow-md">
          Simulated weather
        </p>
      )}
      {!webglSupported && (
        <p className="absolute inset-0 flex items-center justify-center bg-slate-200 p-6 text-center text-sm text-slate-700">
          The map could not be displayed in this browser. The route cards still show the full
          comparison.
        </p>
      )}
    </div>
  )
}

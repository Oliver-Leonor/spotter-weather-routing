import { useMutation } from '@tanstack/react-query'
import { CloudLightning, LoaderCircle, TriangleAlert } from 'lucide-react'
import { Suspense, lazy, useState } from 'react'
import { AttributionFooter } from './components/AttributionFooter'
import { DemoBanner } from './components/DemoBanner'
import { Legend } from './components/Legend'
import { ForecastSlider } from './features/heatmap/ForecastSlider'
import { createHourStore } from './features/heatmap/hourStore'
import { LayerToggles, type MapLayers } from './features/heatmap/LayerToggles'
import { CheckpointDetail } from './features/route-comparison/CheckpointDetail'
import { RecommendationBanner } from './features/route-comparison/RecommendationBanner'
import { RouteCard } from './features/route-comparison/RouteCard'
import { TripSummary } from './features/route-comparison/TripSummary'
import { TRIP_FORM_FIELDS } from './features/trip-planner/fields'
import { TripForm, type TripFormValues } from './features/trip-planner/TripForm'
import { useRevealOnSmallScreens } from './hooks/useRevealOnSmallScreens'
import { ApiRequestError, analyzeRoutes, fieldErrors } from './lib/api'
import type { AnalyzeResponse } from './types/api'

// MapLibre is most of the JavaScript, so it loads on its own while the form is already usable.
const RouteMap = lazy(() => import('./features/route-map/RouteMap'))

/**
 * What the error alert says. A rejected field is explained on that field in the form, so the
 * alert only points there. A message for a field that has no input in the form (the demo mode
 * being disabled on the server, for example) is shown here, or nobody would ever see it.
 */
function alertMessages(
  error: Error,
  isValidationError: boolean,
  fieldMessages: Record<string, string>,
): string[] {
  if (!isValidationError) return [error.message]
  const formFields: readonly string[] = TRIP_FORM_FIELDS
  const fields = Object.keys(fieldMessages)
  const messages = fields.some((field) => formFields.includes(field))
    ? ['Check the highlighted fields and compare again.']
    : []
  messages.push(...fields.filter((f) => !formFields.includes(f)).map((f) => fieldMessages[f]))
  return messages.length > 0 ? messages : [error.message]
}

export default function App() {
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null)
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const [selectedCheckpointId, setSelectedCheckpointId] = useState<string | null>(null)
  const [resultId, setResultId] = useState<string | null>(null) // a new value per analysis
  // The slider's hour lives outside React state so that dragging it only repaints the map.
  const [hourStore] = useState(createHourStore)
  const [layers, setLayers] = useState<MapLayers>({
    heatmap: true,
    checkpoints: true,
    otherRoutes: true,
  })

  const comparison = useMutation({
    mutationFn: (trip: TripFormValues) => analyzeRoutes(trip),
    // The form may now describe a different trip, so results for the earlier one are removed
    // as soon as a new comparison starts. They never sit next to a failed or pending request.
    onMutate: () => {
      setAnalysis(null)
      setSelectedRouteId(null)
      setSelectedCheckpointId(null)
      hourStore.set(0)
    },
    onSuccess: (result) => {
      setAnalysis(result)
      setResultId(String(Date.now()))
      setSelectedRouteId(result.recommendation.route_id ?? result.routes[0]?.id ?? null)
      setSelectedCheckpointId(null)
    },
  })

  const routes = analysis?.routes ?? []
  const isDemo = analysis?.provenance.mode === 'fixture'
  const selectedRoute = routes.find((route) => route.id === selectedRouteId) ?? null
  const selectedCheckpoint =
    selectedRoute?.checkpoints.find((checkpoint) => checkpoint.id === selectedCheckpointId) ?? null
  const warnings = (analysis?.warnings ?? []).filter((warning) => warning.code !== 'DEMO_MODE')
  const hasCorridorForecast = (analysis?.heatmap.cells.length ?? 0) > 0

  const fitKey = analysis
    ? `${analysis.provenance.routing.fetched_at}|${analysis.request.departure_time_utc}|${analysis.provenance.weather.fetched_at}|${routes.length}`
    : null
  const resultsRef = useRevealOnSmallScreens<HTMLDivElement>(resultId)
  const detailRef = useRevealOnSmallScreens<HTMLDivElement>(selectedCheckpoint?.id ?? null)

  const error = comparison.error
  const serverFieldErrors = fieldErrors(error)
  const isValidationError = error instanceof ApiRequestError && error.code === 'VALIDATION_ERROR'
  const errorMessages = error ? alertMessages(error, isValidationError, serverFieldErrors) : []

  function selectRoute(routeId: string) {
    setSelectedRouteId(routeId)
    setSelectedCheckpointId(null)
  }

  function selectCheckpoint(routeId: string, checkpointId: string) {
    setSelectedRouteId(routeId)
    setSelectedCheckpointId(checkpointId)
  }

  function stepCheckpoint(offset: number) {
    if (!selectedRoute || !selectedCheckpoint) return
    const next = selectedRoute.checkpoints[selectedCheckpoint.index + offset]
    if (next) setSelectedCheckpointId(next.id)
  }

  return (
    <div className="flex min-h-full flex-col lg:h-full">
      <header className="bg-ink text-white">
        <div className="flex items-center gap-3 px-4 py-2.5">
          <CloudLightning className="h-7 w-7 shrink-0 text-teal-400" aria-hidden="true" />
          <div className="flex flex-wrap items-baseline gap-x-3">
            <h1 className="font-display text-2xl leading-none font-semibold tracking-wide">
              StormRoute
            </h1>
            <p className="text-sm text-slate-300">Weather-aware trip planning for truck drivers</p>
          </div>
        </div>
      </header>

      {isDemo && <DemoBanner />}

      <main className="flex flex-1 flex-col lg:grid lg:min-h-0 lg:grid-cols-[27rem_minmax(0,1fr)]">
        {/* On small screens these blocks are laid out by <main>, so the map can sit between the
            recommendation and the route cards. On large screens they form one scrolling rail. */}
        <div className="contents lg:flex lg:min-h-0 lg:flex-col lg:overflow-y-auto lg:border-r lg:border-slate-300 lg:bg-paper">
          <section aria-label="Trip" className="order-1 border-b border-slate-300 bg-white p-4">
            <TripForm
              onSubmit={(trip) => comparison.mutate(trip)}
              isLoading={comparison.isPending}
              serverErrors={serverFieldErrors}
            />
          </section>

          <div
            ref={resultsRef}
            className="order-2 flex scroll-mt-28 flex-col gap-3 p-4 empty:hidden lg:pb-0"
          >
            {comparison.isPending && (
              <p role="status" className="flex items-center gap-2 text-sm font-medium text-ink">
                <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
                Finding routes and checking the forecast along each one…
              </p>
            )}
            {error && !comparison.isPending && (
              <div
                role="alert"
                className="rounded-lg border border-risk-severe bg-red-50 p-3 text-sm text-ink"
              >
                <div className="flex items-start gap-2 font-medium">
                  <TriangleAlert
                    className="mt-0.5 h-4 w-4 shrink-0 text-risk-severe"
                    aria-hidden="true"
                  />
                  <div className="flex flex-col gap-1">
                    {errorMessages.map((message) => (
                      <p key={message}>{message}</p>
                    ))}
                  </div>
                </div>
                {!isValidationError && comparison.variables && (
                  <button
                    type="button"
                    onClick={() => comparison.mutate(comparison.variables)}
                    className="button-secondary mt-2"
                  >
                    Try again
                  </button>
                )}
              </div>
            )}
            {analysis && <TripSummary analysis={analysis} />}
            {analysis && (
              <RecommendationBanner recommendation={analysis.recommendation} routes={routes} />
            )}
            {warnings.map((warning) => (
              <p
                key={warning.code}
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
              >
                {warning.message}
              </p>
            ))}
          </div>

          <div className="order-4 flex flex-col gap-3 p-4">
            {routes.map((route) => (
              <RouteCard
                key={route.id}
                route={route}
                isSelected={route.id === selectedRouteId}
                isRecommended={route.id === analysis?.recommendation.route_id}
                selectedCheckpointId={selectedCheckpointId}
                onSelect={selectRoute}
                onSelectCheckpoint={selectCheckpoint}
              />
            ))}
            {analysis && <Legend />}
            <AttributionFooter notes={analysis?.provenance.notes ?? []} />
          </div>
        </div>

        <section
          aria-label="Map"
          className="relative order-3 flex flex-col lg:order-none lg:min-h-0"
        >
          {/* On a phone the map is kept short enough to stay in view with the forecast slider. */}
          <div className="relative h-[42vh] min-h-72 lg:h-full">
            <Suspense fallback={<div className="h-full w-full bg-slate-200" />}>
              <RouteMap
                routes={routes}
                recommendedRouteId={analysis?.recommendation.route_id ?? null}
                selectedRouteId={selectedRouteId}
                selectedCheckpointId={selectedCheckpointId}
                fitKey={fitKey}
                isDemo={isDemo}
                heatmap={analysis?.heatmap ?? null}
                hourStore={hourStore}
                layers={layers}
                onSelectRoute={selectRoute}
                onSelectCheckpoint={selectCheckpoint}
              />
            </Suspense>
            {!analysis && !comparison.isPending && (
              <p className="pointer-events-none absolute inset-x-4 bottom-6 mx-auto max-w-md rounded-lg bg-white/95 p-4 text-center text-base text-ink shadow-lg">
                Plan a trip to see routes, checkpoints and the weather risk along each one.
              </p>
            )}
          </div>
          {analysis && (
            <section
              aria-label="Corridor forecast"
              className="flex flex-col gap-3 border-b border-slate-300 bg-white p-4 lg:absolute lg:bottom-8 lg:left-3 lg:z-20 lg:w-80 lg:rounded-lg lg:border lg:shadow-xl"
            >
              {hasCorridorForecast ? (
                <ForecastSlider
                  key={resultId}
                  store={hourStore}
                  hours={analysis.heatmap.hours}
                  departure={analysis.request.departure_time_utc}
                  timeZone={analysis.routes[0]?.checkpoints[0]?.timezone ?? null}
                />
              ) : (
                <p className="text-sm text-slate-700">No corridor forecast for this trip.</p>
              )}
              <LayerToggles
                layers={layers}
                onChange={setLayers}
                heatmapAvailable={hasCorridorForecast}
              />
            </section>
          )}
          {selectedRoute && selectedCheckpoint && (
            <div
              ref={detailRef}
              className="scroll-mt-28 p-4 lg:absolute lg:top-3 lg:right-3 lg:z-20 lg:w-88 lg:p-0 lg:shadow-xl"
            >
              <CheckpointDetail
                route={selectedRoute}
                checkpoint={selectedCheckpoint}
                onPrevious={() => stepCheckpoint(-1)}
                onNext={() => stepCheckpoint(1)}
                onClose={() => setSelectedCheckpointId(null)}
              />
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

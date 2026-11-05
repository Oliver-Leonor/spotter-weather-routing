import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ApiRequestError, analyzeRoutes } from './lib/api'
import { makeAnalysis } from './test/fixtures'
import type { AnalyzeResponse } from './types/api'

vi.mock('./lib/api', async (original) => ({
  ...(await original<typeof import('./lib/api')>()),
  analyzeRoutes: vi.fn(),
  searchPlaces: vi.fn().mockResolvedValue([]),
}))

// MapLibre needs WebGL, which jsdom does not have. The stub exposes what the map was given and
// lets a test act as a click on the map.
vi.mock('./features/route-map/RouteMap', () => ({
  default: (props: any) => (
    <div
      data-testid="map"
      data-routes={props.routes.length}
      data-selected-route={props.selectedRouteId ?? ''}
      data-selected-checkpoint={props.selectedCheckpointId ?? ''}
      data-demo={String(props.isDemo)}
    >
      <button type="button" onClick={() => props.onSelectCheckpoint('route-1', 'route-1-cp-2')}>
        map: checkpoint on Route A
      </button>
      <button type="button" onClick={() => props.onSelectRoute('route-3')}>
        map: Route C line
      </button>
    </div>
  ),
}))

const demoAnalysis = (): AnalyzeResponse => {
  const analysis = makeAnalysis()
  return {
    ...analysis,
    provenance: { ...analysis.provenance, mode: 'fixture' },
    warnings: [{ code: 'DEMO_MODE', message: 'Demo data: recorded routes with scripted weather.' }],
  }
}

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  )
}

async function runDemo(analysis: AnalyzeResponse = demoAnalysis()) {
  vi.mocked(analyzeRoutes).mockResolvedValue(analysis)
  renderApp()
  await userEvent.click(screen.getByRole('button', { name: 'Run the demo trip' }))
  await screen.findByRole('heading', { name: 'Take Route B' })
}

const routeButton = (name: string) => screen.getByRole('button', { name })
const map = () => screen.getByTestId('map')

beforeEach(() => vi.mocked(analyzeRoutes).mockReset())

describe('before a trip is compared', () => {
  it('shows the product name and invites the driver to plan a trip', async () => {
    renderApp()
    expect(screen.getByRole('heading', { name: 'StormRoute' })).toBeInTheDocument()
    expect(screen.getByText(/Plan a trip to see routes/)).toBeInTheDocument()
    expect(screen.queryByText(/Simulated weather/)).not.toBeInTheDocument()
    expect(await screen.findByTestId('map')).toHaveAttribute('data-routes', '0')
  })
})

describe('comparing routes', () => {
  it('sends the trip and shows progress while the analysis runs', async () => {
    let finish!: (analysis: AnalyzeResponse) => void
    vi.mocked(analyzeRoutes).mockReturnValue(new Promise((resolve) => (finish = resolve)))
    renderApp()

    await userEvent.click(screen.getByRole('button', { name: 'Run the demo trip' }))

    expect(vi.mocked(analyzeRoutes).mock.calls[0][0]).toMatchObject({
      mode: 'fixture',
      load_weight_lb: 42000,
    })
    expect(screen.getByRole('status')).toHaveTextContent(
      'Finding routes and checking the forecast along each one',
    )
    finish(demoAnalysis())
    expect(await screen.findByRole('heading', { name: 'Take Route B' })).toBeInTheDocument()
  })

  it('shows every route with the recommended one marked and selected', async () => {
    await runDemo()

    expect(screen.getAllByRole('article')).toHaveLength(3)
    expect(routeButton('Route B')).toHaveAttribute('aria-pressed', 'true')
    expect(routeButton('Route A')).toHaveAttribute('aria-pressed', 'false')
    const recommendedCard = screen.getAllByRole('article')[1]
    expect(within(recommendedCard).getByText('Recommended')).toBeInTheDocument()
    expect(map()).toHaveAttribute('data-routes', '3')
    expect(map()).toHaveAttribute('data-selected-route', 'route-2')
  })

  it('selects the first route when none is recommended', async () => {
    const analysis = makeAnalysis()
    await runDemoWithoutRecommendation(analysis)
    expect(routeButton('Route A')).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps a prominent simulated-weather label on screen for demo results', async () => {
    await runDemo()
    const label = screen.getByRole('note', { name: 'Simulated weather' })
    expect(label).toHaveTextContent('Simulated weather')
    expect(label).toHaveTextContent('This is demo data, not a real forecast')
    expect(map()).toHaveAttribute('data-demo', 'true')
  })

  it('does not label live results as simulated', async () => {
    await runDemo(makeAnalysis())
    expect(screen.queryByRole('note', { name: 'Simulated weather' })).not.toBeInTheDocument()
    expect(map()).toHaveAttribute('data-demo', 'false')
  })

  it('shows provider warnings but not the demo notice twice', async () => {
    const analysis = demoAnalysis()
    analysis.warnings.push({
      code: 'FEWER_ROUTES',
      message: 'The routing provider returned 2 distinct routes for this trip.',
    })
    await runDemo(analysis)
    expect(
      screen.getByText('The routing provider returned 2 distinct routes for this trip.'),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Demo data: recorded routes with scripted weather.'),
    ).not.toBeInTheDocument()
  })

  it('discloses the routing limitation and credits the data providers', async () => {
    await runDemo()
    expect(screen.getByText(/Truck restrictions are not applied/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'OpenStreetMap contributors' })).toHaveAttribute(
      'href',
      'https://www.openstreetmap.org/copyright',
    )
    expect(screen.getByRole('link', { name: 'Open-Meteo' })).toBeInTheDocument()
  })
})

async function runDemoWithoutRecommendation(analysis: AnalyzeResponse) {
  vi.mocked(analyzeRoutes).mockResolvedValue({
    ...analysis,
    recommendation: {
      route_id: null,
      explanation: 'No safe route is currently recommended. Route A: No Travel at checkpoint 2.',
      ranking: [],
      blocked_route_ids: ['route-1'],
      unverified_route_ids: ['route-3'],
    },
  })
  renderApp()
  await userEvent.click(screen.getByRole('button', { name: 'Run the demo trip' }))
  await screen.findByRole('heading', { name: 'No safe route is currently recommended' })
}

describe('exploring the result', () => {
  it('selects a route from its card', async () => {
    await runDemo()
    await userEvent.click(routeButton('Route A'))
    expect(routeButton('Route A')).toHaveAttribute('aria-pressed', 'true')
    expect(map()).toHaveAttribute('data-selected-route', 'route-1')
  })

  it('selects a route from the map', async () => {
    await runDemo()
    await userEvent.click(screen.getByRole('button', { name: 'map: Route C line' }))
    expect(routeButton('Route C')).toHaveAttribute('aria-pressed', 'true')
  })

  it('opens checkpoint details from the risk ribbon and steps along the route', async () => {
    await runDemo()
    const routeA = screen.getAllByRole('article')[0]

    await userEvent.click(within(routeA).getByRole('button', { name: 'Mile 25, Severe' }))

    const details = screen.getByRole('region', { name: 'Checkpoint details' })
    expect(within(details).getByRole('heading', { name: 'Route A, mile 25' })).toBeInTheDocument()
    expect(routeButton('Route A')).toHaveAttribute('aria-pressed', 'true')
    expect(map()).toHaveAttribute('data-selected-checkpoint', 'route-1-cp-1')

    await userEvent.click(within(details).getByRole('button', { name: 'Next checkpoint' }))
    expect(within(details).getByRole('heading', { name: 'Route A, mile 50' })).toBeInTheDocument()
    await userEvent.click(within(details).getByRole('button', { name: 'Previous checkpoint' }))
    expect(within(details).getByRole('heading', { name: 'Route A, mile 25' })).toBeInTheDocument()

    await userEvent.click(within(details).getByRole('button', { name: 'Close checkpoint details' }))
    expect(screen.queryByRole('region', { name: 'Checkpoint details' })).not.toBeInTheDocument()
  })

  it('opens checkpoint details from a checkpoint on the map', async () => {
    await runDemo()
    await userEvent.click(screen.getByRole('button', { name: 'map: checkpoint on Route A' }))
    expect(screen.getByRole('heading', { name: 'Route A, mile 50' })).toBeInTheDocument()
    expect(routeButton('Route A')).toHaveAttribute('aria-pressed', 'true')
  })

  it('closes checkpoint details when another route is selected', async () => {
    await runDemo()
    await userEvent.click(screen.getByRole('button', { name: 'map: checkpoint on Route A' }))
    await userEvent.click(routeButton('Route B'))
    expect(screen.queryByRole('region', { name: 'Checkpoint details' })).not.toBeInTheDocument()
  })

  it('starts fresh when the trip is compared again', async () => {
    await runDemo()
    await userEvent.click(screen.getByRole('button', { name: 'map: checkpoint on Route A' }))

    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))

    await waitFor(() => expect(analyzeRoutes).toHaveBeenCalledTimes(2))
    await waitFor(() =>
      expect(screen.queryByRole('region', { name: 'Checkpoint details' })).not.toBeInTheDocument(),
    )
    expect(routeButton('Route B')).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('when the analysis fails', () => {
  it('explains a provider failure and offers to try again', async () => {
    vi.mocked(analyzeRoutes)
      .mockRejectedValueOnce(
        new ApiRequestError(
          502,
          'ROUTING_UNAVAILABLE',
          'The routing service is unavailable right now. Please try again shortly.',
          {
            provider: 'valhalla',
          },
        ),
      )
      .mockResolvedValueOnce(demoAnalysis())
    renderApp()
    await userEvent.click(screen.getByRole('button', { name: 'Run the demo trip' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(
      'The routing service is unavailable right now. Please try again shortly.',
    )
    expect(screen.queryByRole('article')).not.toBeInTheDocument()

    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'Take Route B' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('points to the fields the server rejected', async () => {
    vi.mocked(analyzeRoutes).mockRejectedValueOnce(
      new ApiRequestError(400, 'VALIDATION_ERROR', 'Invalid request.', {
        details: { destination: ['Origin and destination must be different places.'] },
      }),
    )
    renderApp()
    await userEvent.click(screen.getByRole('button', { name: 'Run the demo trip' }))

    expect(
      await screen.findByText('Origin and destination must be different places.'),
    ).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Check the highlighted fields and compare again.',
    )
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('never leaves an earlier result on screen when a later comparison fails', async () => {
    // Review finding (PR #3): the form may now describe a different trip, so a recommendation
    // from the earlier one must not stay visible next to it.
    await runDemo()
    vi.mocked(analyzeRoutes).mockRejectedValueOnce(
      new ApiRequestError(504, 'WEATHER_TIMEOUT', 'The weather service did not respond in time.'),
    )

    await userEvent.clear(screen.getByLabelText('Load weight'))
    await userEvent.type(screen.getByLabelText('Load weight'), '28000')
    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The weather service did not respond in time.',
    )
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Take Route B' })).not.toBeInTheDocument()
    expect(screen.queryByRole('note', { name: 'Simulated weather' })).not.toBeInTheDocument()
    expect(map()).toHaveAttribute('data-routes', '0')
  })

  it('clears the earlier result as soon as a new comparison starts', async () => {
    await runDemo()
    vi.mocked(analyzeRoutes).mockReturnValueOnce(new Promise(() => {})) // never settles

    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Finding routes')
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Take Route B' })).not.toBeInTheDocument()
    expect(map()).toHaveAttribute('data-routes', '0')
  })
})

describe('which trip the result belongs to', () => {
  it('states the analyzed trip next to the recommendation', async () => {
    await runDemo()
    const summary = screen.getByRole('region', { name: 'Analyzed trip' })
    expect(summary).toHaveTextContent('Denver, Colorado, US to Kansas City, Missouri, US')
    expect(summary).toHaveTextContent('Departs Fri, Nov 6, 8:00 AM MST')
    expect(summary).toHaveTextContent('42,000 lb load')
    expect(summary).toHaveTextContent('weather checked every 25 mi')
  })
})

describe('with a keyboard only', () => {
  it('opens checkpoint details and steps through them without touching the map', async () => {
    await runDemo()
    const routeA = screen.getAllByRole('article')[0]
    within(routeA).getByRole('button', { name: 'Route A' }).focus()

    await userEvent.tab() // into Route A's ribbon
    await userEvent.keyboard('{ArrowRight}{Enter}')

    const details = screen.getByRole('region', { name: 'Checkpoint details' })
    expect(within(details).getByRole('heading', { name: 'Route A, mile 25' })).toBeInTheDocument()
    expect(within(routeA).getByRole('button', { name: 'Mile 25, Severe' })).toHaveFocus()

    await userEvent.keyboard('{ArrowRight}{Enter}')
    expect(within(details).getByRole('heading', { name: 'Route A, mile 50' })).toBeInTheDocument()
  })
})

describe('on a small screen', () => {
  const scrollIntoView = vi.fn()

  function useViewport(narrow: boolean) {
    scrollIntoView.mockReset()
    Element.prototype.scrollIntoView = scrollIntoView
    vi.stubGlobal(
      'matchMedia',
      (query: string) => ({ matches: narrow && query === '(max-width: 1023px)' }) as MediaQueryList,
    )
  }

  it('brings the recommendation into view, since it sits below the form', async () => {
    useViewport(true)
    await runDemo()
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    vi.unstubAllGlobals()
  })

  it('brings checkpoint details into view when a checkpoint is picked', async () => {
    useViewport(true)
    await runDemo()
    await userEvent.click(screen.getByRole('button', { name: 'map: checkpoint on Route A' }))
    expect(scrollIntoView).toHaveBeenCalledTimes(2)
    vi.unstubAllGlobals()
  })

  it('does not move the page on a wide screen, where everything is already visible', async () => {
    useViewport(false)
    await runDemo()
    await userEvent.click(screen.getByRole('button', { name: 'map: checkpoint on Route A' }))
    expect(scrollIntoView).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})

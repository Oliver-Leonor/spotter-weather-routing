import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, type Page, type Request } from '@playwright/test'

/**
 * Recorded responses of the real backend in demo mode (departure 2026-11-06 15:00 UTC, 25 mile
 * checkpoints) for a 42,000 lb and a 28,000 lb load. Regenerate them from the backend with
 * `analysis.service.analyze` if the response contract changes.
 */
const fixture = (name: string) =>
  readFileSync(fileURLToPath(new URL(`./fixtures/${name}.json`, import.meta.url)), 'utf8')
const HEAVY_LOAD = fixture('demo-heavy-load')
const LIGHT_LOAD = fixture('demo-light-load')

/** A map style with no tiles and no fonts, so the map renders without the network. */
const BLANK_STYLE = {
  version: 8,
  name: 'blank',
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#e8ecef' } }],
}

const PLACES: Record<string, object[]> = {
  den: [
    {
      name: 'Denver',
      admin1: 'Colorado',
      country_code: 'US',
      lat: 39.73915,
      lon: -104.9847,
      label: 'Denver, Colorado, US',
    },
    {
      name: 'Denver City',
      admin1: 'Texas',
      country_code: 'US',
      lat: 32.96,
      lon: -102.83,
      label: 'Denver City, Texas, US',
    },
  ],
  kan: [
    {
      name: 'Kansas City',
      admin1: 'Missouri',
      country_code: 'US',
      lat: 39.09973,
      lon: -94.57857,
      label: 'Kansas City, Missouri, US',
    },
  ],
}

/** The body of an analysis request, as the app sends it. */
export type AnalysisRequest = Record<string, unknown> & { load_weight_lb: number }

export interface Backend {
  /** Bodies of the analysis requests the app has sent. */
  analyses: AnalysisRequest[]
  /** Make the next analysis request fail with this status and error envelope. */
  failNext: (status: number, error: Record<string, unknown>) => void
}

export async function mockBackend(page: Page): Promise<Backend> {
  const analyses: AnalysisRequest[] = []
  let failure: { status: number; body: string } | null = null

  await page.route('**/api/routes/analyze/', async (route) => {
    const body = route.request().postDataJSON() as AnalysisRequest
    analyses.push(body)
    if (failure) {
      const { status, body: errorBody } = failure
      failure = null
      await route.fulfill({ status, contentType: 'application/json', body: errorBody })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: body.load_weight_lb > 30_000 ? HEAVY_LOAD : LIGHT_LOAD,
    })
  })
  await page.route('**/api/geocode/**', async (route) => {
    const query = new URL(route.request().url()).searchParams.get('q') ?? ''
    const results = PLACES[query.slice(0, 3).toLowerCase()] ?? []
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ results }) })
  })
  await page.route('https://tiles.openfreemap.org/**', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(BLANK_STYLE) }),
  )
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort())

  return {
    analyses,
    failNext: (status, error) => {
      failure = { status, body: JSON.stringify({ error }) }
    },
  }
}

/** Open the app, run the demo trip and wait for the result and the map. */
export async function runDemoTrip(page: Page): Promise<Backend> {
  const backend = await mockBackend(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Run the demo trip' }).click()
  await expect(page.getByRole('heading', { name: 'Take Route C' })).toBeVisible()
  await mapIsIdle(page)
  return backend
}

/** The map canvas exists and has finished drawing what it was last given. */
export async function mapIsIdle(page: Page) {
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible()
  await page.waitForTimeout(1200)
}

/**
 * A picture of what the map itself has drawn. Everything that sits on top of the canvas (the
 * truck and start/end markers, the corridor panel, the checkpoint details, the map controls, and
 * the sticky simulated-weather band when the page is scrolled) is hidden for the capture, so two
 * pictures differ only if the map's own layers changed.
 */
export function mapPicture(page: Page): Promise<Buffer> {
  return page.locator('canvas.maplibregl-canvas').screenshot({
    style: `
      .maplibregl-marker, .maplibregl-control-container,
      [aria-label="Corridor forecast"], [aria-label="Checkpoint details"],
      [aria-label="Map"] p, [aria-label="Simulated weather"] { visibility: hidden !important; }
    `,
  })
}

/** Every request the page makes from now on. */
export function recordRequests(page: Page): Request[] {
  const requests: Request[] = []
  page.on('request', (request) => requests.push(request))
  return requests
}

export async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
}

import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError, analyzeRoutes, fieldErrors, searchPlaces } from './api'
import { makeAnalysis } from '../test/fixtures'
import type { AnalyzeRequest } from '../types/api'

const REQUEST: AnalyzeRequest = {
  origin: { lat: 39.7392, lon: -104.9903, label: 'Denver, Colorado, US' },
  destination: { lat: 39.0997, lon: -94.5786, label: 'Kansas City, Missouri, US' },
  departure_time: '2026-11-06T15:00:00.000Z',
  load_weight_lb: 42000,
  checkpoint_interval_miles: 25,
}

function respondWith(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(typeof body === 'string' ? body : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': typeof body === 'string' ? 'text/html' : 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('analyzeRoutes', () => {
  it('posts the trip as JSON and returns the analysis', async () => {
    const analysis = makeAnalysis()
    const fetchMock = respondWith(200, analysis)

    await expect(analyzeRoutes(REQUEST)).resolves.toEqual(analysis)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/routes/analyze/')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual(REQUEST)
  })

  it('turns the error envelope into an ApiRequestError', async () => {
    respondWith(502, {
      error: {
        code: 'ROUTING_UNAVAILABLE',
        message: 'The routing service is unavailable.',
        provider: 'valhalla',
      },
    })
    const error = await analyzeRoutes(REQUEST).catch((e) => e)
    expect(error).toBeInstanceOf(ApiRequestError)
    expect(error).toMatchObject({
      status: 502,
      code: 'ROUTING_UNAVAILABLE',
      message: 'The routing service is unavailable.',
      provider: 'valhalla',
    })
  })

  it('reports a server reply that is not the JSON envelope', async () => {
    respondWith(500, '<html>Bad gateway</html>')
    const error = await analyzeRoutes(REQUEST).catch((e) => e)
    expect(error).toMatchObject({ status: 500, code: 'SERVER_ERROR' })
    expect(error.message).toBe('The server returned an unexpected response. Try again in a moment.')
  })

  it('reports a network failure in plain words', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = await analyzeRoutes(REQUEST).catch((e) => e)
    expect(error).toMatchObject({ status: 0, code: 'NETWORK_ERROR' })
    expect(error.message).toBe(
      'Cannot reach the StormRoute server. Check your connection and try again.',
    )
  })

  it('lets a cancelled request reject as an abort, not as a network error', async () => {
    const abort = new DOMException('Aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(analyzeRoutes(REQUEST)).rejects.toBe(abort)
  })
})

describe('searchPlaces', () => {
  it('asks the geocoder and returns its results', async () => {
    const results = [
      {
        name: 'Denver',
        admin1: 'Colorado',
        country_code: 'US',
        lat: 39.74,
        lon: -104.98,
        label: 'Denver, Colorado, US',
      },
    ]
    const fetchMock = respondWith(200, { results })

    await expect(searchPlaces('Den ver')).resolves.toEqual(results)
    expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/api/geocode/?q=Den+ver&limit=5')
  })
})

describe('fieldErrors', () => {
  it('flattens validation details to one message per field', () => {
    const error = new ApiRequestError(400, 'VALIDATION_ERROR', 'Invalid request.', {
      details: {
        departure_time: ['Departure time cannot be more than 1 hour in the past.'],
        origin: { lat: ['Ensure this value is less than or equal to 90.'] },
        destination: ['Origin and destination must be different places.'],
      },
    })
    expect(fieldErrors(error)).toEqual({
      departure_time: 'Departure time cannot be more than 1 hour in the past.',
      origin: 'Ensure this value is less than or equal to 90.',
      destination: 'Origin and destination must be different places.',
    })
  })

  it('is empty for errors without details', () => {
    expect(fieldErrors(new ApiRequestError(502, 'ROUTING_UNAVAILABLE', 'Down'))).toEqual({})
    expect(fieldErrors(new Error('other'))).toEqual({})
  })
})

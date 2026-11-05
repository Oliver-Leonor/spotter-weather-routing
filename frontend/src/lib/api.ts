import type { AnalyzeRequest, AnalyzeResponse, GeocodeResult } from '../types/api'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

/** A failed API call: either the backend's error envelope or a problem reaching it at all. */
export class ApiRequestError extends Error {
  readonly status: number
  readonly code: string
  readonly provider?: string
  readonly details?: unknown

  constructor(
    status: number,
    code: string,
    message: string,
    extra: { provider?: string; details?: unknown } = {},
  ) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.code = code
    this.provider = extra.provider
    this.details = extra.details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, init)
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new ApiRequestError(
      0,
      'NETWORK_ERROR',
      'Cannot reach the StormRoute server. Check your connection and try again.',
    )
  }

  const body: unknown = await response.json().catch(() => null)
  if (response.ok && body !== null) return body as T

  const error = (body as { error?: Record<string, unknown> } | null)?.error
  if (error && typeof error.code === 'string' && typeof error.message === 'string') {
    throw new ApiRequestError(response.status, error.code, error.message, {
      provider: typeof error.provider === 'string' ? error.provider : undefined,
      details: error.details,
    })
  }
  throw new ApiRequestError(
    response.status,
    'SERVER_ERROR',
    'The server returned an unexpected response. Try again in a moment.',
  )
}

export function analyzeRoutes(
  trip: AnalyzeRequest,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>('/api/routes/analyze/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(trip),
    signal,
  })
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<GeocodeResult[]> {
  const params = new URLSearchParams({ q: query, limit: '5' })
  const body = await request<{ results: GeocodeResult[] }>(`/api/geocode/?${params}`, { signal })
  return body.results
}

function firstMessage(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = firstMessage(item)
      if (message) return message
    }
    return null
  }
  if (value && typeof value === 'object') return firstMessage(Object.values(value))
  return null
}

/** One message per request field from a 400 validation error; empty for any other error. */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiRequestError) || !error.details || typeof error.details !== 'object') {
    return {}
  }
  const messages: Record<string, string> = {}
  for (const [field, value] of Object.entries(error.details)) {
    const message = firstMessage(value)
    if (message) messages[field] = message
  }
  return messages
}

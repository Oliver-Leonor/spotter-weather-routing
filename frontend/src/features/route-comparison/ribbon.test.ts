import { describe, expect, it } from 'vitest'
import { ribbonSegments } from './ribbon'
import { makeRoute } from '../../test/fixtures'

describe('ribbonSegments', () => {
  it('gives each checkpoint a width in proportion to the miles it owns', () => {
    const route = makeRoute(1, ['low', 'severe', 'no_travel', 'low'])
    const segments = ribbonSegments(route.checkpoints)

    expect(segments.map((s) => s.level)).toEqual(['low', 'severe', 'no_travel', 'low'])
    // 12.5, 25, 25 and 12.5 of 75 miles
    expect(segments.map((s) => Number(s.widthPercent.toFixed(2)))).toEqual([
      16.67, 33.33, 33.33, 16.67,
    ])
    expect(segments.reduce((sum, s) => sum + s.widthPercent, 0)).toBeCloseTo(100)
    expect(segments.map((s) => s.checkpointId)).toEqual(route.checkpoints.map((c) => c.id))
  })

  it('is empty for a route without checkpoints', () => {
    expect(ribbonSegments([])).toEqual([])
  })
})

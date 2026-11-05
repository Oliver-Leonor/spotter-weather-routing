import { describe, expect, it } from 'vitest'
import { truckPositionAt } from './truck'
import { makeRoute } from '../../test/fixtures'

// Checkpoints at 15:00, 16:00, 17:00 and 18:00 UTC; lon -100, -100.5, -101, -101.5; lat 39 to 39.3.
const route = makeRoute(1, ['low', 'low', 'low', 'low'])
const at = (time: string) => truckPositionAt(route, Date.parse(time))

describe('truckPositionAt', () => {
  it('is at a checkpoint at that checkpoint ETA', () => {
    expect(at('2026-11-06T16:00:00Z')).toMatchObject({ lon: -100.5, lat: 39.1, status: 'driving' })
  })

  it('is between two checkpoints in proportion to the time elapsed between their ETAs', () => {
    const position = at('2026-11-06T16:15:00Z') // a quarter of the way from the second to the third
    expect(position.lon).toBeCloseTo(-100.625)
    expect(position.lat).toBeCloseTo(39.125)
  })

  it('waits at the origin before departure', () => {
    expect(at('2026-11-06T12:00:00Z')).toEqual({ lon: -100, lat: 39, status: 'not_departed' })
  })

  it('stays at the destination after arrival', () => {
    const destination = route.checkpoints[3]
    expect(at('2026-11-07T09:00:00Z')).toEqual({
      lon: destination.lon,
      lat: destination.lat,
      status: 'arrived',
    })
  })
})

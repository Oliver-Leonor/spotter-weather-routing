import { describe, expect, it } from 'vitest'
import { boundsOf, checkpointFeatures, routeFeatures } from './mapData'
import { makeAnalysis } from '../../test/fixtures'

const { routes } = makeAnalysis()

describe('routeFeatures', () => {
  it('has one line per route carrying its selection, status and recommendation', () => {
    const collection = routeFeatures(routes, 'route-2', 'route-2')
    expect(collection.features.map((f) => f.properties)).toEqual([
      { id: 'route-1', name: 'Route A', status: 'blocked', selected: false, recommended: false },
      { id: 'route-2', name: 'Route B', status: 'ok', selected: true, recommended: true },
      { id: 'route-3', name: 'Route C', status: 'unverified', selected: false, recommended: false },
    ])
    expect(collection.features[0].geometry).toEqual(routes[0].geometry)
  })
})

describe('checkpointFeatures', () => {
  it('has a point per checkpoint with its risk level and route', () => {
    const collection = checkpointFeatures(routes, 'route-2', 'route-2-cp-1')
    expect(collection.features).toHaveLength(12)
    const selected = collection.features.find((f) => f.properties.id === 'route-2-cp-1')!
    expect(selected.properties).toEqual({
      id: 'route-2-cp-1',
      route_id: 'route-2',
      level: 'moderate',
      kind: 'checkpoint',
      on_selected_route: true,
      selected: true,
    })
    expect(selected.geometry).toEqual({ type: 'Point', coordinates: [-100.5, 39.1] })
  })

  it('marks checkpoints of other routes so they can be drawn smaller', () => {
    const collection = checkpointFeatures(routes, 'route-2', null)
    const other = collection.features.find((f) => f.properties.id === 'route-1-cp-2')!
    expect(other.properties).toMatchObject({
      level: 'no_travel',
      on_selected_route: false,
      selected: false,
    })
  })
})

describe('boundsOf', () => {
  it('covers every route as [[west, south], [east, north]]', () => {
    const [[west, south], [east, north]] = boundsOf(routes)!
    expect(west).toBe(-101.5)
    expect(east).toBe(-100)
    expect(south).toBeCloseTo(39.2)
    expect(north).toBeCloseTo(39.9)
  })

  it('is null without routes', () => {
    expect(boundsOf([])).toBeNull()
  })
})

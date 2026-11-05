import { describe, expect, it } from 'vitest'
import { UNKNOWN_RISK, heatmapFeatures, riskFillColor, riskFillOpacity } from './heatmapData'
import { RISK_COLORS } from '../../lib/risk'
import type { Heatmap } from '../../types/api'

const heatmap: Heatmap = {
  base_time: '2026-11-06T15:00:00Z',
  hours: ['2026-11-06T15:00:00Z', '2026-11-06T16:00:00Z', '2026-11-06T17:00:00Z'],
  cell_size_miles: 23.08,
  lat_step: 0.4,
  lon_step: 0.5,
  cells: [
    {
      lat: 39,
      lon: -100,
      risk: [0, 3, null],
      wind: [5, 47, null],
      rain: [0, 0, null],
      snow: [0, 0, null],
    },
    { lat: 39.4, lon: -100, risk: [1, 4, 2], wind: [26, 60, 36], rain: [0, 0, 0], snow: [0, 0, 0] },
  ],
}

describe('heatmapFeatures', () => {
  it('draws each cell as a rectangle of one step around its centre', () => {
    const [cell] = heatmapFeatures(heatmap).features
    expect(cell.geometry).toEqual({
      type: 'Polygon',
      coordinates: [
        [
          [-100.25, 38.8],
          [-99.75, 38.8],
          [-99.75, 39.2],
          [-100.25, 39.2],
          [-100.25, 38.8],
        ],
      ],
    })
  })

  it('carries one risk value per forecast hour, so the slider only changes paint', () => {
    const [first, second] = heatmapFeatures(heatmap).features
    expect(first.properties).toEqual({ r_0: 0, r_1: 3, r_2: UNKNOWN_RISK })
    expect(second.properties).toEqual({ r_0: 1, r_1: 4, r_2: 2 })
  })

  it('tiles neighbouring cells without a gap', () => {
    const [south, north] = heatmapFeatures(heatmap).features
    const topOfSouth = south.geometry.coordinates[0][2][1]
    const bottomOfNorth = north.geometry.coordinates[0][0][1]
    expect(topOfSouth).toBeCloseTo(bottomOfNorth)
  })

  it('is empty when the heatmap has no cells', () => {
    expect(heatmapFeatures({ ...heatmap, cells: [] }).features).toEqual([])
  })
})

describe('riskFillColor', () => {
  it('reads the risk of the chosen hour and maps it to the shared risk colors', () => {
    expect(riskFillColor(7)).toEqual([
      'match',
      ['get', 'r_7'],
      0,
      RISK_COLORS.low,
      1,
      RISK_COLORS.moderate,
      2,
      RISK_COLORS.high,
      3,
      RISK_COLORS.severe,
      4,
      RISK_COLORS.no_travel,
      RISK_COLORS.unknown, // no forecast: never drawn as low
    ])
  })
})

describe('riskFillOpacity', () => {
  it('keeps calm cells faint so that weather stands out, and unknown cells visible', () => {
    expect(riskFillOpacity(7)).toEqual(['match', ['get', 'r_7'], 0, 0.14, UNKNOWN_RISK, 0.35, 0.5])
  })
})

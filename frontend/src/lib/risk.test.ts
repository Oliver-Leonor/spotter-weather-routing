import { describe, expect, it } from 'vitest'
import { RISK_COLORS, riskLabel, riskColor, riskValue } from './risk'

describe('risk presentation helpers', () => {
  it('maps every level to a consistent color and label', () => {
    expect(riskLabel('low')).toBe('Low')
    expect(riskLabel('no_travel')).toBe('No Travel')
    expect(riskLabel('unknown')).toBe('Unknown')
    expect(riskColor('severe')).toBe(RISK_COLORS.severe)
    expect(riskColor('unknown')).toBe(RISK_COLORS.unknown)
  })

  it('exposes the numeric severity order used by the backend', () => {
    expect(riskValue('low')).toBe(0)
    expect(riskValue('moderate')).toBe(1)
    expect(riskValue('high')).toBe(2)
    expect(riskValue('severe')).toBe(3)
    expect(riskValue('no_travel')).toBe(4)
    expect(riskValue('unknown')).toBeNull()
  })
})

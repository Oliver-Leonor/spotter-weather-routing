import { describe, expect, it } from 'vitest'
import {
  datetimeLocalToIso,
  formatClock,
  formatDuration,
  formatLocalTime,
  formatMeasurement,
  formatMiles,
  formatWeight,
  toDatetimeLocalValue,
} from './format'
import { RAIN_THRESHOLDS, SNOW_THRESHOLDS, WIND_THRESHOLDS } from './risk'

describe('distance, duration and weight', () => {
  it('formats miles with a chosen precision', () => {
    expect(formatMiles(604.07)).toBe('604 mi')
    expect(formatMiles(12.5, 1)).toBe('12.5 mi')
    expect(formatMiles(1234.4)).toBe('1,234 mi')
  })

  it('formats a duration as hours and minutes', () => {
    expect(formatDuration(31608)).toBe('8 h 47 min')
    expect(formatDuration(7200)).toBe('2 h')
    expect(formatDuration(2700)).toBe('45 min')
    expect(formatDuration(3570)).toBe('1 h') // 59.5 minutes rounds up into the hour
  })

  it('formats a load weight', () => {
    expect(formatWeight(42000)).toBe('42,000 lb')
  })
})

describe('local time at a checkpoint', () => {
  it('shows the time in the checkpoint zone with its abbreviation', () => {
    expect(formatLocalTime('2026-11-06T15:00:00Z', 'America/Denver')).toBe(
      'Fri, Nov 6, 8:00 AM MST',
    )
    expect(formatClock('2026-11-07T00:46:00Z', 'America/Chicago')).toBe('6:46 PM CST')
  })

  it('is right on both sides of the end of daylight saving time', () => {
    expect(formatClock('2026-11-01T07:30:00Z', 'America/Denver')).toBe('1:30 AM MDT')
    expect(formatClock('2026-11-01T08:30:00Z', 'America/Denver')).toBe('1:30 AM MST')
  })

  it('falls back to UTC when the zone is missing or unknown', () => {
    expect(formatClock('2026-11-06T15:00:00Z', null)).toBe('3:00 PM UTC')
    expect(formatClock('2026-11-06T15:00:00Z', 'Not/AZone')).toBe('3:00 PM UTC')
  })
})

describe('measurements never contradict their risk band', () => {
  it('uses the default precision when rounding stays in the same band', () => {
    expect(formatMeasurement(58, 1, WIND_THRESHOLDS)).toBe('58.0')
    expect(formatMeasurement(1.2, 2, RAIN_THRESHOLDS)).toBe('1.20')
    expect(formatMeasurement(0, 2, SNOW_THRESHOLDS)).toBe('0.00')
  })

  it('adds decimals when rounding would cross a threshold', () => {
    expect(formatMeasurement(1.000394, 2, RAIN_THRESHOLDS)).toBe('1.0004') // above 1.00: No Travel
    expect(formatMeasurement(3.003937, 2, SNOW_THRESHOLDS)).toBe('3.004')
    expect(formatMeasurement(54.9913, 1, WIND_THRESHOLDS)).toBe('54.99') // below 55: Severe
    expect(formatMeasurement(24.96, 1, WIND_THRESHOLDS)).toBe('24.96')
  })

  it('keeps a value that sits exactly on a threshold', () => {
    expect(formatMeasurement(1, 2, RAIN_THRESHOLDS)).toBe('1.00')
    expect(formatMeasurement(55, 1, WIND_THRESHOLDS)).toBe('55.0')
  })
})

describe('departure input', () => {
  it('round-trips a moment through the datetime-local value', () => {
    const moment = new Date('2026-11-06T15:20:00Z')
    const value = toDatetimeLocalValue(moment)
    expect(value).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(datetimeLocalToIso(value)).toBe('2026-11-06T15:20:00.000Z')
  })

  it('returns null for an empty or invalid value', () => {
    expect(datetimeLocalToIso('')).toBeNull()
    expect(datetimeLocalToIso('not a date')).toBeNull()
  })
})

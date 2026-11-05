import type { RiskLevelOrUnknown } from '../types/api'

/** Consistent risk colors across map, cards and legend (spec section 10.1). */
export const RISK_COLORS: Record<RiskLevelOrUnknown, string> = {
  low: '#22c55e',
  moderate: '#eab308',
  high: '#f97316',
  severe: '#dc2626',
  no_travel: '#7f1d1d',
  unknown: '#94a3b8',
}

const LABELS: Record<RiskLevelOrUnknown, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
  no_travel: 'No Travel',
  unknown: 'Unknown',
}

const VALUES: Record<RiskLevelOrUnknown, number | null> = {
  low: 0,
  moderate: 1,
  high: 2,
  severe: 3,
  no_travel: 4,
  unknown: null,
}

export const RISK_ORDER: RiskLevelOrUnknown[] = [
  'low',
  'moderate',
  'high',
  'severe',
  'no_travel',
  'unknown',
]

export function riskLabel(level: RiskLevelOrUnknown): string {
  return LABELS[level]
}

export function riskColor(level: RiskLevelOrUnknown): string {
  return RISK_COLORS[level]
}

export function riskValue(level: RiskLevelOrUnknown): number | null {
  return VALUES[level]
}

/** Band boundaries of the risk rules, used to format measurements without crossing a band. */
export const WIND_THRESHOLDS = [25, 35, 45, 55]
export const RAIN_THRESHOLDS = [0.1, 0.25, 0.5, 1]
export const SNOW_THRESHOLDS = [0.5, 1, 2, 3]

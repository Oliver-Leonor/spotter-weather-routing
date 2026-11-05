import { riskColor, riskLabel } from '../lib/risk'
import type { RiskLevelOrUnknown } from '../types/api'

/** Risk level as a colored dot and its name. The name carries the meaning; color only supports it. */
export function RiskBadge({
  level,
  size = 'md',
}: {
  level: RiskLevelOrUnknown
  size?: 'sm' | 'md'
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium text-ink ${
        size === 'sm' ? 'text-xs' : 'text-sm'
      }`}
    >
      <span
        aria-hidden="true"
        className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-black/10"
        style={{ backgroundColor: riskColor(level) }}
      />
      {riskLabel(level)}
    </span>
  )
}

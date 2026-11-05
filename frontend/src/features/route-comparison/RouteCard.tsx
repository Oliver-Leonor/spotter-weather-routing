import { Ban, CircleCheck, CircleHelp } from 'lucide-react'
import { formatClock, formatDuration, formatMiles } from '../../lib/format'
import { riskColor, riskLabel } from '../../lib/risk'
import type { RiskLevelOrUnknown, RouteAnalysis } from '../../types/api'
import { RiskRibbon } from './RiskRibbon'

interface Props {
  route: RouteAnalysis
  isSelected: boolean
  isRecommended: boolean
  selectedCheckpointId: string | null
  onSelect: (routeId: string) => void
  onSelectCheckpoint: (routeId: string, checkpointId: string) => void
}

function milesByLevel(route: RouteAnalysis): [RiskLevelOrUnknown, number][] {
  const { summary } = route
  const rows: [RiskLevelOrUnknown, number][] = [
    ['no_travel', summary.no_travel_miles],
    ['severe', summary.severe_miles],
    ['high', summary.high_miles],
    ['moderate', summary.moderate_miles],
    ['low', summary.low_miles],
    ['unknown', summary.unknown_miles],
  ]
  return rows.filter(([, miles]) => miles > 0)
}

export function RouteCard({
  route,
  isSelected,
  isRecommended,
  selectedCheckpointId,
  onSelect,
  onSelectCheckpoint,
}: Props) {
  const destination = route.checkpoints[route.checkpoints.length - 1]
  return (
    <article
      className={`relative rounded-lg border bg-white p-4 transition-colors ${
        isSelected ? 'border-signal shadow-[inset_4px_0_0_var(--color-signal)]' : 'border-slate-300'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-2xl leading-none font-semibold tracking-wide text-ink">
          {/* The button stretches over the whole card, so anywhere on it selects the route. */}
          <button
            type="button"
            aria-pressed={isSelected}
            onClick={() => onSelect(route.id)}
            className="cursor-pointer rounded-sm after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-signal"
          >
            {route.name}
          </button>
        </h3>
        <div className="flex flex-wrap justify-end gap-1.5">
          {isRecommended && (
            <span className="inline-flex items-center gap-1 rounded-sm bg-signal px-2 py-0.5 text-xs font-semibold text-white">
              <CircleCheck className="h-3.5 w-3.5" aria-hidden="true" />
              Recommended
            </span>
          )}
          {route.status === 'blocked' && (
            <span className="inline-flex items-center gap-1 rounded-sm bg-risk-no-travel px-2 py-0.5 text-xs font-semibold text-white">
              <Ban className="h-3.5 w-3.5" aria-hidden="true" />
              Blocked
            </span>
          )}
          {route.status === 'unverified' && (
            <span className="inline-flex items-center gap-1 rounded-sm bg-slate-600 px-2 py-0.5 text-xs font-semibold text-white">
              <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
              Unverified
            </span>
          )}
        </div>
      </div>

      <p className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-sm text-slate-600">
        <span className="font-display text-xl font-semibold text-ink">
          {formatDuration(route.duration_seconds)}
        </span>
        <span>{formatMiles(route.distance_miles)}</span>
        <span>Arrives {formatClock(route.arrival_time, destination?.timezone ?? null)}</span>
      </p>

      {route.status === 'blocked' && (
        <p className="mt-2 text-sm font-medium text-risk-no-travel">
          No Travel conditions on {route.summary.no_travel_miles.toFixed(1)} miles. Not recommended.
        </p>
      )}
      {route.status === 'unverified' && (
        <p className="mt-2 text-sm font-medium text-slate-700">
          No usable forecast for {route.summary.unknown_miles.toFixed(1)} miles. Not treated as
          safe.
        </p>
      )}

      <div className="relative z-10 mt-3">
        <RiskRibbon
          route={route}
          selectedCheckpointId={selectedCheckpointId}
          onSelectCheckpoint={onSelectCheckpoint}
        />
      </div>

      <ul aria-label="Miles by risk level" className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {milesByLevel(route).map(([level, miles]) => (
          <li key={level} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="h-2.5 w-2.5 rounded-full ring-1 ring-black/10"
              style={{ backgroundColor: riskColor(level) }}
            />
            <span className="mr-1 text-slate-600">{riskLabel(level)}</span>
            <span className="font-medium text-ink tabular-nums">{miles.toFixed(1)} mi</span>
          </li>
        ))}
      </ul>
    </article>
  )
}

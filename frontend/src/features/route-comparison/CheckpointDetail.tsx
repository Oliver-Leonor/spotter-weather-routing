import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { RiskBadge } from '../../components/RiskBadge'
import { formatClock, formatLocalTime, formatMeasurement } from '../../lib/format'
import { RAIN_THRESHOLDS, SNOW_THRESHOLDS, WIND_THRESHOLDS } from '../../lib/risk'
import type { Checkpoint, RiskLevel, RouteAnalysis } from '../../types/api'

interface Props {
  route: RouteAnalysis
  checkpoint: Checkpoint
  onPrevious: () => void
  onNext: () => void
  onClose: () => void
}

const LOAD_RULE_NOTES: Record<string, string> = {
  load_rule_2: 'Wind of 45 to 55 mph is No Travel with a load over 30,000 lb.',
  load_rule_3: 'Wind of 35 to 45 mph is Severe with a load over 40,000 lb.',
}

function place(checkpoint: Checkpoint): string {
  if (checkpoint.kind === 'origin') return 'origin'
  if (checkpoint.kind === 'destination') return 'destination'
  return `mile ${Math.round(checkpoint.distance_miles)}`
}

function MeasurementRow({
  label,
  value,
  unit,
  decimals,
  thresholds,
  level,
}: {
  label: string
  value: number | null
  unit: string
  decimals: number
  thresholds: number[]
  level: RiskLevel | null
}) {
  return (
    <tr className="border-t border-slate-200">
      <th scope="row" className="py-1.5 pr-3 text-left font-normal text-slate-600">
        {label}
      </th>
      <td className="py-1.5 pr-3 font-medium text-ink tabular-nums">
        {value === null
          ? 'Not available'
          : `${formatMeasurement(value, decimals, thresholds)} ${unit}`}
      </td>
      <td className="py-1.5 text-right">
        <RiskBadge level={level ?? 'unknown'} size="sm" />
      </td>
    </tr>
  )
}

export function CheckpointDetail({ route, checkpoint, onPrevious, onNext, onClose }: Props) {
  const { weather, risk } = checkpoint
  const isFirst = checkpoint.index === 0
  const isLast = checkpoint.index === route.checkpoints.length - 1
  const loadRuleNote = risk.load_rule_applied ? LOAD_RULE_NOTES[risk.load_rule_applied] : undefined

  return (
    <section
      aria-label="Checkpoint details"
      className="rounded-lg border border-slate-300 bg-white p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-display text-xl leading-tight font-semibold tracking-wide text-ink">
            {route.name}, {place(checkpoint)}
          </h3>
          <p className="mt-0.5 text-sm text-slate-600">
            Arrives{' '}
            <span className="font-medium text-ink">
              {formatLocalTime(checkpoint.eta, checkpoint.timezone)}
            </span>
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            aria-label="Previous checkpoint"
            disabled={isFirst}
            onClick={onPrevious}
            className="icon-button"
          >
            <ChevronLeft className="h-5 w-5" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="Next checkpoint"
            disabled={isLast}
            onClick={onNext}
            className="icon-button"
          >
            <ChevronRight className="h-5 w-5" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="Close checkpoint details"
            onClick={onClose}
            className="icon-button"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 rounded-sm bg-slate-100 px-3 py-2">
        <span className="text-sm text-slate-600">Risk at estimated arrival</span>
        <RiskBadge level={risk.level} />
      </div>

      {weather === null ? (
        <p className="mt-3 text-sm leading-relaxed text-ink">
          No usable forecast for this arrival time, so this checkpoint is not treated as safe.
        </p>
      ) : (
        <>
          <table className="mt-3 w-full text-sm">
            <tbody>
              <MeasurementRow
                label="Wind"
                value={weather.wind_mph}
                unit="mph"
                decimals={1}
                thresholds={WIND_THRESHOLDS}
                level={risk.wind_level}
              />
              <MeasurementRow
                label="Rain"
                value={weather.rain_in_per_hr}
                unit="in/h"
                decimals={2}
                thresholds={RAIN_THRESHOLDS}
                level={risk.rain_level}
              />
              <MeasurementRow
                label="Snow"
                value={weather.snow_in_per_hr}
                unit="in/h"
                decimals={2}
                thresholds={SNOW_THRESHOLDS}
                level={risk.snow_level}
              />
            </tbody>
          </table>
          {loadRuleNote && <p className="mt-2 text-sm font-medium text-ink">{loadRuleNote}</p>}
          <p className="mt-2 text-xs leading-relaxed text-slate-500">
            {[
              weather.wind_gust_mph !== null && `Gusts ${weather.wind_gust_mph.toFixed(1)} mph`,
              weather.temperature_f !== null && `${Math.round(weather.temperature_f)} °F`,
            ]
              .filter(Boolean)
              .join(', ')}
            {'. '}
            Forecast for {formatClock(weather.forecast_time, checkpoint.timezone)}, the hour nearest
            the arrival.
          </p>
        </>
      )}

      <p className="mt-2 text-xs text-slate-500">
        Stands for {checkpoint.attributed_miles.toFixed(1)} miles of this route.
      </p>
    </section>
  )
}

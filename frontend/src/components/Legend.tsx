import { RISK_ORDER, riskColor, riskLabel } from '../lib/risk'

/** One legend for the map, the ribbons and the cards: the colors mean the same thing everywhere. */
export function Legend() {
  return (
    <div>
      <ul
        aria-label="Risk levels"
        className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-700"
      >
        {RISK_ORDER.map((level) => (
          <li key={level} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className={`h-3 w-3 rounded-full ring-1 ring-black/10 ${
                level === 'unknown' ? 'ribbon-unknown' : ''
              }`}
              style={level === 'unknown' ? undefined : { backgroundColor: riskColor(level) }}
            />
            {riskLabel(level)}
          </li>
        ))}
      </ul>
      <p className="mt-1.5 text-xs leading-relaxed text-slate-500">
        Colors show the risk at each checkpoint when the truck is expected to arrive there. Unknown
        means no usable forecast, and is never treated as safe.
      </p>
    </div>
  )
}

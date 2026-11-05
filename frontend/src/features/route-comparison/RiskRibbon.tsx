import { riskColor, riskLabel } from '../../lib/risk'
import type { RouteAnalysis } from '../../types/api'
import { ribbonSegments } from './ribbon'

interface Props {
  route: RouteAnalysis
  selectedCheckpointId: string | null
  onSelectCheckpoint: (routeId: string, checkpointId: string) => void
}

/**
 * The route drawn as a strip map: origin on the left, destination on the right, each stretch in
 * the color of the risk at its checkpoint. Segments are pointer targets; keyboard users step
 * through checkpoints with the Previous and Next buttons in the detail panel.
 */
export function RiskRibbon({ route, selectedCheckpointId, onSelectCheckpoint }: Props) {
  return (
    <div>
      <div
        role="group"
        aria-label={`Risk along ${route.name}, from origin to destination`}
        className="flex h-5 w-full overflow-hidden rounded-sm bg-slate-200"
      >
        {ribbonSegments(route.checkpoints).map((segment) => {
          const selected = segment.checkpointId === selectedCheckpointId
          return (
            <button
              key={segment.checkpointId}
              type="button"
              tabIndex={-1}
              aria-label={`Mile ${Math.round(segment.distanceMiles)}, ${riskLabel(segment.level)}`}
              title={`Mile ${Math.round(segment.distanceMiles)}: ${riskLabel(segment.level)}`}
              onClick={() => onSelectCheckpoint(route.id, segment.checkpointId)}
              className={`h-full min-w-0 cursor-pointer border-r border-white/50 last:border-r-0 ${
                segment.level === 'unknown' ? 'ribbon-unknown' : ''
              } ${selected ? 'relative z-10 outline-2 -outline-offset-2 outline-ink' : ''}`}
              style={{
                width: `${segment.widthPercent}%`,
                backgroundColor: segment.level === 'unknown' ? undefined : riskColor(segment.level),
              }}
            />
          )
        })}
      </div>
      <div className="mt-1 flex justify-between text-xs text-slate-500" aria-hidden="true">
        <span>Mile 0</span>
        <span>Mile {Math.round(route.distance_miles)}</span>
      </div>
    </div>
  )
}

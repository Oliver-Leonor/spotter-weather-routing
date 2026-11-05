import { useId, useRef, useState, type KeyboardEvent } from 'react'
import { riskColor, riskLabel } from '../../lib/risk'
import type { RouteAnalysis } from '../../types/api'
import { ribbonSegments, type RibbonSegment } from './ribbon'

interface Props {
  route: RouteAnalysis
  selectedCheckpointId: string | null
  onSelectCheckpoint: (routeId: string, checkpointId: string) => void
}

function placeName(segment: RibbonSegment): string {
  if (segment.kind === 'origin') return 'Origin'
  if (segment.kind === 'destination') return 'Destination'
  return `Mile ${Math.round(segment.distanceMiles)}`
}

/**
 * The route drawn as a strip map: origin on the left, destination on the right, each stretch in
 * the color of the risk at its checkpoint. Every stretch opens that checkpoint's details.
 *
 * Keyboard: the ribbon is a single tab stop (a route can have 60 checkpoints). Inside it the
 * arrow, Home and End keys move between checkpoints, and Enter or Space opens the focused one.
 */
export function RiskRibbon({ route, selectedCheckpointId, onSelectCheckpoint }: Props) {
  const hintId = useId()
  const buttons = useRef<(HTMLButtonElement | null)[]>([])
  // The checkpoint reached with the keyboard, while focus is inside the ribbon.
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null)

  const segments = ribbonSegments(route.checkpoints)
  const selectedIndex = segments.findIndex((s) => s.checkpointId === selectedCheckpointId)
  // Entering the ribbon lands on the selected checkpoint, or on the origin if none is selected.
  const tabStop = focusedIndex ?? (selectedIndex >= 0 ? selectedIndex : 0)

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const last = segments.length - 1
    const target = {
      ArrowRight: Math.min(tabStop + 1, last),
      ArrowDown: Math.min(tabStop + 1, last),
      ArrowLeft: Math.max(tabStop - 1, 0),
      ArrowUp: Math.max(tabStop - 1, 0),
      Home: 0,
      End: last,
    }[event.key]
    if (target === undefined) return
    event.preventDefault()
    setFocusedIndex(target)
    buttons.current[target]?.focus()
  }

  return (
    <div>
      <div
        role="group"
        aria-label={`Risk along ${route.name}, from origin to destination`}
        aria-describedby={hintId}
        onKeyDown={onKeyDown}
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setFocusedIndex(null)
        }}
        className="flex h-5 w-full rounded-sm bg-slate-200"
      >
        {segments.map((segment, index) => {
          const selected = index === selectedIndex
          const label = `${placeName(segment)}, ${riskLabel(segment.level)}`
          return (
            <button
              key={segment.checkpointId}
              ref={(element) => {
                buttons.current[index] = element
              }}
              type="button"
              tabIndex={index === tabStop ? 0 : -1}
              aria-label={label}
              aria-pressed={selected}
              title={label}
              onFocus={() => setFocusedIndex(index)}
              onClick={() => onSelectCheckpoint(route.id, segment.checkpointId)}
              className={`h-full min-w-0 cursor-pointer border-r border-white/50 first:rounded-l-sm last:rounded-r-sm last:border-r-0 focus-visible:relative focus-visible:z-20 focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-ink ${
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
      <p id={hintId} className="sr-only">
        Use the arrow keys to move between checkpoints and Enter to open one.
      </p>
      <div className="mt-1 flex justify-between text-xs text-slate-500" aria-hidden="true">
        <span>Mile 0</span>
        <span>Mile {Math.round(route.distance_miles)}</span>
      </div>
    </div>
  )
}

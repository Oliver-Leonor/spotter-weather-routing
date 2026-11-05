import { useEffect, useId, useRef, useState } from 'react'
import { formatDayHour, formatLocalTime, formatSinceDeparture } from '../../lib/format'
import type { HourStore } from './hourStore'

interface Props {
  store: HourStore
  /** One ISO timestamp per forecast hour, starting at the top of the departure hour. */
  hours: string[]
  /** The actual departure time. It is usually not on the hour, so offsets are measured from it. */
  departure: string
  /** Zone used to show the time, normally the trip origin's. */
  timeZone: string | null
}

/**
 * Time control for the corridor forecast. The thumb and the label follow the pointer at once;
 * the map is told at most once per animation frame, through the store, so dragging stays smooth
 * and nothing else on the page re-renders.
 */
export function ForecastSlider({ store, hours, departure, timeZone }: Props) {
  const id = useId()
  const [hour, setHour] = useState(() => store.get())
  const pending = useRef<number | null>(null)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  function change(next: number) {
    setHour(next)
    const frameAlreadyScheduled = pending.current !== null
    pending.current = next
    if (frameAlreadyScheduled) return
    const schedule =
      globalThis.requestAnimationFrame ??
      ((callback: FrameRequestCallback) => setTimeout(callback, 16))
    schedule(() => {
      const latest = pending.current
      pending.current = null
      if (mounted.current && latest !== null) store.set(latest)
    })
  }

  const last = hours.length - 1
  const iso = hours[Math.min(hour, last)]
  const localTime = formatLocalTime(iso, timeZone)
  const sinceDeparture = formatSinceDeparture(iso, departure)

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <label htmlFor={id} className="text-sm font-medium text-ink">
          Corridor forecast time
        </label>
        <span className="text-xs text-slate-500">{sinceDeparture}</span>
      </div>
      <p className="font-display text-xl leading-tight font-semibold text-ink">
        <time dateTime={iso} title={`${iso} (UTC)`}>
          {localTime}
        </time>
      </p>
      <input
        id={id}
        type="range"
        min={0}
        max={last}
        step={1}
        value={hour}
        onChange={(event) => change(Number(event.target.value))}
        aria-valuetext={`${localTime}, ${sinceDeparture.replace('At departure', 'at departure')}`}
        className="forecast-slider mt-2 w-full"
      />
      {/* Clock times, not offsets: the left end is the top of the departure hour, which is
          usually a little before the departure itself. */}
      <div
        data-testid="forecast-slider-ticks"
        className="flex justify-between text-xs text-slate-500"
        aria-hidden="true"
      >
        <span>{formatDayHour(hours[0], timeZone)}</span>
        <span>{formatDayHour(hours[Math.floor(last / 2)], timeZone)}</span>
        <span>{formatDayHour(hours[last], timeZone)}</span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-slate-500">
        Shading shows the forecast risk across the corridor at this time, for this load. Checkpoints
        keep showing the risk at their own arrival time. The dark marker is where the truck would be
        on the selected route.
      </p>
    </div>
  )
}

import { FlaskConical, Route } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { datetimeLocalToIso, toDatetimeLocalValue } from '../../lib/format'
import type { AnalysisMode, AnalyzeRequest, CheckpointInterval, LatLon } from '../../types/api'
import type { TripFormField } from './fields'
import { PlaceInput } from './PlaceInput'

export type TripFormValues = AnalyzeRequest & { mode: AnalysisMode }

interface Props {
  onSubmit: (values: TripFormValues) => void
  isLoading: boolean
  /** Field messages from a 400 response, keyed by request field. */
  serverErrors: Record<string, string>
  /** The current time. Injectable so validation can be tested. */
  now?: Date
}

const INTERVALS: CheckpointInterval[] = [10, 25, 50]
const MAX_LOAD_LB = 200_000
const HOUR_MS = 3_600_000
const DEMO_ORIGIN: LatLon = { lat: 39.7392, lon: -104.9903, label: 'Denver, Colorado, US' }
const DEMO_DESTINATION: LatLon = { lat: 39.0997, lon: -94.5786, label: 'Kansas City, Missouri, US' }
const DEMO_LOAD_LB = 42_000

/** One hour from now, rounded up to the hour. */
function defaultDeparture(now: Date): Date {
  return new Date(Math.ceil((now.getTime() + HOUR_MS) / HOUR_MS) * HOUR_MS)
}

/** The next 15:00 UTC (8:00 AM in Denver in winter), when the demo storm lies ahead of the truck. */
function nextDemoDeparture(now: Date): Date {
  const departure = new Date(now)
  departure.setUTCHours(15, 0, 0, 0)
  if (departure <= now) departure.setUTCDate(departure.getUTCDate() + 1)
  return departure
}

/** The browser's UTC offset, for example "GMT+8" or "GMT-5:30". */
function localOffsetLabel(): string {
  const minutes = -new Date().getTimezoneOffset()
  const hours = Math.floor(Math.abs(minutes) / 60)
  const rest = Math.abs(minutes) % 60
  return `GMT${minutes >= 0 ? '+' : '-'}${hours}${rest ? `:${String(rest).padStart(2, '0')}` : ''}`
}

type Errors = Partial<Record<TripFormField, string>>

export function TripForm({ onSubmit, isLoading, serverErrors, now }: Props) {
  const ids = { departure: useId(), load: useId() }
  const [origin, setOrigin] = useState<LatLon | null>(null)
  const [destination, setDestination] = useState<LatLon | null>(null)
  const [departure, setDeparture] = useState(() =>
    toDatetimeLocalValue(defaultDeparture(now ?? new Date())),
  )
  const [load, setLoad] = useState(String(DEMO_LOAD_LB))
  const [interval, setInterval] = useState<CheckpointInterval>(25)
  const [isDemo, setIsDemo] = useState(false)
  const [errors, setErrors] = useState<Errors>({})
  const [offsetLabel] = useState(localOffsetLabel)

  function validate(): { errors: Errors; departureIso: string | null; loadLb: number } {
    const found: Errors = {}
    const current = now ?? new Date()
    if (!origin) found.origin = 'Choose where the trip starts.'
    if (!destination) found.destination = 'Choose where the trip ends.'

    const departureIso = datetimeLocalToIso(departure)
    if (!departureIso) {
      found.departure_time = 'Choose a departure date and time.'
    } else {
      const ahead = new Date(departureIso).getTime() - current.getTime()
      if (ahead < -HOUR_MS) {
        found.departure_time = 'Departure cannot be more than 1 hour in the past.'
      } else if (ahead > 14 * 24 * HOUR_MS) {
        found.departure_time = 'Choose a departure within the next 14 days.'
      }
    }

    const loadLb = Number(load)
    if (load.trim() === '' || Number.isNaN(loadLb)) {
      found.load_weight_lb = 'Enter the load weight in pounds.'
    } else if (!Number.isInteger(loadLb)) {
      found.load_weight_lb = 'Load weight must be a whole number of pounds.'
    } else if (loadLb < 0 || loadLb > MAX_LOAD_LB) {
      found.load_weight_lb = 'Load weight must be between 0 and 200,000 lb.'
    }
    return { errors: found, departureIso, loadLb }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const result = validate()
    setErrors(result.errors)
    if (Object.keys(result.errors).length > 0 || !origin || !destination || !result.departureIso) {
      return
    }
    onSubmit({
      origin,
      destination,
      departure_time: result.departureIso,
      load_weight_lb: result.loadLb,
      checkpoint_interval_miles: interval,
      mode: isDemo ? 'fixture' : 'live',
    })
  }

  function runDemo() {
    const demoDeparture = nextDemoDeparture(now ?? new Date())
    setOrigin(DEMO_ORIGIN)
    setDestination(DEMO_DESTINATION)
    setDeparture(toDatetimeLocalValue(demoDeparture))
    setLoad(String(DEMO_LOAD_LB))
    setInterval(25)
    setIsDemo(true)
    setErrors({})
    onSubmit({
      origin: DEMO_ORIGIN,
      destination: DEMO_DESTINATION,
      departure_time: demoDeparture.toISOString(),
      load_weight_lb: DEMO_LOAD_LB,
      checkpoint_interval_miles: 25,
      mode: 'fixture',
    })
  }

  // A demo trip only makes sense for the recorded places, so changing either one leaves it.
  function changePlace(setPlace: (place: LatLon | null) => void) {
    return (place: LatLon | null) => {
      setPlace(place)
      setIsDemo(false)
    }
  }

  const message = (field: keyof Errors) => errors[field] ?? serverErrors[field]
  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      <PlaceInput
        label="Origin"
        value={origin}
        onChange={changePlace(setOrigin)}
        error={message('origin')}
        placeholder="City or town"
      />
      <PlaceInput
        label="Destination"
        value={destination}
        onChange={changePlace(setDestination)}
        error={message('destination')}
        placeholder="City or town"
      />

      <div className="grid grid-cols-1 gap-4 min-[460px]:grid-cols-[3fr_2fr]">
        <div>
          <label htmlFor={ids.departure} className="field-label">
            Departure
          </label>
          <input
            id={ids.departure}
            type="datetime-local"
            value={departure}
            onChange={(event) => setDeparture(event.target.value)}
            aria-invalid={message('departure_time') ? true : undefined}
            aria-describedby={`${ids.departure}-hint`}
            className="field-input"
          />
          <p id={`${ids.departure}-hint`} className="field-hint">
            Your local time ({offsetLabel})
          </p>
          {message('departure_time') && <p className="field-error">{message('departure_time')}</p>}
        </div>
        <div>
          <label htmlFor={ids.load} className="field-label">
            Load weight
          </label>
          <div className="relative">
            <input
              id={ids.load}
              type="number"
              inputMode="numeric"
              min={0}
              max={MAX_LOAD_LB}
              step={1}
              value={load}
              onChange={(event) => setLoad(event.target.value)}
              aria-invalid={message('load_weight_lb') ? true : undefined}
              aria-describedby={`${ids.load}-hint`}
              className="field-input pr-9"
            />
            <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm text-slate-500">
              lb
            </span>
          </div>
          <p id={`${ids.load}-hint`} className="field-hint">
            Cargo. Wind limits tighten above 30,000 and 40,000 lb.
          </p>
          {message('load_weight_lb') && <p className="field-error">{message('load_weight_lb')}</p>}
        </div>
      </div>

      <fieldset>
        <legend className="field-label">Check the weather every</legend>
        <div className="grid grid-cols-3 overflow-hidden rounded-md border border-slate-300">
          {INTERVALS.map((miles) => (
            <label
              key={miles}
              className="cursor-pointer border-r border-slate-300 text-center text-sm font-medium last:border-r-0 has-checked:bg-ink has-checked:text-white has-focus-visible:outline-2 has-focus-visible:-outline-offset-2 has-focus-visible:outline-signal"
            >
              <input
                type="radio"
                name="interval"
                value={miles}
                checked={interval === miles}
                onChange={() => setInterval(miles)}
                className="sr-only"
              />
              <span className="block px-2 py-2">{miles} mi</span>
            </label>
          ))}
        </div>
      </fieldset>

      {isDemo && (
        <p className="rounded-md border border-hazard bg-amber-50 px-3 py-2 text-sm text-ink">
          Demo trip with simulated weather. Change the origin or destination to use live data.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={isLoading} className="button-primary flex-1">
          <Route className="h-4 w-4" aria-hidden="true" />
          {isLoading ? 'Comparing routes…' : 'Compare routes'}
        </button>
        <button type="button" disabled={isLoading} onClick={runDemo} className="button-secondary">
          <FlaskConical className="h-4 w-4" aria-hidden="true" />
          Run the demo trip
        </button>
      </div>
    </form>
  )
}

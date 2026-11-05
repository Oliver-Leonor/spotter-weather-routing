/** Display formatting. All functions are pure and locale-fixed (en-US) so output is predictable. */

export function formatMiles(miles: number, decimals = 0): string {
  const text = miles.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
  return `${text} mi`
}

export function formatWeight(pounds: number): string {
  return `${pounds.toLocaleString('en-US')} lb`
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours === 0) return `${minutes} min`
  return minutes === 0 ? `${hours} h` : `${hours} h ${minutes} min`
}

function zonedFormat(iso: string, timeZone: string | null, options: Intl.DateTimeFormatOptions) {
  const format = (zone: string) =>
    new Intl.DateTimeFormat('en-US', { ...options, timeZone: zone, timeZoneName: 'short' })
      .format(new Date(iso))
      .replace(/ /g, ' ') // newer ICU puts a narrow no-break space before AM/PM
  try {
    return format(timeZone ?? 'UTC')
  } catch {
    return format('UTC') // unknown zone name
  }
}

/** Time of day in the given IANA zone, for example "8:00 AM MST". Falls back to UTC. */
export function formatClock(iso: string, timeZone: string | null): string {
  return zonedFormat(iso, timeZone, { hour: 'numeric', minute: '2-digit' })
}

/** Day and time in the given IANA zone, for example "Fri, Nov 6, 8:00 AM MST". */
export function formatLocalTime(iso: string, timeZone: string | null): string {
  return zonedFormat(iso, timeZone, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** Weekday and hour in the given zone, for example "Fri 8 AM". Used for slider tick marks. */
export function formatDayHour(iso: string, timeZone: string | null): string {
  const format = (zone: string) =>
    new Intl.DateTimeFormat('en-US', { weekday: 'short', hour: 'numeric', timeZone: zone })
      .format(new Date(iso))
      .replace(/\u202f/g, ' ')
      .replace(',', '')
  try {
    return format(timeZone ?? 'UTC')
  } catch {
    return format('UTC')
  }
}

/**
 * How a moment relates to the departure, for example "45 min before departure" or
 * "1 h 15 min after departure". The forecast hours start at the top of the departure hour, so
 * the first one is usually before the truck leaves.
 */
export function formatSinceDeparture(iso: string, departureIso: string): string {
  const minutes = Math.round((Date.parse(iso) - Date.parse(departureIso)) / 60_000)
  if (minutes === 0) return 'At departure'
  const direction = minutes > 0 ? 'after' : 'before'
  return `${formatDuration(Math.abs(minutes) * 60)} ${direction} departure`
}

const MAX_DECIMALS = 6

/**
 * Format a measurement with at least `decimals` places, adding places while the rounded number
 * would land on the other side of a risk threshold. 1.000394 in/h of rain is above 1.00 (No
 * Travel), so it is shown as "1.0004" rather than "1.00". Mirrors `risk/formatting.py`.
 */
export function formatMeasurement(value: number, decimals: number, thresholds: number[]): string {
  for (let places = decimals; places < MAX_DECIMALS; places += 1) {
    const rounded = Number(value.toFixed(places))
    const sameBand = thresholds.every(
      (t) => value >= t === rounded >= t && value > t === rounded > t,
    )
    if (sameBand) return value.toFixed(places)
  }
  return value.toFixed(MAX_DECIMALS)
}

const pad = (n: number) => String(n).padStart(2, '0')

/** The value a `datetime-local` input needs to show `date` in the browser's own time zone. */
export function toDatetimeLocalValue(date: Date): string {
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** A `datetime-local` value (browser time zone) as a UTC ISO string, or null if it is not a date. */
export function datetimeLocalToIso(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

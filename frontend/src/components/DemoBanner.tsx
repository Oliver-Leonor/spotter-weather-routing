/**
 * Shown for as long as demo results are on screen. Demo mode replays recorded routes with
 * scripted weather, so it must never be mistaken for a real forecast.
 */
export function DemoBanner() {
  return (
    <div role="note" aria-label="Simulated weather" className="sticky top-0 z-40 shadow-md">
      <div className="hazard-tape h-2" aria-hidden="true" />
      <p className="bg-hazard px-4 py-2 text-center text-sm leading-snug text-ink sm:text-base">
        <strong className="font-display text-lg font-semibold tracking-wide">
          Simulated weather.
        </strong>{' '}
        This is demo data, not a real forecast. The routes are a recorded Denver to Kansas City
        trip.
      </p>
    </div>
  )
}

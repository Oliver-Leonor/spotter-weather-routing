import { CloudSun, Route } from 'lucide-react'

export default function App() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="bg-navy-900 text-white">
        <div className="mx-auto flex max-w-screen-2xl items-center gap-3 px-4 py-3">
          <span className="bg-teal-500 inline-flex h-9 w-9 items-center justify-center rounded-lg">
            <CloudSun className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h1 className="text-lg font-semibold leading-tight">StormRoute</h1>
            <p className="text-xs text-slate-300">Weather-Aware Trip Planning</p>
          </div>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-screen-2xl flex-1 flex-col gap-4 p-4 lg:flex-row">
        <section
          aria-label="Trip planner"
          className="w-full rounded-xl bg-white p-4 shadow-sm lg:w-80 lg:shrink-0"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Trip planner
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Origin, destination, departure time, load weight and checkpoint interval controls arrive
            in PR #3.
          </p>
        </section>
        <section
          aria-label="Route map"
          className="flex min-h-[320px] flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-sm"
        >
          <Route className="h-10 w-10 text-slate-400" aria-hidden="true" />
          <p className="mt-3 text-base font-medium text-slate-700">
            Plan a trip to see routes, checkpoints and the weather corridor.
          </p>
          <p className="mt-1 text-sm text-slate-500">
            Routes come from OpenStreetMap data via Valhalla; forecasts from Open-Meteo.
          </p>
        </section>
      </main>
    </div>
  )
}

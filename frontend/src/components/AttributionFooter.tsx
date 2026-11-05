const DEFAULT_NOTE = 'Routes are standard driving routes, not truck-restricted routes.'

/** Limitations of the analysis and credit to the data providers (required by their terms). */
export function AttributionFooter({ notes }: { notes: string[] }) {
  const link = 'underline decoration-slate-400 underline-offset-2 hover:text-ink'
  return (
    <footer className="text-xs leading-relaxed text-slate-500">
      {(notes.length > 0 ? notes : [DEFAULT_NOTE]).map((note) => (
        <p key={note} className="mb-1">
          {note}
        </p>
      ))}
      <p className="mt-2">
        Routing by Valhalla on the FOSSGIS server, map data ©{' '}
        <a className={link} href="https://www.openstreetmap.org/copyright">
          OpenStreetMap contributors
        </a>{' '}
        (
        <a className={link} href="https://www.openstreetmap.org/fixthemap">
          report a map issue
        </a>
        ). Weather data by{' '}
        <a className={link} href="https://open-meteo.com/">
          Open-Meteo
        </a>{' '}
        (CC BY 4.0). Map tiles by{' '}
        <a className={link} href="https://openfreemap.org/">
          OpenFreeMap
        </a>
        .
      </p>
    </footer>
  )
}

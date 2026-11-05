export interface MapLayers {
  heatmap: boolean
  checkpoints: boolean
  otherRoutes: boolean
}

interface Props {
  layers: MapLayers
  onChange: (layers: MapLayers) => void
  /** False when the corridor forecast could not be loaded. */
  heatmapAvailable: boolean
}

const OPTIONS: [keyof MapLayers, string][] = [
  ['heatmap', 'Weather corridor'],
  ['checkpoints', 'Checkpoints'],
  ['otherRoutes', 'Other routes'],
]

/** What is drawn on the map. */
export function LayerToggles({ layers, onChange, heatmapAvailable }: Props) {
  return (
    <fieldset>
      <legend className="sr-only">Show on the map</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {OPTIONS.map(([key, label]) => {
          const disabled = key === 'heatmap' && !heatmapAvailable
          return (
            <label
              key={key}
              className={`inline-flex items-center gap-1.5 text-sm ${
                disabled ? 'text-slate-400' : 'cursor-pointer text-ink'
              }`}
            >
              <input
                type="checkbox"
                checked={layers[key] && !disabled}
                disabled={disabled}
                onChange={(event) => onChange({ ...layers, [key]: event.target.checked })}
                className="h-4 w-4 accent-signal"
              />
              {label}
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

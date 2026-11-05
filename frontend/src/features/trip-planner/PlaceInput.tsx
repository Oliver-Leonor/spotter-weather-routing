import { useQuery } from '@tanstack/react-query'
import { MapPin } from 'lucide-react'
import { useId, useState, type KeyboardEvent } from 'react'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { searchPlaces } from '../../lib/api'
import type { LatLon } from '../../types/api'

interface Props {
  label: string
  value: LatLon | null
  onChange: (place: LatLon | null) => void
  error?: string
  placeholder?: string
}

const MIN_QUERY_LENGTH = 2

/** City and town search. A place only counts once it is picked from the suggestions. */
export function PlaceInput({ label, value, onChange, error, placeholder }: Props) {
  const id = useId()
  // What the user is typing. Once a place is chosen (or set from outside, as the demo trip does),
  // the field shows that place's label instead.
  const [typed, setTyped] = useState('')
  const text = value?.label ?? typed
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)

  const query = useDebouncedValue(text.trim(), 250)
  const searching = value === null && query.length >= MIN_QUERY_LENGTH
  const places = useQuery({
    queryKey: ['geocode', query],
    queryFn: ({ signal }) => searchPlaces(query, signal),
    enabled: searching,
    staleTime: 5 * 60_000,
  })
  const options = searching && places.data ? places.data : []
  const showList = open && searching && (places.isSuccess || places.isError)

  function choose(index: number) {
    const place = options[index]
    if (!place) return
    onChange({ lat: place.lat, lon: place.lon, label: place.label })
    setOpen(false)
    setActiveIndex(-1)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown' && options.length > 0) {
      event.preventDefault()
      setOpen(true)
      setActiveIndex((index) => (index + 1) % options.length)
    } else if (event.key === 'ArrowUp' && options.length > 0) {
      event.preventDefault()
      setActiveIndex((index) => (index <= 0 ? options.length - 1 : index - 1))
    } else if (event.key === 'Enter' && open && activeIndex >= 0) {
      event.preventDefault() // pick the suggestion instead of submitting the form
      choose(activeIndex)
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="relative">
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <div className="relative">
        <MapPin
          className="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-slate-400"
          aria-hidden="true"
        />
        <input
          id={id}
          type="text"
          role="combobox"
          aria-expanded={showList}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          autoComplete="off"
          placeholder={placeholder}
          value={text}
          onChange={(event) => {
            setTyped(event.target.value)
            setOpen(true)
            setActiveIndex(-1)
            if (value !== null) onChange(null)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          className="field-input pl-8"
        />
      </div>
      {showList && (
        <div
          id={`${id}-list`}
          role="listbox"
          aria-label={`${label} suggestions`}
          className="absolute z-30 mt-1 w-full overflow-hidden rounded-md border border-slate-300 bg-white shadow-lg"
        >
          {options.map((place, index) => (
            <div
              key={`${place.lat},${place.lon}`}
              id={`${id}-option-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              // Keep focus in the input so the click lands before the list closes on blur.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(index)}
              className={`cursor-pointer px-3 py-2 text-sm ${
                index === activeIndex ? 'bg-teal-50 text-ink' : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              {place.label}
            </div>
          ))}
          {places.isSuccess && options.length === 0 && (
            <p className="px-3 py-2 text-sm text-slate-600">No places match "{query}".</p>
          )}
          {places.isError && (
            <p className="px-3 py-2 text-sm text-risk-severe">{places.error.message}</p>
          )}
        </div>
      )}
      {error && (
        <p id={`${id}-error`} className="field-error">
          {error}
        </p>
      )}
    </div>
  )
}

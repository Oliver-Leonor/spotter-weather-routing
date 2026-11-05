/**
 * The forecast hour chosen on the slider, held outside React. The slider writes it and the map
 * subscribes to it directly, so dragging the slider repaints the map without re-rendering the
 * rest of the page.
 */
export interface HourStore {
  get: () => number
  set: (hour: number) => void
  subscribe: (listener: () => void) => () => void
}

export function createHourStore(initial = 0): HourStore {
  let hour = initial
  const listeners = new Set<() => void>()
  return {
    get: () => hour,
    set(next) {
      if (next === hour) return
      hour = next
      listeners.forEach((listener) => listener())
    },
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}

import { describe, expect, it, vi } from 'vitest'
import { createHourStore } from './hourStore'

describe('hour store', () => {
  it('holds the selected forecast hour and notifies subscribers when it changes', () => {
    const store = createHourStore()
    const listener = vi.fn()
    store.subscribe(listener)

    expect(store.get()).toBe(0)
    store.set(12)
    expect(store.get()).toBe(12)
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('does not notify when the hour is unchanged', () => {
    const store = createHourStore(5)
    const listener = vi.fn()
    store.subscribe(listener)
    store.set(5)
    expect(listener).not.toHaveBeenCalled()
  })

  it('stops notifying after unsubscribe', () => {
    const store = createHourStore()
    const listener = vi.fn()
    const unsubscribe = store.subscribe(listener)
    unsubscribe()
    store.set(3)
    expect(listener).not.toHaveBeenCalled()
  })
})

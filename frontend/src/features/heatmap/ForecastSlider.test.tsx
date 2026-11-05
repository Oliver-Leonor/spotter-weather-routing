import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ForecastSlider } from './ForecastSlider'
import { createHourStore } from './hourStore'

const HOURS = Array.from({ length: 49 }, (_, i) =>
  new Date(Date.parse('2026-11-06T15:00:00Z') + i * 3_600_000).toISOString().replace('.000Z', 'Z'),
)

function renderSlider(store = createHourStore()) {
  render(<ForecastSlider store={store} hours={HOURS} timeZone="America/Denver" />)
  return { store, slider: screen.getByRole('slider', { name: 'Corridor forecast time' }) }
}

afterEach(() => vi.unstubAllGlobals())

describe('ForecastSlider', () => {
  it('covers forecast offsets 0 to 48 hours and starts at the departure hour', () => {
    const { slider } = renderSlider()
    expect(slider).toHaveAttribute('min', '0')
    expect(slider).toHaveAttribute('max', '48')
    expect(slider).toHaveValue('0')
    expect(screen.getByText('Fri, Nov 6, 8:00 AM MST')).toBeInTheDocument()
    expect(screen.getByText('At departure')).toBeInTheDocument()
  })

  it('shows the exact local time of the chosen hour, with UTC on hover', () => {
    const { slider } = renderSlider()
    fireEvent.change(slider, { target: { value: '30' } })
    const time = screen.getByText('Sat, Nov 7, 2:00 PM MST')
    expect(time).toHaveAttribute('title', '2026-11-07T21:00:00Z (UTC)')
    expect(screen.getByText('30 h after departure')).toBeInTheDocument()
  })

  it('announces the time, not a bare number, to screen readers', () => {
    const { slider } = renderSlider()
    fireEvent.change(slider, { target: { value: '1' } })
    expect(slider).toHaveAttribute('aria-valuetext', 'Fri, Nov 6, 9:00 AM MST, 1 h after departure')
  })

  // Arrow-key stepping is the browser's own range behaviour, which jsdom does not implement.
  // It is covered in the Playwright suite (e2e/heatmap.spec.ts).
  it('tells the map about the chosen hour', async () => {
    const { slider, store } = renderSlider()
    fireEvent.change(slider, { target: { value: '3' } })
    expect(slider).toHaveValue('3')
    await vi.waitFor(() => expect(store.get()).toBe(3))
  })

  it('pushes at most one update per animation frame to the map', () => {
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) =>
      frames.push(callback),
    )
    const { slider, store } = renderSlider()
    const listener = vi.fn()
    store.subscribe(listener)

    for (const value of ['5', '9', '14']) fireEvent.change(slider, { target: { value } })

    expect(slider).toHaveValue('14') // the thumb and the label follow immediately
    expect(store.get()).toBe(0) // the map has not been told yet
    expect(frames).toHaveLength(1) // three moves, one frame scheduled
    frames[0](0)
    expect(store.get()).toBe(14) // only the latest hour is applied
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('explains that the shading is the corridor forecast and not the checkpoint risk', () => {
    renderSlider()
    expect(
      screen.getByText(/Shading shows the forecast risk across the corridor at this time/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Checkpoints keep showing the risk at their own arrival time/),
    ).toBeInTheDocument()
  })
})

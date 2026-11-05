import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ForecastSlider } from './ForecastSlider'
import { createHourStore } from './hourStore'

const HOURS = Array.from({ length: 49 }, (_, i) =>
  new Date(Date.parse('2026-11-06T15:00:00Z') + i * 3_600_000).toISOString().replace('.000Z', 'Z'),
)

function renderSlider(store = createHourStore(), departure = '2026-11-06T15:00:00Z') {
  render(
    <ForecastSlider store={store} hours={HOURS} departure={departure} timeZone="America/Denver" />,
  )
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

// Codex finding (PR #4): the forecast hours start at the top of the departure hour, so for a
// 8:45 AM departure hour 0 is 45 minutes BEFORE departure, not "at departure".
describe('ForecastSlider when the departure is not on the hour', () => {
  const DEPARTS_0845 = '2026-11-06T15:45:00Z' // 8:45 AM MST; the forecast hours still start at 8:00

  function at(hour: number) {
    const { slider } = renderSlider(createHourStore(), DEPARTS_0845)
    fireEvent.change(slider, { target: { value: String(hour) } })
    return slider
  }

  it('says the first forecast hour is before departure', () => {
    const slider = at(0)
    expect(screen.getByText('Fri, Nov 6, 8:00 AM MST')).toBeInTheDocument()
    expect(screen.getByText('45 min before departure')).toBeInTheDocument()
    expect(screen.queryByText('At departure')).not.toBeInTheDocument()
    expect(slider).toHaveAttribute(
      'aria-valuetext',
      'Fri, Nov 6, 8:00 AM MST, 45 min before departure',
    )
  })

  it('measures later hours from the real departure time', () => {
    const slider = at(1)
    expect(screen.getByText('15 min after departure')).toBeInTheDocument()
    expect(slider).toHaveAttribute(
      'aria-valuetext',
      'Fri, Nov 6, 9:00 AM MST, 15 min after departure',
    )
  })

  it.each([
    [2, '1 h 15 min after departure'],
    [25, '24 h 15 min after departure'],
    [48, '47 h 15 min after departure'],
  ])('labels hour %i as "%s"', (hour, label) => {
    at(hour)
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('marks the ends of the slider with clock times, not with offsets from departure', () => {
    renderSlider(createHourStore(), DEPARTS_0845)
    const ticks = screen.getByTestId('forecast-slider-ticks')
    expect(ticks).toHaveTextContent('Fri 8 AM')
    expect(ticks).toHaveTextContent('Sat 8 AM')
    expect(ticks).toHaveTextContent('Sun 8 AM')
    expect(ticks).not.toHaveTextContent('Departure')
    expect(ticks).not.toHaveTextContent('+24 h')
  })
})

describe('ForecastSlider when the departure is exactly on the hour', () => {
  it('still says "At departure" for the first hour and whole hours after it', () => {
    const { slider } = renderSlider()
    expect(screen.getByText('At departure')).toBeInTheDocument()
    expect(slider).toHaveAttribute('aria-valuetext', 'Fri, Nov 6, 8:00 AM MST, at departure')
    fireEvent.change(slider, { target: { value: '1' } })
    expect(screen.getByText('1 h after departure')).toBeInTheDocument()
  })
})

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CheckpointDetail } from './CheckpointDetail'
import { makeCheckpoint, makeRoute } from '../../test/fixtures'
import type { Checkpoint } from '../../types/api'

const route = makeRoute(1, ['low', 'severe', 'no_travel', 'low'], 'blocked')

function renderDetail(checkpoint: Checkpoint, handlers = {}) {
  const props = { onPrevious: vi.fn(), onNext: vi.fn(), onClose: vi.fn(), ...handlers }
  render(<CheckpointDetail route={route} checkpoint={checkpoint} {...props} />)
  return props
}

const windy = makeCheckpoint('route-1', 2, 'no_travel', {
  weather: {
    forecast_time: '2026-11-06T20:00:00Z',
    wind_mph: 50.1,
    wind_gust_mph: 70.14,
    rain_in_per_hr: 0.136,
    snow_in_per_hr: 1.6,
    temperature_f: 30.4,
    weather_code: 73,
  },
  eta: '2026-11-06T20:27:00Z',
  timezone: 'America/Chicago',
  risk: {
    level: 'no_travel',
    value: 4,
    drivers: ['wind', 'load_rule_2'],
    wind_level: 'no_travel',
    rain_level: 'moderate',
    snow_level: 'high',
    load_rule_applied: 'load_rule_2',
    missing: [],
  },
})

describe('CheckpointDetail', () => {
  it('says where the checkpoint is and when the truck gets there, in local time', () => {
    renderDetail(windy)
    expect(screen.getByRole('heading', { name: 'Route A, mile 50' })).toBeInTheDocument()
    expect(screen.getByText('Fri, Nov 6, 2:27 PM CST')).toBeInTheDocument()
    expect(screen.getByText(/Forecast for 2:00 PM CST/)).toBeInTheDocument()
  })

  it('labels the risk as the risk at the estimated arrival', () => {
    renderDetail(windy)
    expect(screen.getByText('Risk at estimated arrival')).toBeInTheDocument()
    expect(screen.getAllByText('No Travel').length).toBeGreaterThan(0)
  })

  it('shows each measurement with its unit and its own risk level', () => {
    renderDetail(windy)
    expect(screen.getByRole('row', { name: /Wind 50.1 mph No Travel/ })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /Rain 0.14 in\/h Moderate/ })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /Snow 1.60 in\/h High/ })).toBeInTheDocument()
    expect(screen.getByText(/Gusts 70.1 mph/)).toBeInTheDocument()
    expect(screen.getByText(/30 °F/)).toBeInTheDocument()
  })

  it('explains a load rule when one decided the wind risk', () => {
    renderDetail(windy)
    expect(
      screen.getByText('Wind of 45 to 55 mph is No Travel with a load over 30,000 lb.'),
    ).toBeInTheDocument()
  })

  it('keeps enough decimals that a reading never contradicts its level', () => {
    const barelyOver = makeCheckpoint('route-1', 1, 'no_travel', {
      weather: { ...windy.weather!, wind_mph: 10, rain_in_per_hr: 1.000394, snow_in_per_hr: 0 },
      risk: {
        ...windy.risk,
        wind_level: 'low',
        rain_level: 'no_travel',
        snow_level: 'low',
        load_rule_applied: null,
      },
    })
    renderDetail(barelyOver)
    expect(screen.getByRole('row', { name: /Rain 1.0004 in\/h No Travel/ })).toBeInTheDocument()
  })

  it('says an unknown checkpoint has no usable forecast and is not treated as safe', () => {
    renderDetail(makeCheckpoint('route-1', 1, 'unknown'))
    expect(screen.getByText('Unknown')).toBeInTheDocument()
    expect(
      screen.getByText(
        'No usable forecast for this arrival time, so this checkpoint is not treated as safe.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /Wind/ })).not.toBeInTheDocument()
  })

  it('names the measurement that is missing when the forecast is incomplete', () => {
    const partial = makeCheckpoint('route-1', 1, 'unknown', {
      weather: { ...windy.weather!, rain_in_per_hr: null },
      risk: {
        ...windy.risk,
        level: 'unknown',
        value: null,
        rain_level: null,
        missing: ['rain'],
        load_rule_applied: null,
      },
    })
    renderDetail(partial)
    expect(screen.getByRole('row', { name: /Rain Not available Unknown/ })).toBeInTheDocument()
  })

  it('states how many miles the checkpoint stands for', () => {
    renderDetail(windy)
    expect(screen.getByText(/Stands for 25.0 miles of this route/)).toBeInTheDocument()
  })

  it('steps to the neighbouring checkpoints and closes', async () => {
    const handlers = renderDetail(windy)
    await userEvent.click(screen.getByRole('button', { name: 'Previous checkpoint' }))
    await userEvent.click(screen.getByRole('button', { name: 'Next checkpoint' }))
    await userEvent.click(screen.getByRole('button', { name: 'Close checkpoint details' }))
    expect(handlers.onPrevious).toHaveBeenCalledOnce()
    expect(handlers.onNext).toHaveBeenCalledOnce()
    expect(handlers.onClose).toHaveBeenCalledOnce()
  })

  it('disables stepping past the ends of the route', () => {
    renderDetail(route.checkpoints[0])
    expect(screen.getByRole('button', { name: 'Previous checkpoint' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next checkpoint' })).toBeEnabled()
  })
})

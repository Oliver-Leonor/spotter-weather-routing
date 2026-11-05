import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TripForm, type TripFormValues } from './TripForm'
import { toDatetimeLocalValue } from '../../lib/format'

// The place search has its own tests; here a place is typed in directly.
vi.mock('./PlaceInput', () => ({
  PlaceInput: ({ label, value, onChange, error }: any) => (
    <label>
      {label}
      <input
        aria-label={label}
        value={value?.label ?? ''}
        onChange={(event) =>
          onChange(
            event.target.value
              ? {
                  lat: label === 'Origin' ? 39.7392 : 39.0997,
                  lon: label === 'Origin' ? -104.9903 : -94.5786,
                  label: event.target.value,
                }
              : null,
          )
        }
      />
      {error && <span>{error}</span>}
    </label>
  ),
}))

const NOW = new Date('2026-11-05T12:00:00Z')

function renderForm(props: Partial<Parameters<typeof TripForm>[0]> = {}) {
  const onSubmit = vi.fn<(values: TripFormValues) => void>()
  render(<TripForm onSubmit={onSubmit} isLoading={false} serverErrors={{}} now={NOW} {...props} />)
  return onSubmit
}

async function fillPlaces() {
  await userEvent.type(screen.getByLabelText('Origin'), 'Denver')
  await userEvent.type(screen.getByLabelText('Destination'), 'Kansas City')
}

describe('TripForm', () => {
  it('starts with a departure one hour ahead, a 42,000 lb load and 25 mile checkpoints', () => {
    renderForm()
    expect(screen.getByLabelText(/Departure/)).toHaveValue(
      toDatetimeLocalValue(new Date('2026-11-05T13:00:00Z')),
    )
    expect(screen.getByLabelText(/Load weight/)).toHaveValue(42000)
    expect(screen.getByRole('radio', { name: '25 mi' })).toBeChecked()
  })

  it('submits the trip as the API expects it', async () => {
    const onSubmit = renderForm()
    await fillPlaces()
    await userEvent.clear(screen.getByLabelText(/Load weight/))
    await userEvent.type(screen.getByLabelText(/Load weight/), '30001')
    await userEvent.click(screen.getByRole('radio', { name: '10 mi' }))
    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))

    expect(onSubmit).toHaveBeenCalledWith({
      origin: { lat: 39.7392, lon: -104.9903, label: 'Denver' },
      destination: { lat: 39.0997, lon: -94.5786, label: 'Kansas City' },
      departure_time: '2026-11-05T13:00:00.000Z',
      load_weight_lb: 30001,
      checkpoint_interval_miles: 10,
      mode: 'live',
    })
  })

  it('asks for a place to be chosen before comparing', async () => {
    const onSubmit = renderForm()
    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(screen.getByText('Choose where the trip starts.')).toBeInTheDocument()
    expect(screen.getByText('Choose where the trip ends.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it.each([
    ['', 'Enter the load weight in pounds.'],
    ['-5', 'Load weight must be between 0 and 200,000 lb.'],
    ['200001', 'Load weight must be between 0 and 200,000 lb.'],
    ['42000.5', 'Load weight must be a whole number of pounds.'],
  ])('rejects a load weight of "%s"', async (typed, message) => {
    const onSubmit = renderForm()
    await fillPlaces()
    await userEvent.clear(screen.getByLabelText(/Load weight/))
    if (typed) await userEvent.type(screen.getByLabelText(/Load weight/), typed)
    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(screen.getByText(message)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('rejects a departure outside the forecast window', async () => {
    const onSubmit = renderForm()
    await fillPlaces()
    const departure = screen.getByLabelText(/Departure/)
    await userEvent.clear(departure)
    await userEvent.type(departure, toDatetimeLocalValue(new Date('2026-11-25T12:00:00Z')))
    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(screen.getByText('Choose a departure within the next 14 days.')).toBeInTheDocument()

    await userEvent.clear(departure)
    await userEvent.type(departure, toDatetimeLocalValue(new Date('2026-11-05T09:00:00Z')))
    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(
      screen.getByText('Departure cannot be more than 1 hour in the past.'),
    ).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('shows field errors returned by the server', () => {
    renderForm({
      serverErrors: { destination: 'Origin and destination must be different places.' },
    })
    expect(screen.getByText('Origin and destination must be different places.')).toBeInTheDocument()
  })

  it('loads the demo trip with simulated weather in one step', async () => {
    const onSubmit = renderForm()
    await userEvent.click(screen.getByRole('button', { name: 'Run the demo trip' }))

    expect(onSubmit).toHaveBeenCalledWith({
      origin: { lat: 39.7392, lon: -104.9903, label: 'Denver, Colorado, US' },
      destination: { lat: 39.0997, lon: -94.5786, label: 'Kansas City, Missouri, US' },
      departure_time: '2026-11-05T15:00:00.000Z', // the next 8:00 AM in Denver
      load_weight_lb: 42000,
      checkpoint_interval_miles: 25,
      mode: 'fixture',
    })
    expect(screen.getByLabelText('Origin')).toHaveValue('Denver, Colorado, US')
    expect(screen.getByLabelText('Destination')).toHaveValue('Kansas City, Missouri, US')
  })

  it('keeps comparing in demo mode after the demo trip is loaded, until a place is changed', async () => {
    const onSubmit = renderForm()
    await userEvent.click(screen.getByRole('button', { name: 'Run the demo trip' }))
    await userEvent.clear(screen.getByLabelText(/Load weight/))
    await userEvent.type(screen.getByLabelText(/Load weight/), '28000')
    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(onSubmit).toHaveBeenLastCalledWith(
      expect.objectContaining({ mode: 'fixture', load_weight_lb: 28000 }),
    )

    await userEvent.type(screen.getByLabelText('Origin'), ' again')
    await userEvent.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(onSubmit).toHaveBeenLastCalledWith(expect.objectContaining({ mode: 'live' }))
  })

  it('cannot be submitted twice while an analysis is running', () => {
    renderForm({ isLoading: true })
    expect(screen.getByRole('button', { name: 'Comparing routes…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Run the demo trip' })).toBeDisabled()
  })
})

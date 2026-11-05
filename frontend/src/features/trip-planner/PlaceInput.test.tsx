import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PlaceInput } from './PlaceInput'
import { searchPlaces } from '../../lib/api'
import type { LatLon } from '../../types/api'

vi.mock('../../lib/api', async (original) => ({
  ...(await original<typeof import('../../lib/api')>()),
  searchPlaces: vi.fn(),
}))

const DENVER = {
  name: 'Denver',
  admin1: 'Colorado',
  country_code: 'US',
  lat: 39.74,
  lon: -104.98,
  label: 'Denver, Colorado, US',
}
const DENVER_CITY = {
  name: 'Denver City',
  admin1: 'Texas',
  country_code: 'US',
  lat: 32.96,
  lon: -102.83,
  label: 'Denver City, Texas, US',
}

function Harness({ onChange }: { onChange: (place: LatLon | null) => void }) {
  const [place, setPlace] = useState<LatLon | null>(null)
  return (
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PlaceInput
        label="Origin"
        value={place}
        onChange={(next) => {
          setPlace(next)
          onChange(next)
        }}
      />
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.mocked(searchPlaces).mockReset().mockResolvedValue([DENVER, DENVER_CITY])
})

describe('PlaceInput', () => {
  it('suggests places for what was typed and selects one with a click', async () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)

    await userEvent.type(screen.getByRole('combobox', { name: 'Origin' }), 'Denv')
    await userEvent.click(await screen.findByRole('option', { name: 'Denver, Colorado, US' }))

    expect(searchPlaces).toHaveBeenCalledWith('Denv', expect.anything())
    expect(onChange).toHaveBeenLastCalledWith({
      lat: 39.74,
      lon: -104.98,
      label: 'Denver, Colorado, US',
    })
    expect(screen.getByRole('combobox', { name: 'Origin' })).toHaveValue('Denver, Colorado, US')
    expect(screen.queryByRole('option')).not.toBeInTheDocument()
  })

  it('selects with the keyboard', async () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)

    await userEvent.type(screen.getByRole('combobox', { name: 'Origin' }), 'Denv')
    await screen.findByRole('option', { name: 'Denver City, Texas, US' })
    await userEvent.keyboard('{ArrowDown}{ArrowDown}{Enter}')

    expect(onChange).toHaveBeenLastCalledWith({
      lat: 32.96,
      lon: -102.83,
      label: 'Denver City, Texas, US',
    })
  })

  it('does not search for a single character', async () => {
    render(<Harness onChange={vi.fn()} />)
    await userEvent.type(screen.getByRole('combobox', { name: 'Origin' }), 'D')
    await new Promise((resolve) => setTimeout(resolve, 400))
    expect(searchPlaces).not.toHaveBeenCalled()
  })

  it('clears the chosen place when the text is edited again', async () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    const input = screen.getByRole('combobox', { name: 'Origin' })

    await userEvent.type(input, 'Denv')
    await userEvent.click(await screen.findByRole('option', { name: 'Denver, Colorado, US' }))
    await userEvent.type(input, 'x')

    expect(onChange).toHaveBeenLastCalledWith(null)
  })

  it('says when nothing matches', async () => {
    vi.mocked(searchPlaces).mockResolvedValue([])
    render(<Harness onChange={vi.fn()} />)
    await userEvent.type(screen.getByRole('combobox', { name: 'Origin' }), 'Zzzz')
    expect(await screen.findByText('No places match "Zzzz".')).toBeInTheDocument()
  })

  it('says when place search is unavailable', async () => {
    vi.mocked(searchPlaces).mockRejectedValue(new Error('Place search is unavailable right now.'))
    render(<Harness onChange={vi.fn()} />)
    await userEvent.type(screen.getByRole('combobox', { name: 'Origin' }), 'Denv')
    await waitFor(() =>
      expect(screen.getByText('Place search is unavailable right now.')).toBeInTheDocument(),
    )
  })
})

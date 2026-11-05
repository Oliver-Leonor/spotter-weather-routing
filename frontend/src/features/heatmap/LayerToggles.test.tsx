import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { LayerToggles, type MapLayers } from './LayerToggles'

const ALL_ON: MapLayers = { heatmap: true, checkpoints: true, otherRoutes: true }

describe('LayerToggles', () => {
  it('offers the weather corridor, checkpoints and other routes', () => {
    render(<LayerToggles layers={ALL_ON} onChange={vi.fn()} heatmapAvailable />)
    expect(screen.getByRole('checkbox', { name: 'Weather corridor' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Checkpoints' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Other routes' })).toBeChecked()
  })

  it('reports the new set of layers when one is switched', async () => {
    const onChange = vi.fn()
    render(<LayerToggles layers={ALL_ON} onChange={onChange} heatmapAvailable />)
    await userEvent.click(screen.getByRole('checkbox', { name: 'Weather corridor' }))
    expect(onChange).toHaveBeenCalledWith({ heatmap: false, checkpoints: true, otherRoutes: true })
  })

  it('disables the corridor switch when there is no corridor forecast', () => {
    render(<LayerToggles layers={ALL_ON} onChange={vi.fn()} heatmapAvailable={false} />)
    expect(screen.getByRole('checkbox', { name: 'Weather corridor' })).toBeDisabled()
  })
})

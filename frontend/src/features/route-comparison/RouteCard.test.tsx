import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { RouteCard } from './RouteCard'
import { makeRoute } from '../../test/fixtures'

const blocked = makeRoute(1, ['low', 'severe', 'no_travel', 'low'], 'blocked')
const fine = makeRoute(2, ['low', 'moderate', 'high', 'low'], 'ok')
const unverified = makeRoute(3, ['low', 'unknown', 'low', 'low'], 'unverified')

function renderCard(route = fine, props: Partial<Parameters<typeof RouteCard>[0]> = {}) {
  const onSelect = vi.fn()
  const onSelectCheckpoint = vi.fn()
  render(
    <RouteCard
      route={route}
      isSelected={false}
      isRecommended={false}
      selectedCheckpointId={null}
      onSelect={onSelect}
      onSelectCheckpoint={onSelectCheckpoint}
      {...props}
    />,
  )
  return { onSelect, onSelectCheckpoint }
}

describe('RouteCard', () => {
  it('shows the route name, travel time, distance and arrival in the destination time zone', () => {
    renderCard(fine)
    expect(screen.getByRole('heading', { name: 'Route B' })).toBeInTheDocument()
    expect(screen.getByText('3 h')).toBeInTheDocument() // 10,800 seconds
    expect(screen.getByText('75 mi')).toBeInTheDocument()
    expect(screen.getByText(/Arrives 10:30 AM MST/)).toBeInTheDocument()
  })

  it('lists the miles at each risk level that the route actually has', () => {
    renderCard(fine)
    const miles = screen.getByRole('list', { name: 'Miles by risk level' })
    expect(
      within(miles)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['High25.0 mi', 'Moderate25.0 mi', 'Low25.0 mi'])
  })

  it('marks the recommended route', () => {
    renderCard(fine, { isRecommended: true })
    expect(screen.getByText('Recommended')).toBeInTheDocument()
  })

  it('warns that a blocked route has No Travel conditions and is not recommended', () => {
    renderCard(blocked)
    expect(screen.getByText('Blocked')).toBeInTheDocument()
    expect(
      screen.getByText(/No Travel conditions on 25.0 miles. Not recommended./),
    ).toBeInTheDocument()
  })

  it('says an unverified route is not treated as safe', () => {
    renderCard(unverified)
    expect(screen.getByText('Unverified')).toBeInTheDocument()
    expect(
      screen.getByText(/No usable forecast for 25.0 miles. Not treated as safe./),
    ).toBeInTheDocument()
  })

  it('selects the route when its header is activated', async () => {
    const { onSelect } = renderCard(fine)
    await userEvent.click(screen.getByRole('button', { name: /Route B/ }))
    expect(onSelect).toHaveBeenCalledWith('route-2')
  })

  it('exposes the selected state to assistive technology', () => {
    renderCard(fine, { isSelected: true })
    expect(screen.getByRole('button', { name: /Route B/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('selects a checkpoint from the risk ribbon', async () => {
    const { onSelectCheckpoint } = renderCard(blocked)
    await userEvent.click(screen.getByRole('button', { name: 'Mile 50, No Travel' }))
    expect(onSelectCheckpoint).toHaveBeenCalledWith('route-1', 'route-1-cp-2')
  })

  it('describes the ribbon for screen readers', () => {
    renderCard(blocked)
    expect(
      screen.getByRole('group', { name: 'Risk along Route A, from origin to destination' }),
    ).toBeInTheDocument()
  })
})

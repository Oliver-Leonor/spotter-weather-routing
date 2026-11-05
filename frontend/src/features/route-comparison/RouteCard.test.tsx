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

// Review finding (PR #3): the ribbon was pointer-only, so keyboard users could never open the
// checkpoint details. The ribbon is now one tab stop with arrow-key movement inside it.
describe('RouteCard keyboard access to checkpoints', () => {
  const segment = (name: string) => screen.getByRole('button', { name })

  it('is a single tab stop that starts on the first checkpoint', async () => {
    renderCard(blocked)
    await userEvent.tab() // the route itself
    expect(screen.getByRole('button', { name: /Route A/ })).toHaveFocus()
    await userEvent.tab() // into the ribbon
    expect(segment('Origin, Low')).toHaveFocus()
    await userEvent.tab() // out of the ribbon again, not on to the next checkpoint
    expect(segment('Mile 25, Severe')).not.toHaveFocus()
    expect(document.body).toHaveFocus()
  })

  it('moves between checkpoints with the arrow, Home and End keys', async () => {
    renderCard(blocked)
    await userEvent.tab()
    await userEvent.tab()
    await userEvent.keyboard('{ArrowRight}')
    expect(segment('Mile 25, Severe')).toHaveFocus()
    await userEvent.keyboard('{ArrowRight}{ArrowRight}{ArrowRight}') // stops at the destination
    expect(segment('Destination, Low')).toHaveFocus()
    await userEvent.keyboard('{ArrowLeft}')
    expect(segment('Mile 50, No Travel')).toHaveFocus()
    await userEvent.keyboard('{Home}')
    expect(segment('Origin, Low')).toHaveFocus()
    await userEvent.keyboard('{End}')
    expect(segment('Destination, Low')).toHaveFocus()
  })

  it('opens the focused checkpoint with Enter or Space', async () => {
    const { onSelectCheckpoint } = renderCard(blocked)
    await userEvent.tab()
    await userEvent.tab()
    await userEvent.keyboard('{ArrowRight}{Enter}')
    expect(onSelectCheckpoint).toHaveBeenLastCalledWith('route-1', 'route-1-cp-1')
    await userEvent.keyboard('{ArrowRight} ')
    expect(onSelectCheckpoint).toHaveBeenLastCalledWith('route-1', 'route-1-cp-2')
  })

  it('returns to the selected checkpoint when the ribbon is entered again', async () => {
    renderCard(blocked, { selectedCheckpointId: 'route-1-cp-2' })
    await userEvent.tab()
    await userEvent.tab()
    expect(segment('Mile 50, No Travel')).toHaveFocus()
    expect(segment('Mile 50, No Travel')).toHaveAttribute('aria-pressed', 'true')
  })

  it('tells keyboard users how to use the ribbon', () => {
    renderCard(blocked)
    expect(
      screen.getByRole('group', { name: 'Risk along Route A, from origin to destination' }),
    ).toHaveAccessibleDescription(
      'Use the arrow keys to move between checkpoints and Enter to open one.',
    )
  })
})

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RecommendationBanner } from './RecommendationBanner'
import { makeAnalysis } from '../../test/fixtures'

describe('RecommendationBanner', () => {
  it('names the recommended route and explains why', () => {
    const { recommendation, routes } = makeAnalysis()
    render(<RecommendationBanner recommendation={recommendation} routes={routes} />)
    expect(screen.getByRole('heading', { name: 'Take Route B' })).toBeInTheDocument()
    expect(
      screen.getByText(/it is the only route that is neither blocked nor unverified/),
    ).toBeInTheDocument()
  })

  it('says plainly when no route is safe', () => {
    const { routes } = makeAnalysis()
    render(
      <RecommendationBanner
        routes={routes}
        recommendation={{
          route_id: null,
          explanation:
            'No safe route is currently recommended. Route A: No Travel at checkpoint 2 (wind 58.0 mph).',
          ranking: [],
          blocked_route_ids: ['route-1'],
          unverified_route_ids: [],
        }}
      />,
    )
    expect(
      screen.getByRole('heading', { name: 'No safe route is currently recommended' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Route A: No Travel at checkpoint 2 (wind 58.0 mph).'),
    ).toBeInTheDocument()
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

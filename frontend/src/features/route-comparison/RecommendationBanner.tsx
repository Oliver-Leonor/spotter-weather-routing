import { CircleCheck, TriangleAlert } from 'lucide-react'
import type { Recommendation, RouteAnalysis } from '../../types/api'

const NO_ROUTE_LEAD = 'No safe route is currently recommended.'

interface Props {
  recommendation: Recommendation
  routes: RouteAnalysis[]
}

/** The answer the driver came for, with the reasoning the backend computed. */
export function RecommendationBanner({ recommendation, routes }: Props) {
  const recommended = routes.find((route) => route.id === recommendation.route_id)

  if (!recommended) {
    const reasons = recommendation.explanation.replace(NO_ROUTE_LEAD, '').trim()
    return (
      <section role="alert" className="rounded-lg border-2 border-risk-no-travel bg-red-50 p-4">
        <h2 className="flex items-start gap-2 font-display text-2xl leading-tight font-semibold text-risk-no-travel">
          <TriangleAlert className="mt-0.5 h-6 w-6 shrink-0" aria-hidden="true" />
          No safe route is currently recommended
        </h2>
        {reasons && <p className="mt-2 text-sm leading-relaxed text-ink">{reasons}</p>}
      </section>
    )
  }

  return (
    <section role="status" className="rounded-lg bg-ink p-4 text-white">
      <h2 className="flex items-center gap-2 font-display text-2xl leading-tight font-semibold">
        <CircleCheck className="h-6 w-6 shrink-0 text-teal-400" aria-hidden="true" />
        Take {recommended.name}
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-200">{recommendation.explanation}</p>
    </section>
  )
}

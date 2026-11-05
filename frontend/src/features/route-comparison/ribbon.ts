import type { Checkpoint, CheckpointKind, RiskLevelOrUnknown } from '../../types/api'

export interface RibbonSegment {
  checkpointId: string
  kind: CheckpointKind
  level: RiskLevelOrUnknown
  distanceMiles: number
  /** Share of the route this checkpoint stands for, from the miles attributed to it. */
  widthPercent: number
}

/** The route as a strip: one segment per checkpoint, as wide as the miles it owns. */
export function ribbonSegments(checkpoints: Checkpoint[]): RibbonSegment[] {
  const total = checkpoints.reduce((sum, c) => sum + c.attributed_miles, 0)
  if (total <= 0) return []
  return checkpoints.map((checkpoint) => ({
    checkpointId: checkpoint.id,
    kind: checkpoint.kind,
    level: checkpoint.risk.level,
    distanceMiles: checkpoint.distance_miles,
    widthPercent: (checkpoint.attributed_miles / total) * 100,
  }))
}

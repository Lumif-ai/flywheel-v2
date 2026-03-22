import type { WorkStreamEntity } from '@/types/streams'
import { DensityBar } from './DensityIndicator'

interface StreamIntelligenceProps {
  entities: WorkStreamEntity[]
  densityScore: number
}

export function StreamIntelligence({ entities, densityScore }: StreamIntelligenceProps) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-2 text-sm font-medium text-muted-foreground">
          Knowledge Coverage
        </h3>
        <DensityBar score={densityScore} showLabel />
      </div>

      <div>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">
          Linked Entities
        </h3>

        {entities.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <p className="text-sm text-muted-foreground">
              No entities linked. Intelligence will appear as context accumulates.
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {entities.map((entity) => (
              <div
                key={entity.id}
                className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5"
              >
                <span className="text-sm font-medium">{entity.entity_name}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(entity.linked_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

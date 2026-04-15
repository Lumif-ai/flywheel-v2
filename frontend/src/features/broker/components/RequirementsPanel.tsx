import { ShimmerSkeleton } from '@/components/ui/skeleton'
import type { ProjectCoverage, AnalysisStatus } from '../types/broker'
import { RequirementCard } from './RequirementCard'

interface RequirementsPanelProps {
  coverages: ProjectCoverage[]
  analysisStatus: AnalysisStatus
}

export function RequirementsPanel({ coverages, analysisStatus }: RequirementsPanelProps) {
  if (analysisStatus === 'running') {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <ShimmerSkeleton key={i} className="h-24 w-full rounded-xl" />
        ))}
      </div>
    )
  }

  if (analysisStatus === 'failed') {
    return (
      <div className="flex flex-col items-center py-12 text-muted-foreground">
        <p className="text-sm text-destructive font-medium">Analysis failed</p>
        <p className="text-xs mt-1">Re-upload documents and run analysis again.</p>
      </div>
    )
  }

  if (coverages.length === 0) {
    return (
      <div className="flex flex-col items-center py-12 text-muted-foreground">
        <p className="text-sm">No requirements extracted yet.</p>
        <p className="text-xs mt-1">Upload contract documents and run analysis.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {coverages.map((coverage, index) => (
        <RequirementCard
          key={coverage.id}
          coverage={coverage}
          style={{
            // Spec requires 60ms stagger — do NOT use staggerDelay() which is 50ms
            animationDelay: `${index * 60}ms`,
            opacity: 0,
          }}
        />
      ))}
    </div>
  )
}

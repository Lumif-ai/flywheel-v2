import { CheckCircle, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useBrokerProject } from '../../hooks/useBrokerProject'
import { useCoverageMutation } from '../../hooks/useCoverageMutation'
import { useApproveProject } from '../../hooks/useApproveProject'
import { GapCoverageGrid } from '../GapCoverageGrid'

interface CoverageTabProps {
  projectId: string
}

export function CoverageTab({ projectId }: CoverageTabProps) {
  const { data: project, isLoading } = useBrokerProject(projectId)
  // Keep mutation available for inline edits triggered elsewhere in the tab
  useCoverageMutation(projectId)
  const approve = useApproveProject(projectId)

  const coverages = project?.coverages ?? []

  const daysUntilStart = project?.start_date
    ? Math.ceil((new Date(project.start_date).getTime() - Date.now()) / 86_400_000)
    : null
  const showUrgencyBanner = daysUntilStart !== null && daysUntilStart <= 30

  if (isLoading) {
    return (
      <div className="space-y-4 py-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-11 w-full rounded" />
        ))}
      </div>
    )
  }

  if (coverages.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
        No coverages extracted yet. Trigger analysis to extract requirements.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Urgency Banner — project starts within 30 days */}
      {showUrgencyBanner && (
        <div
          style={{
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 8,
            padding: '12px 16px',
          }}
          className="flex items-start gap-2"
        >
          <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
          <p className="text-sm text-red-700">
            {daysUntilStart !== null && daysUntilStart <= 0
              ? 'Project has started — coverage gaps remain unresolved.'
              : `Project starts in ${daysUntilStart} day${daysUntilStart === 1 ? '' : 's'} — ensure all coverage gaps are resolved.`}
          </p>
        </div>
      )}

      {/* Coverage Grid */}
      <GapCoverageGrid coverages={coverages} />

      {/* Approve Project Button */}
      <div className="pt-2">
        {project?.approval_status === 'approved' ? (
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm font-medium">Project Approved</span>
          </div>
        ) : (
          <Button onClick={() => approve.mutate()} disabled={approve.isPending}>
            {approve.isPending ? 'Approving...' : 'Approve Project'}
          </Button>
        )}
      </div>
    </div>
  )
}

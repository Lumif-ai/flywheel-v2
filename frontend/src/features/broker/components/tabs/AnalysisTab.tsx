import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { useAnalysisPolling } from '../../hooks/useAnalysisPolling'
import { DocumentViewer } from '../DocumentViewer'
import { RequirementsPanel } from '../RequirementsPanel'
import type { BrokerProjectDetail } from '../../types/broker'

interface AnalysisTabProps {
  project: BrokerProjectDetail
}

export function AnalysisTab({ project }: AnalysisTabProps) {
  const { data } = useAnalysisPolling(project.id)
  const analysisStatus = data?.analysis_status ?? project.analysis_status
  const coverages = data?.coverages ?? project.coverages ?? []
  const isRunning = analysisStatus === 'running'

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-[calc(100vh-200px)]">
      {/* Left: Document viewer */}
      <div className="rounded-xl border overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto">
          {isRunning ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <ShimmerSkeleton key={i} className="h-20 w-full rounded-lg" />
              ))}
            </div>
          ) : (
            <DocumentViewer coverages={coverages} />
          )}
        </div>
      </div>

      {/* Right: Requirements panel */}
      <div className="rounded-xl border overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b bg-muted/30">
          <h3 className="text-sm font-semibold">Requirements</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <RequirementsPanel coverages={coverages} analysisStatus={analysisStatus} />
        </div>
      </div>
    </div>
  )
}

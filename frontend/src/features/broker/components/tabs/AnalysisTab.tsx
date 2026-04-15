import { ShimmerSkeleton } from '@/components/ui/skeleton'
import { useAnalysisPolling } from '../../hooks/useAnalysisPolling'
import { DocumentViewer } from '../DocumentViewer'
import type { BrokerProjectDetail } from '../../types/broker'

interface AnalysisTabProps {
  project: BrokerProjectDetail
}

export function AnalysisTab({ project }: AnalysisTabProps) {
  const { data } = useAnalysisPolling(project.id)
  const analysisStatus = data?.analysis_status ?? project.analysis_status
  const coverages = data?.coverages ?? project.coverages ?? []
  const isRunning = analysisStatus === 'running'
  const isFailed = analysisStatus === 'failed'

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ minHeight: '600px' }}>
      {/* Left: Document viewer */}
      <div className="rounded-xl border overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b bg-muted/30">
          <h3 className="text-sm font-semibold">Contract Documents</h3>
        </div>
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

      {/* Right: Requirements panel (shell — filled in 137-03) */}
      <div className="rounded-xl border overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b bg-muted/30">
          <h3 className="text-sm font-semibold">Requirements</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {isRunning ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <ShimmerSkeleton key={i} className="h-24 w-full rounded-xl" />
              ))}
            </div>
          ) : isFailed ? (
            <div className="flex flex-col items-center py-12 text-muted-foreground">
              <p className="text-sm text-destructive">Analysis failed. Re-run to try again.</p>
            </div>
          ) : coverages.length === 0 ? (
            <div className="flex flex-col items-center py-12 text-muted-foreground">
              <p className="text-sm">No requirements extracted yet. Upload documents and run analysis.</p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Requirements panel coming in next plan.</p>
          )}
        </div>
      </div>
    </div>
  )
}

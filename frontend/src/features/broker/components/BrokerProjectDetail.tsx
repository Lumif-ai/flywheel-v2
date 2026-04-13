import { useParams, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft } from 'lucide-react'
import { format } from 'date-fns'
import { useBrokerProject } from '../hooks/useBrokerProject'
import { useAnalyzeProject } from '../hooks/useAnalyzeProject'
import { StatusBadge } from './StatusBadge'
import { CoverageTable } from './CoverageTable'
import { GapAnalysis } from './GapAnalysis'
import { CarrierSelection } from './CarrierSelection'
import { SolicitationPanel } from './SolicitationPanel'
import { QuoteTracking } from './QuoteTracking'
import { ComparisonMatrix } from './ComparisonMatrix'
import { ActivityTimeline } from './ActivityTimeline'
import { DeliveryPanel } from './DeliveryPanel'

export function BrokerProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: project, isLoading } = useBrokerProject(id!)
  const analyzeMutation = useAnalyzeProject(id!)

  if (isLoading) return <DetailSkeleton />
  if (!project) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">Project not found.</p>
        <Button variant="ghost" className="mt-4" onClick={() => navigate('/broker')}>
          Back to Dashboard
        </Button>
      </div>
    )
  }

  const canAnalyze = project.analysis_status !== 'running'

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/broker')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold">{project.name}</h1>
            <p className="text-sm text-muted-foreground">{project.project_type || 'General'}</p>
          </div>
          <StatusBadge status={project.status} />
        </div>
        <Button
          onClick={() => analyzeMutation.mutate()}
          disabled={!canAnalyze || analyzeMutation.isPending}
        >
          {project.analysis_status === 'running' ? 'Analyzing...' : 'Run Analysis'}
        </Button>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content: coverages (2/3 width) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="space-y-4">
            <h2 className="text-lg font-medium">Coverage Requirements</h2>
            <CoverageTable
              coverages={project.coverages}
              projectId={project.id}
              isAnalyzing={project.analysis_status === 'running'}
            />
          </div>

          {/* Gap Analysis section */}
          {project.coverages.length > 0 && (
            <GapAnalysis coverages={project.coverages} projectId={project.id} />
          )}

          {/* Carrier Selection section */}
          {['gaps_identified', 'soliciting', 'quotes_partial', 'quotes_complete', 'bound'].includes(project.status) && (
            <CarrierSelection projectId={project.id} />
          )}

          {/* Solicitation Panel -- shows after drafts are created */}
          {['soliciting', 'quotes_partial', 'quotes_complete', 'bound'].includes(project.status) && (
            <SolicitationPanel projectId={project.id} />
          )}

          {/* Quote Tracking -- shows when soliciting or later */}
          {['soliciting', 'quotes_partial', 'quotes_complete', 'bound'].includes(project.status) && (
            <QuoteTracking projectId={project.id} />
          )}

          {/* Comparison Matrix -- shows when quotes start coming in */}
          {['quotes_partial', 'quotes_complete', 'bound'].includes(project.status) && (
            <ComparisonMatrix projectId={project.id} currency={project.currency || 'MXN'} />
          )}

          {/* Delivery Panel -- shows when quotes are complete or later */}
          {['quotes_complete', 'recommended', 'delivered'].includes(project.status) && (
            <DeliveryPanel project={project} />
          )}
        </div>

        {/* Sidebar: project info + timeline (1/3 width) */}
        <div className="space-y-4">
          {/* Project info card */}
          <div className="rounded-xl border p-4 space-y-2">
            <h3 className="font-medium">Project Info</h3>
            <dl className="text-sm space-y-1">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Source</dt>
                <dd>{project.source}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Type</dt>
                <dd>{project.project_type || '\u2014'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Created</dt>
                <dd>{format(new Date(project.created_at), 'MMM d, yyyy')}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Coverages</dt>
                <dd>{project.coverages.length}</dd>
              </div>
              {project.contract_value != null && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Value</dt>
                  <dd>
                    {new Intl.NumberFormat('en-US', {
                      style: 'currency',
                      currency: project.currency || 'USD',
                      maximumFractionDigits: 0,
                    }).format(project.contract_value)}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Activity timeline */}
          <div className="rounded-xl border p-4">
            <h3 className="font-medium mb-3">Activity</h3>
            <ActivityTimeline activities={project.activities} />
          </div>
        </div>
      </div>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Skeleton className="h-9 w-9 rounded-md" />
        <div className="space-y-2">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          <Skeleton className="h-5 w-40" />
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-lg" />
          ))}
        </div>
        <div className="space-y-4">
          <Skeleton className="h-48 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      </div>
    </div>
  )
}

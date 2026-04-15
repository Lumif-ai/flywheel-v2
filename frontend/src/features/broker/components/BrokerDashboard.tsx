import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useBrokerProjects } from '../hooks/useBrokerProjects'
import { useDashboardStats } from '../hooks/useDashboardStats'
import { TaskList } from './TaskList'
import { ProjectPipelineGrid } from './ProjectPipelineGrid'
import { CreateProjectDialog } from './CreateProjectDialog'
import { MetricCard } from './MetricCard'

const PAGE_SIZE = 20

const ACTION_STATUSES = 'new_request,analysis_failed,gaps_identified'

function formatPremium(value: number): string {
  if (value >= 1_000_000) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value)
  }
  if (value >= 1_000) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 0,
    }).format(value)
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function BrokerDashboard() {
  const [offset, setOffset] = useState(0)
  const [filterAttention, setFilterAttention] = useState(false)
  const navigate = useNavigate()

  const { data: stats } = useDashboardStats()

  const { data: projects, isLoading: projectsLoading } = useBrokerProjects({
    limit: PAGE_SIZE,
    offset,
    ...(filterAttention ? { status: ACTION_STATUSES } : {}),
  })

  const needsAttentionCount = stats?.projects_needing_action ?? 0
  const totalPremium = stats?.total_premium ?? 0
  const quotesComplete = stats?.projects_by_status?.['quotes_complete'] ?? 0

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
        <CreateProjectDialog />
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricCard
          label="Total Projects"
          value={stats?.total_projects ?? 0}
        />
        <MetricCard
          label="Needs Attention"
          value={needsAttentionCount}
          accent={needsAttentionCount > 0}
        />
        <MetricCard
          label="Total Premium"
          value={formatPremium(totalPremium)}
        />
        <MetricCard
          label="Quotes Complete"
          value={quotesComplete}
        />
      </div>

      <TaskList />

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-foreground">Pipeline</h2>
          <button
            onClick={() => {
              setFilterAttention((prev) => !prev)
              setOffset(0)
            }}
            className="text-sm px-3 py-1 rounded-full border transition-colors"
            style={
              filterAttention
                ? { backgroundColor: '#E94D35', color: '#FFFFFF', borderColor: '#E94D35' }
                : { backgroundColor: 'transparent', color: '#374151', borderColor: '#D1D5DB' }
            }
          >
            Needs Attention
            {needsAttentionCount > 0 && (
              <span
                className="ml-1.5 text-xs font-semibold px-1.5 py-0.5 rounded-full"
                style={
                  filterAttention
                    ? { backgroundColor: 'rgba(255,255,255,0.25)', color: '#FFFFFF' }
                    : { backgroundColor: '#FEE2E2', color: '#B91C1C' }
                }
              >
                {needsAttentionCount}
              </span>
            )}
          </button>
        </div>
        <ProjectPipelineGrid
          projects={projects?.items ?? []}
          total={projects?.total ?? 0}
          isLoading={projectsLoading}
          offset={offset}
          limit={PAGE_SIZE}
          onPageChange={setOffset}
          onRowClick={(id) => navigate(`/broker/projects/${id}`)}
          storageKey="broker-dashboard-pipeline"
        />
      </section>
    </div>
  )
}

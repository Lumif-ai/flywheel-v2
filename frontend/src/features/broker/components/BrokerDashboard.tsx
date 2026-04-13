import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useDashboardStats } from '../hooks/useDashboardStats'
import { useBrokerProjects } from '../hooks/useBrokerProjects'
import { KPICards } from './KPICards'
import { ProjectTable } from './ProjectTable'
import { CreateProjectDialog } from './CreateProjectDialog'

const PAGE_SIZE = 20

export function BrokerDashboard() {
  const [offset, setOffset] = useState(0)
  const { data: stats, isLoading: statsLoading } = useDashboardStats()
  const { data: projects, isLoading: projectsLoading } = useBrokerProjects({
    limit: PAGE_SIZE,
    offset,
  })
  const navigate = useNavigate()

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Broker Dashboard</h1>
        <CreateProjectDialog />
      </div>

      {statsLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      ) : stats ? (
        <KPICards stats={stats} />
      ) : null}

      <ProjectTable
        projects={projects?.items ?? []}
        total={projects?.total ?? 0}
        isLoading={projectsLoading}
        onPageChange={setOffset}
        onRowClick={(id) => navigate(`/broker/projects/${id}`)}
        limit={PAGE_SIZE}
        offset={offset}
      />
    </div>
  )
}

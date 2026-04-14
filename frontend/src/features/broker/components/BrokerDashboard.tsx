import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useBrokerProjects } from '../hooks/useBrokerProjects'
import { TaskList } from './TaskList'
import { ProjectPipelineGrid } from './ProjectPipelineGrid'
import { CreateProjectDialog } from './CreateProjectDialog'

const PAGE_SIZE = 20

export function BrokerDashboard() {
  const [offset, setOffset] = useState(0)
  const { data: projects, isLoading: projectsLoading } = useBrokerProjects({
    limit: PAGE_SIZE,
    offset,
  })
  const navigate = useNavigate()

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
        <CreateProjectDialog />
      </div>

      <TaskList />

      <section>
        <h2 className="text-lg font-semibold text-foreground mb-3">Pipeline</h2>
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

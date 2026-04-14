import { format } from 'date-fns'
import { ActivityTimeline } from './ActivityTimeline'
import type { BrokerProjectDetail } from '../types/broker'

interface ProjectSidebarProps {
  project: BrokerProjectDetail
}

export function ProjectSidebar({ project }: ProjectSidebarProps) {
  const formattedValue =
    project.contract_value != null
      ? new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: project.currency || 'USD',
          maximumFractionDigits: 0,
        }).format(project.contract_value)
      : null

  return (
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
          {project.location && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Location</dt>
              <dd>{project.location}</dd>
            </div>
          )}
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Created</dt>
            <dd>{format(new Date(project.created_at), 'MMM d, yyyy')}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Coverages</dt>
            <dd>{project.coverages.length}</dd>
          </div>
          {formattedValue && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Value</dt>
              <dd>{formattedValue}</dd>
            </div>
          )}
        </dl>
      </div>

      {/* Activity card */}
      <div className="rounded-xl border p-4">
        <h3 className="font-medium mb-3">Activity</h3>
        <ActivityTimeline activities={project.activities} />
      </div>
    </div>
  )
}

import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { StatusBadge } from './StatusBadge'
import type { BrokerProject } from '../types/broker'

interface ProjectTableProps {
  projects: BrokerProject[]
  total: number
  isLoading: boolean
  onPageChange: (offset: number) => void
  onRowClick: (id: string) => void
  limit?: number
  offset?: number
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function ProjectTable({
  projects,
  total,
  isLoading,
  onPageChange,
  onRowClick,
  limit = 20,
  offset = 0,
}: ProjectTableProps) {
  const start = offset + 1
  const end = Math.min(offset + limit, total)

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  if (projects.length === 0) {
    return (
      <div className="rounded-xl border bg-white p-8 text-center text-muted-foreground">
        No projects yet. Create your first project to get started.
      </div>
    )
  }

  return (
    <div className="rounded-xl border bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="px-4 py-3 font-medium">Project Name</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => (
              <tr
                key={project.id}
                className="cursor-pointer border-b last:border-0 hover:bg-muted/50 transition-colors"
                onClick={() => onRowClick(project.id)}
              >
                <td className="px-4 py-3 font-medium">{project.name}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  {project.project_type || '-'}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={project.status} />
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {formatDate(project.created_at)}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {formatDate(project.updated_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > limit && (
        <div className="flex items-center justify-between border-t px-4 py-3">
          <span className="text-sm text-muted-foreground">
            {start}-{end} of {total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => onPageChange(Math.max(0, offset - limit))}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + limit >= total}
              onClick={() => onPageChange(offset + limit)}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

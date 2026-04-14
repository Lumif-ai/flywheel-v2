import { useNavigate } from 'react-router'
import { FileSearch, CheckCircle, Download, Clock, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDashboardTasks } from '../hooks/useDashboardTasks'
import type { DashboardTask } from '../types/broker'

const TASK_CONFIG: Record<
  DashboardTask['type'],
  { icon: typeof FileSearch; label: string }
> = {
  review: { icon: FileSearch, label: 'Review' },
  approve: { icon: CheckCircle, label: 'Approve' },
  export: { icon: Download, label: 'Export' },
  followup: { icon: Clock, label: 'Follow Up' },
}

const MAX_DISPLAY = 10

export function TaskList() {
  const navigate = useNavigate()
  const { data, isLoading } = useDashboardTasks()

  if (isLoading) {
    return (
      <div className="rounded-xl border bg-white shadow-sm">
        <div className="px-4 py-3 border-b">
          <h2 className="text-lg font-semibold text-foreground">Tasks</h2>
        </div>
        <div className="divide-y">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-3 flex-1">
                <div className="h-5 w-5 animate-pulse rounded bg-muted" />
                <div className="h-4 w-48 animate-pulse rounded bg-muted" />
              </div>
              <div className="h-8 w-20 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  const tasks = data?.tasks ?? []
  const total = data?.total ?? 0

  if (tasks.length === 0) {
    return (
      <div className="rounded-xl border bg-white shadow-sm">
        <div className="px-4 py-3 border-b">
          <h2 className="text-lg font-semibold text-foreground">Tasks</h2>
        </div>
        <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
          <CheckCircle2 className="h-8 w-8 mb-2" />
          <p className="text-sm">No pending tasks</p>
        </div>
      </div>
    )
  }

  const displayed = tasks.slice(0, MAX_DISPLAY)

  return (
    <div className="rounded-xl border bg-white shadow-sm">
      <div className="px-4 py-3 border-b">
        <h2 className="text-lg font-semibold text-foreground">Tasks</h2>
      </div>
      <div className="divide-y">
        {displayed.map((task, idx) => {
          const config = TASK_CONFIG[task.type]
          const Icon = config.icon
          return (
            <div
              key={`${task.type}-${task.project_id}-${idx}`}
              className="flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <p className="text-sm text-foreground truncate">{task.message}</p>
                  {task.type === 'followup' && task.carrier_name && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {task.carrier_name}
                      {task.days_overdue != null && task.days_overdue > 0 && (
                        <span className="ml-1 text-amber-600">
                          ({task.days_overdue}d overdue)
                        </span>
                      )}
                    </p>
                  )}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="shrink-0 ml-3"
                onClick={() => navigate(`/broker/projects/${task.project_id}`)}
              >
                {config.label}
              </Button>
            </div>
          )
        })}
      </div>
      {total > MAX_DISPLAY && (
        <div className="border-t px-4 py-2 text-center">
          <button
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => navigate('/broker/projects')}
          >
            View all ({total})
          </button>
        </div>
      )}
    </div>
  )
}

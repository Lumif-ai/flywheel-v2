import { formatDistanceToNow } from 'date-fns'
import { FileText, CheckCircle, AlertCircle, Edit2, Upload, PlusCircle } from 'lucide-react'
import type { BrokerActivity } from '../types/broker'

const ACTION_CONFIG: Record<string, { label: string; icon: typeof FileText }> = {
  project_created: { label: 'Project created', icon: PlusCircle },
  analysis_started: { label: 'Analysis started', icon: FileText },
  analysis_completed: { label: 'Analysis completed', icon: CheckCircle },
  analysis_failed: { label: 'Analysis failed', icon: AlertCircle },
  coverage_updated: { label: 'Coverage updated', icon: Edit2 },
  document_uploaded: { label: 'Document uploaded', icon: Upload },
}

interface ActivityTimelineProps {
  activities: BrokerActivity[]
}

export function ActivityTimeline({ activities }: ActivityTimelineProps) {
  if (!activities || activities.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No activity yet.</p>
    )
  }

  const sorted = [...activities].sort(
    (a, b) => new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime()
  )

  return (
    <div className="max-h-[400px] overflow-y-auto">
      <div className="relative space-y-4 pl-6">
        {/* Vertical timeline line */}
        <div className="absolute left-[9px] top-2 bottom-2 w-px bg-border" />

        {sorted.map((activity) => {
          const config = ACTION_CONFIG[activity.activity_type] ?? {
            label: activity.activity_type.replace(/_/g, ' '),
            icon: FileText,
          }
          const Icon = config.icon

          return (
            <div key={activity.id} className="relative flex items-start gap-3">
              {/* Dot on timeline */}
              <div className="absolute -left-6 top-1 flex h-[18px] w-[18px] items-center justify-center rounded-full border bg-background">
                <Icon className="h-3 w-3 text-muted-foreground" />
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium leading-tight">{config.label}</p>
                {activity.description && (
                  <p className="text-xs text-muted-foreground truncate">{activity.description}</p>
                )}
                <p className="text-xs text-muted-foreground mt-0.5">
                  {activity.actor_type && <span>{activity.actor_type} &middot; </span>}
                  {formatDistanceToNow(new Date(activity.occurred_at), { addSuffix: true })}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

import { Badge } from '@/components/ui/badge'
import type { TaskStatus } from '../types/tasks'

interface TaskStatusBadgeProps {
  status: TaskStatus
}

const statusStyles: Record<TaskStatus, { color: string; background: string }> = {
  detected: { color: '#6B7280', background: 'rgba(107,114,128,0.1)' },
  in_review: { color: '#D97706', background: 'rgba(245,158,11,0.1)' },
  confirmed: { color: '#3B82F6', background: 'rgba(59,130,246,0.1)' },
  in_progress: { color: 'var(--brand-coral)', background: 'var(--brand-tint)' },
  done: { color: '#22C55E', background: 'rgba(34,197,94,0.1)' },
  blocked: { color: '#EF4444', background: 'rgba(239,68,68,0.1)' },
  dismissed: { color: '#9CA3AF', background: 'rgba(156,163,175,0.1)' },
  deferred: { color: '#D97706', background: 'rgba(245,158,11,0.1)' },
}

function formatStatusLabel(status: TaskStatus): string {
  return status
    .replace(/_/g, ' ')
    .replace(/^./, (c) => c.toUpperCase())
}

export function TaskStatusBadge({ status }: TaskStatusBadgeProps) {
  const style = statusStyles[status]

  return (
    <Badge
      variant="secondary"
      style={{
        color: style.color,
        background: style.background,
        border: 'none',
      }}
    >
      {formatStatusLabel(status)}
    </Badge>
  )
}

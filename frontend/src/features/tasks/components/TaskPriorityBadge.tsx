import { ChevronUp, Minus, ChevronDown } from 'lucide-react'
import type { Priority } from '../types/tasks'

interface TaskPriorityBadgeProps {
  priority: Priority
}

const priorityConfig: Record<Priority, { icon: typeof ChevronUp; label: string; color: string }> = {
  high: { icon: ChevronUp, label: 'High', color: 'var(--error)' },
  medium: { icon: Minus, label: 'Medium', color: 'var(--warning)' },
  low: { icon: ChevronDown, label: 'Low', color: 'var(--secondary-text)' },
}

export function TaskPriorityBadge({ priority }: TaskPriorityBadgeProps) {
  const config = priorityConfig[priority]
  const Icon = config.icon

  return (
    <span
      className="inline-flex items-center gap-0.5"
      style={{
        color: config.color,
        fontSize: '12px',
        fontWeight: 500,
      }}
    >
      <Icon className="size-3.5" />
      {config.label}
    </span>
  )
}

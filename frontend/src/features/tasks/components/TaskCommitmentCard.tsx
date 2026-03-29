import { NavLink } from 'react-router'
import { MapPin, Building2, Calendar, Zap } from 'lucide-react'
import { formatDistanceToNow, isBefore, isEqual, startOfDay, endOfWeek } from 'date-fns'
import { BrandedCard } from '@/components/ui/branded-card'
import { Button } from '@/components/ui/button'
import { TaskStatusBadge } from './TaskStatusBadge'
import { TaskPriorityBadge } from './TaskPriorityBadge'
import { TaskSkillChip } from './TaskSkillChip'
import type { Task } from '../types/tasks'

interface TaskCommitmentCardProps {
  task: Task
  onSelect: (id: string) => void
}

function getDueDateColor(dueDate: string | null): string {
  if (!dueDate) return 'var(--secondary-text)'

  const now = new Date()
  const todayStart = startOfDay(now)
  const due = startOfDay(new Date(dueDate))
  const weekEnd = endOfWeek(now, { weekStartsOn: 1 })

  if (isBefore(due, todayStart)) return 'var(--task-overdue-text)'
  if (isEqual(due, todayStart)) return 'var(--warning)'
  if (isBefore(due, weekEnd) || isEqual(due, weekEnd)) return 'var(--heading-text)'
  return 'var(--secondary-text)'
}

function formatDueDate(dueDate: string | null): string {
  if (!dueDate) return 'No date'
  const due = new Date(dueDate)
  const todayStart = startOfDay(new Date())
  const dueStart = startOfDay(due)

  if (isEqual(dueStart, todayStart)) return 'Today'
  if (isBefore(dueStart, todayStart)) {
    return formatDistanceToNow(due, { addSuffix: true })
  }
  return due.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function TaskCommitmentCard({ task, onSelect }: TaskCommitmentCardProps) {
  const isOverdue = task.due_date && isBefore(startOfDay(new Date(task.due_date)), startOfDay(new Date()))

  return (
    <BrandedCard
      variant={isOverdue ? 'action' : 'info'}
      hoverable
      onClick={() => onSelect(task.id)}
      className="!p-0"
    >
      <div
        style={{ padding: '20px 24px' }}
        className="flex flex-col"
      >
        {/* Title */}
        <h3
          className="line-clamp-2"
          style={{
            fontSize: '15px',
            fontWeight: 600,
            color: 'var(--heading-text)',
            margin: 0,
            marginBottom: '12px',
          }}
        >
          {task.title}
        </h3>

        {/* Provenance row */}
        <div
          className="flex items-center gap-1.5"
          style={{
            fontSize: '13px',
            fontWeight: 400,
            color: 'var(--secondary-text)',
            marginBottom: '8px',
          }}
        >
          <MapPin className="size-3.5 shrink-0" />
          <span>
            {task.meeting_id
              ? `Meeting \u00b7 ${formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}`
              : 'Manual task'}
          </span>
        </div>

        {/* Account row (conditional) */}
        {task.account_id && (
          <div
            className="flex items-center gap-1.5"
            style={{
              fontSize: '13px',
              fontWeight: 400,
              marginBottom: '8px',
            }}
          >
            <Building2 className="size-3.5 shrink-0" style={{ color: 'var(--secondary-text)' }} />
            <NavLink
              to={`/accounts/${task.account_id}`}
              style={{ color: 'var(--brand-coral)', textDecoration: 'none' }}
              onClick={(e) => e.stopPropagation()}
            >
              {task.metadata?.account_name
                ? String(task.metadata.account_name)
                : 'View account'}
            </NavLink>
          </div>
        )}

        {/* Status row */}
        <div
          className="flex items-center gap-3 flex-wrap"
          style={{ marginBottom: task.suggested_skill ? '8px' : '0' }}
        >
          <TaskStatusBadge status={task.status} />
          <TaskPriorityBadge priority={task.priority} />
          <span
            className="inline-flex items-center gap-1"
            style={{
              fontSize: '13px',
              fontWeight: 500,
              color: getDueDateColor(task.due_date),
            }}
          >
            <Calendar className="size-3.5" />
            {formatDueDate(task.due_date)}
          </span>
        </div>

        {/* Skill row (conditional) */}
        {task.suggested_skill && (
          <div className="flex items-center justify-between">
            <TaskSkillChip skillName={task.suggested_skill} />
            {task.status === 'confirmed' && (
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  // Generate action wired in later plan
                }}
              >
                <Zap className="size-3" data-icon="inline-start" />
                Generate
              </Button>
            )}
          </div>
        )}
      </div>
    </BrandedCard>
  )
}

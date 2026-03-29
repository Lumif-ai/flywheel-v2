import { useMemo } from 'react'
import { NavLink } from 'react-router'
import { CheckCircle, X } from 'lucide-react'
import { isBefore, startOfDay } from 'date-fns'
import { BrandedCard } from '@/components/ui/branded-card'
import { Badge } from '@/components/ui/badge'
import { useTaskSummary } from '../hooks/useTaskSummary'
import { useTasks } from '../hooks/useTasks'
import { useUpdateTaskStatus } from '../hooks/useUpdateTaskStatus'
import type { Task, TaskStatus } from '../types/tasks'

const TRIAGE_STATUSES: Set<TaskStatus> = new Set(['detected', 'in_review', 'deferred'])
const PROMISE_DIRECTIONS = new Set(['theirs', 'mutual'])
const EXCLUDED_STATUSES = new Set(['done', 'dismissed'])
const MAX_WIDGET_ITEMS = 3

function formatWidgetDueDate(dueDate: string | null): string | null {
  if (!dueDate) return null
  const due = new Date(dueDate)
  return due.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function BriefingTasksWidget() {
  const { data: summary } = useTaskSummary()
  const { data: tasksData } = useTasks()
  const statusMutation = useUpdateTaskStatus()

  const tasks = tasksData?.tasks ?? []

  // Filter triage-eligible tasks
  const triageTasks = useMemo(
    () => tasks.filter((t) => TRIAGE_STATUSES.has(t.status)),
    [tasks],
  )

  // Count overdue promises (theirs/mutual, not done/dismissed, past due)
  const overduePromiseCount = useMemo(() => {
    const today = startOfDay(new Date())
    return tasks.filter(
      (t) =>
        PROMISE_DIRECTIONS.has(t.commitment_direction) &&
        !EXCLUDED_STATUSES.has(t.status) &&
        t.due_date &&
        isBefore(startOfDay(new Date(t.due_date)), today),
    ).length
  }, [tasks])

  // Check if anything exists at all
  const totalAll = summary
    ? summary.detected +
      summary.in_review +
      summary.confirmed +
      summary.in_progress +
      summary.done +
      summary.blocked +
      summary.dismissed +
      summary.deferred
    : 0

  // Hide widget entirely when no tasks exist
  if (totalAll === 0) return null

  const triageCount = triageTasks.length
  const displayTasks = triageTasks.slice(0, MAX_WIDGET_ITEMS)
  const moreCount = triageCount - MAX_WIDGET_ITEMS

  const handleConfirm = (task: Task) => {
    statusMutation.mutate({ id: task.id, status: 'confirmed' })
  }

  const handleDismiss = (task: Task) => {
    statusMutation.mutate({ id: task.id, status: 'dismissed' })
  }

  return (
    <BrandedCard variant={triageCount > 0 ? 'action' : 'info'} hoverable={false}>
      {/* Section title + count */}
      <div className="flex items-center gap-2" style={{ marginBottom: triageCount > 0 || overduePromiseCount > 0 ? '16px' : '0' }}>
        <span
          style={{
            fontSize: '18px',
            fontWeight: 600,
            color: 'var(--heading-text)',
          }}
        >
          Next Actions
        </span>
        {triageCount > 0 && (
          <Badge variant="secondary">{triageCount}</Badge>
        )}
      </div>

      {/* Triage items (max 3) */}
      {displayTasks.length > 0 && (
        <div className="flex flex-col gap-2" style={{ marginBottom: moreCount > 0 || overduePromiseCount > 0 ? '12px' : '16px' }}>
          {displayTasks.map((task) => (
            <WidgetTriageRow
              key={task.id}
              task={task}
              onConfirm={handleConfirm}
              onDismiss={handleDismiss}
            />
          ))}
        </div>
      )}

      {/* "+N more" text */}
      {moreCount > 0 && (
        <p
          style={{
            fontSize: '13px',
            fontWeight: 400,
            color: 'var(--secondary-text)',
            margin: '0 0 12px 0',
          }}
        >
          +{moreCount} more
        </p>
      )}

      {/* Overdue promises line */}
      {overduePromiseCount > 0 && (
        <div
          className="flex items-center gap-2"
          style={{ marginBottom: '16px' }}
        >
          <span
            className="shrink-0 rounded-full"
            style={{
              width: '8px',
              height: '8px',
              background: 'var(--error)',
              display: 'inline-block',
            }}
          />
          <span
            style={{
              fontSize: '13px',
              fontWeight: 500,
              color: 'var(--error)',
            }}
          >
            {overduePromiseCount} overdue promise{overduePromiseCount !== 1 ? 's' : ''}
          </span>
        </div>
      )}

      {/* Footer link */}
      <div
        className="pt-3 border-t"
        style={{ borderColor: 'var(--subtle-border)' }}
      >
        <NavLink
          to="/tasks"
          className="no-underline hover:underline"
          style={{
            fontSize: '13px',
            fontWeight: 500,
            color: 'var(--brand-coral)',
          }}
        >
          View all tasks &rarr;
        </NavLink>
      </div>
    </BrandedCard>
  )
}

// ---------------------------------------------------------------------------
// Compact triage row for widget
// ---------------------------------------------------------------------------

function WidgetTriageRow({
  task,
  onConfirm,
  onDismiss,
}: {
  task: Task
  onConfirm: (task: Task) => void
  onDismiss: (task: Task) => void
}) {
  const dueDateText = formatWidgetDueDate(task.due_date)

  return (
    <div className="flex items-center gap-2 group">
      {/* Dot indicator */}
      <span
        className="shrink-0 rounded-full"
        style={{
          width: '8px',
          height: '8px',
          background: 'var(--brand-coral)',
          display: 'inline-block',
        }}
      />

      {/* Title */}
      <span
        className="truncate flex-1 min-w-0"
        style={{
          fontSize: '14px',
          fontWeight: 400,
          color: 'var(--heading-text)',
        }}
      >
        {task.title}
      </span>

      {/* Due date */}
      {dueDateText && (
        <span
          className="shrink-0"
          style={{
            fontSize: '13px',
            fontWeight: 400,
            color: 'var(--secondary-text)',
          }}
        >
          {dueDateText}
        </span>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => onConfirm(task)}
          aria-label="Confirm task"
          className="flex items-center justify-center rounded transition-colors"
          style={{
            width: '24px',
            height: '24px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--secondary-text)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--success)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--secondary-text)'
          }}
        >
          <CheckCircle className="size-4" strokeWidth={1.5} />
        </button>
        <button
          onClick={() => onDismiss(task)}
          aria-label="Dismiss task"
          className="flex items-center justify-center rounded transition-colors"
          style={{
            width: '24px',
            height: '24px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--secondary-text)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--error)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--secondary-text)'
          }}
        >
          <X className="size-4" strokeWidth={1.5} />
        </button>
      </div>
    </div>
  )
}
